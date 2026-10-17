"""Deployment tests use synthetic installations only, never the live Workshop."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import importlib.util
import ast
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("deploy_workshop", Path(__file__).parents[1] / "tools" / "deploy_workshop.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
TEMP = TEST_TEMP


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.bundle = self.root / "bundle"
        self.backup = self.root / "backup"
        self.files = {n: b"# asset\n" for n in deploy.PATHS}
        self.files["server/es_characters.json"] = json.dumps({
            "characters": [{"id": "un", "name": "Lena", "persona": "Default NPC"}],
            "emotion_synonyms_ru": {}, "player": {"id": "player", "name": deploy.CANONICAL_PLAYER_NAME, "persona": ""}
        }).encode()
        self.files["server/config_loader.py"] = (
            b"import os\ncfg = {}\nkeys = {}\n"
            b"def user_data_dir(): return os.environ.get('LOCALAPPDATA', '') + 'AI.Sovenok'\n"
            b"def save_keys(): pass\ndef save_config(): pass\n"
            + ("DEFAULT_CONFIG = " + repr(deploy.POLICY["static_defaults"]) + "\n").encode())
        self.files["server/settings_window.py"] = (
            b"def run_settings_window(): pass\ndef _log_window_error(): pass\ndef _show_error_box(): pass\n")
        self.files["server/settings.pyw"] = (
            b"from settings_window import run_settings_window, _log_window_error, _show_error_box\n")
        self.files["server/main.py"] = (
            b"import npc_activity, scene_memory, selected_companions, story_events\n"
            b"from clothing_policy import cameo_requested_dress, clothing_refused, romantic_choice, private_scene\n")
        self.files["server/clothing_policy.py"] = (
            b"def cameo_requested_dress(cid, text, unnamed=False): pass\n"
            b"def clothing_refused(reply): pass\n"
            b"def romantic_choice(cid, age, player, reply, private): pass\n"
            b"def private_scene(scene, cid): pass\n")
        for root in (self.source, self.target):
            for name, data in self.files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        for name in ("server/config.json", "server/keys.json",
                     "server/memory/person.json", "server/__pycache__/old.pyc", "log.txt", "es_ai.rpyc"):
            path = self.target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"PRIVATE UNTOUCHED")
        self.original = self.snapshot(self.target)

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def build(self):
        return deploy.build(self.bundle, self.source, self.target)

    def change(self, name="server/npc_activity.py", data=b"value = 2\n"):
        (self.source / name).write_bytes(data)

    def test_reproducible_and_read_only_build_verify(self):
        first = self.build()
        self.assertFalse(first["validation"]["character_seed"]["custom_player"])
        second = deploy.build(self.root / "other", self.source, self.target)
        self.assertEqual(first, second)
        deploy.verify(self.bundle, self.target)
        self.assertEqual(self.snapshot(self.target), self.original)
        self.assertEqual(set(self.snapshot(self.bundle)), set(deploy.PATHS) | {"manifest.json"})
        self.assertIn("server/clothing_policy.py", deploy.PATHS)
        self.assertNotIn("server/test_clothing_requests.py", deploy.PATHS)
        self.assertEqual(first["validation"]["python_modules"], len(deploy.trees(self.files)))

    def test_apply_only_changes_selected_code(self):
        self.change()
        self.build()
        result = deploy.apply(self.bundle, self.target, self.backup)
        self.assertEqual(result["changed"], ["server/npc_activity.py"])
        expected = dict(self.original, **{"server/npc_activity.py": b"value = 2\n"})
        self.assertEqual(self.snapshot(self.target), expected)
        self.assertEqual((self.backup / "server/npc_activity.py").read_bytes(), self.files["server/npc_activity.py"])
        self.assertNotIn("server/keys.json", self.snapshot(self.backup))

    def test_absent_baseline_new_module(self):
        (self.target / "server/npc_activity.py").unlink()
        manifest = self.build()
        entry = next(e for e in manifest["files"] if e["path"] == "server/npc_activity.py")
        self.assertIsNone(entry["base_sha256"])
        deploy.apply(self.bundle, self.target, self.backup)
        self.assertTrue((self.target / "server/npc_activity.py").exists())

    def test_target_revision_conflict(self):
        self.build()
        (self.target / "server/story_events.py").write_bytes(b"concurrent = True\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "Target changed"):
            deploy.apply(self.bundle, self.target, self.backup)
        self.assertFalse(self.backup.exists())

    def test_bundle_hash_conflict(self):
        self.build()
        (self.bundle / "server/npc_activity.py").write_bytes(b"changed = True\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "hash mismatch"):
            deploy.verify(self.bundle, self.target)

    def test_secret_and_malicious_paths(self):
        for name in ("../server/main.py", "server/keys.json", "server/config.json", "userdata/es_characters.json",
                     "SERVER/main.py", "server/main.py.", "server/main.py:stream", "C:/server/main.py",
                     "server\\main.py", ".kilo/state.json", "es_ai.rpyc"):
            with self.subTest(name=name), self.assertRaises(deploy.DeploymentError):
                deploy.safe_path(self.target, name)

    def test_manifest_path_tampering(self):
        self.build()
        path = self.bundle / "manifest.json"
        for name in ("../keys.json", "server/keys.json", "SERVER/main.py"):
            manifest = json.loads(path.read_text())
            manifest["files"][0]["path"] = name
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(deploy.DeploymentError, "whitelist"):
                deploy.verify(self.bundle)

    def test_extra_secret_in_bundle_refused(self):
        self.build()
        (self.bundle / "keys.json").write_bytes(b"secret")
        with self.assertRaisesRegex(deploy.DeploymentError, "unallowlisted content"):
            deploy.verify(self.bundle)

    def test_missing_closure(self):
        for name in ("server/scene_memory.py", "server/clothing_policy.py"):
            with self.subTest(name=name):
                (self.source / name).unlink()
                with self.assertRaises(OSError):
                    self.build()
                self.assertFalse(self.bundle.exists())
                (self.source / name).write_bytes(self.files[name])

    def test_missing_character_seed_refused(self):
        (self.source / "server/es_characters.json").unlink()
        with self.assertRaises(OSError):
            self.build()
        self.assertFalse(self.bundle.exists())

    def test_private_player_and_credentials_refused(self):
        for extra in ({"player": {"name": "private", "persona": ""}},
                      {"player": {"name": "Semyon", "persona": "private"}},
                      {"api_key": "secret"}):
            seed = json.loads(self.files["server/es_characters.json"])
            seed.update(extra)
            self.change("server/es_characters.json", json.dumps(seed).encode())
            with self.assertRaises(deploy.DeploymentError):
                self.build()
            self.assertFalse(self.bundle.exists())

    def test_canonical_player_is_not_custom_and_builds(self):
        seed = json.loads(self.files["server/es_characters.json"])
        seed["player"]["persona"] = deploy.CANONICAL_PLAYER_PERSONA
        data = json.dumps(seed).encode()
        self.change("server/es_characters.json", data)
        result = deploy.validate(dict(self.files, **{"server/es_characters.json": data}))
        self.assertFalse(result["character_seed"]["custom_player"])
        self.assertFalse(self.build()["validation"]["character_seed"]["custom_player"])
        self.assertFalse(deploy.verify(self.bundle)[3]["character_seed"]["custom_player"])

    def test_custom_player_remains_custom_with_canonical_persona(self):
        for updates in ({"name": "private"}, {"id": "private"},
                        {"persona": deploy.CANONICAL_PLAYER_PERSONA + " private"},
                        {"persona": "private"}):
            seed = json.loads(self.files["server/es_characters.json"])
            seed["player"]["persona"] = deploy.CANONICAL_PLAYER_PERSONA
            seed["player"].update(updates)
            files = dict(self.files, **{"server/es_characters.json": json.dumps(seed).encode()})
            self.assertTrue(deploy.validate(files)["character_seed"]["custom_player"])

    def test_real_launchers_use_loader_port_without_live_imports(self):
        for root in existing_paths((deploy.PROJECT / "server", Path(WORKSHOP_ROOT) / "server")):
            source = (root / "settings.pyw").read_text(encoding="utf-8-sig")
            for port, expected in ((41234, 41234), (33147, 40310), (4999, 40310),
                                   (0, 40310), (65536, 40310), ("invalid", 40310)):
                called = []
                loader = types.ModuleType("config_loader")
                loader.cfg = {"port": port}
                window = types.ModuleType("settings_window")
                window.run_settings_window = lambda: called.append("window")
                window._log_window_error = lambda message: None
                window._show_error_box = lambda message: None
                env = {"__file__": str(root / "settings.pyw"), "__name__": "launcher_test"}
                with self.subTest(root=root, port=port), patch.dict("sys.modules", {
                        "config_loader": loader, "settings_window": window}), \
                        patch("sys.path", list(__import__("sys").path)), \
                        patch("urllib.request.urlopen") as request, \
                        patch("subprocess.Popen") as spawn:
                    exec(compile(source, env["__file__"], "exec"), env)
                    self.assertEqual(env["PORT"], expected)
                    request.assert_called_once_with("http://127.0.0.1:%s/health" % expected, timeout=2)
                    spawn.assert_not_called()
                    self.assertEqual(called, ["window"])
                tree = ast.parse((root / "settings_window.py").read_text(encoding="utf-8-sig"))
                functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name in ("_server_port", "_server_url")]
                if port in (41234, 33147, 4999):
                    helper = {"cfg": loader.cfg}
                    exec(compile(ast.Module(body=functions, type_ignores=[]), "window_helpers", "exec"), helper)
                    self.assertEqual(helper["_server_url"](), "http://127.0.0.1:%s" % expected)

    def test_unknown_import_refused(self):
        self.change(data=b"import missing_delivery_module\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "Missing dependency"):
            self.build()

    def test_launcher_missing_export_refused(self):
        for name, data in (("server/settings_window.py", b"def run_settings_window(): pass\n"),
                           ("server/clothing_policy.py", b"def clothing_refused(reply): pass\n")):
            with self.subTest(name=name):
                self.change(name, data)
                with self.assertRaisesRegex(deploy.DeploymentError, "Missing import exports"):
                    self.build()
                self.assertFalse(self.bundle.exists())
                self.change(name, self.files[name])

    def test_launcher_missing_helpers_refused(self):
        self.change("server/settings.pyw", b"from settings_window import run_settings_window\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "launcher helper"):
            self.build()

    def test_development_config_flavor_refused(self):
        self.change("server/config_loader.py", b"cfg = {}\nkeys = {}\n_DIR = '.'\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "Not Workshop flavor"):
            self.build()

    def test_provider_contract_preserved(self):
        (self.target / "server/tts_client.py").write_bytes(b"key_name = 'provider_api_key'\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "provider keys"):
            self.build()

    def test_user_data_routing_preserved(self):
        (self.target / "server/tts_client.py").write_bytes(b"from config_loader import user_data_dir\nfolder = user_data_dir()\n")
        with self.assertRaisesRegex(deploy.DeploymentError, "user-data routing"):
            self.build()

    def test_no_runtime_imports(self):
        self.change(data=b"raise RuntimeError('must not execute')\n")
        self.build()

    def test_output_parent_and_overlap_refused(self):
        for output in (self.root / "absent" / "bundle", self.target / "bundle", self.source / "bundle",
                       self.root / "AI.Sovenok" / "bundle", self.target):
            with self.subTest(output=output), self.assertRaises(deploy.DeploymentError):
                deploy.build(output, self.source, self.target)

    def test_symlink_refused(self):
        path = self.source / "server/npc_activity.py"
        path.unlink()
        try:
            path.symlink_to(self.target / "server/npc_activity.py")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(deploy.DeploymentError, "Symlink"):
            self.build()

    def test_atomic_failure_rolls_back(self):
        self.change("server/npc_activity.py")
        self.change("server/scene_memory.py")
        self.build()
        replace = os.replace
        calls = []
        def failing(src, dst):
            calls.append(str(dst))
            if len(calls) == 2:
                raise OSError("simulated commit failure")
            return replace(src, dst)
        with patch.object(deploy.os, "replace", side_effect=failing):
            with self.assertRaisesRegex(deploy.DeploymentError, "best-effort rollback"):
                deploy.apply(self.bundle, self.target, self.backup)
        self.assertEqual(self.snapshot(self.target), self.original)

    def test_rollback_does_not_overwrite_concurrent_edit(self):
        self.change("server/npc_activity.py")
        self.change("server/scene_memory.py")
        self.build()
        replace = os.replace
        calls = []
        def failing(src, dst):
            calls.append(str(dst))
            if len(calls) == 2:
                (self.target / "server/npc_activity.py").write_bytes(b"concurrent = True\n")
                raise OSError("simulated commit failure")
            return replace(src, dst)
        with patch.object(deploy.os, "replace", side_effect=failing):
            with self.assertRaisesRegex(deploy.DeploymentError, "conflicts=.*npc_activity"):
                deploy.apply(self.bundle, self.target, self.backup)
        self.assertEqual((self.target / "server/npc_activity.py").read_bytes(), b"concurrent = True\n")

    def test_apply_requires_backup_and_staging_requires_flavor(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                deploy.main(["--apply", str(self.bundle)])
            with self.assertRaises(SystemExit):
                deploy.main(["--build", str(self.bundle), "--source", str(self.source)])


if __name__ == "__main__":
    unittest.main()
