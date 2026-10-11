"""Static packaging and isolated Workshop loader regressions; no live keys reads."""
import ast
import copy
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import test_deploy_workshop as packaging
from test_paths import WORKSHOP_ROOT


class WorkshopDefaultsTests(unittest.TestCase):
    setUp = packaging.DeploymentTests.setUp
    snapshot = packaging.DeploymentTests.snapshot
    build = packaging.DeploymentTests.build
    change = packaging.DeploymentTests.change

    def defaults_source(self, value):
        source = self.files["server/config_loader.py"].decode()
        return (source[:source.index("DEFAULT_CONFIG =")] + "DEFAULT_CONFIG = " + value + "\n").encode()

    def test_defaults_packaged_without_user_data(self):
        self.build()
        tree = ast.parse((self.bundle / "server/config_loader.py").read_text())
        self.assertEqual(packaging.deploy.embedded_defaults(tree), packaging.deploy.POLICY["static_defaults"])
        self.assertFalse((self.bundle / "server/config.defaults.json").exists())
        self.assertEqual(self.snapshot(self.target), self.original)
        self.assertNotIn("server/config.json", self.snapshot(self.bundle))
        self.assertNotIn("server/keys.json", self.snapshot(self.bundle))

    def test_secret_pii_and_real_identifiers_rejected(self):
        for value in ({"api_key": ""}, {"llm": {"api_key": "secret"}},
                      {"player_name": "private"}, {"tts": {"fish_reference_id": "real-id"}},
                      {"llm": {"api_url": "https://private.example/v1"}},
                      {"host": "private-host"}, {"port": True}):
            with self.subTest(value=value):
                defaults = copy.deepcopy(packaging.deploy.POLICY["static_defaults"])
                for key, item in value.items():
                    if isinstance(item, dict) and key in defaults:
                        defaults[key].update(item)
                    else:
                        defaults[key] = item
                self.change("server/config_loader.py", self.defaults_source(repr(defaults)))
                with self.assertRaises(packaging.deploy.DeploymentError):
                    self.build()
                self.assertFalse(self.bundle.exists())

    def test_exact_public_defaults_required(self):
        for value in ({}, {"llm": {"api_url": "", "model": ""}}):
            with self.assertRaises(packaging.deploy.DeploymentError):
                packaging.deploy.embedded_defaults(ast.parse(self.defaults_source(repr(value))))

    def test_duplicate_and_nonobject_defaults_rejected(self):
        for data in ('{"host":"127.0.0.1","host":"127.0.0.1"}', '[]', 'None', '{bad',
                     'dict()', '{**{}}', '{"host": str("127.0.0.1")}',
                     repr(packaging.deploy.POLICY["static_defaults"]) + '\nDEFAULT_CONFIG = {}',
                     '{' + ','.join('"host":"127.0.0.1"' for _ in range(300)) + '}'):
            files = dict(self.files)
            files["server/config_loader.py"] = self.defaults_source(data)
            with self.assertRaises((ValueError, SyntaxError)):
                packaging.deploy.validate(files)

    def test_required_defaults_missing_rejected(self):
        self.change("server/config_loader.py", self.files["server/config_loader.py"].split(b"DEFAULT_CONFIG =")[0])
        with self.assertRaisesRegex(packaging.deploy.DeploymentError, "DEFAULT_CONFIG"):
            self.build()

    def test_stale_bundled_template_rejected(self):
        self.build()
        (self.bundle / "server/config.defaults.json").write_text("{}")
        with self.assertRaisesRegex(packaging.deploy.DeploymentError, "unallowlisted content"):
            packaging.deploy.verify(self.bundle)

    def test_workshop_only_defaults_check_is_read_only(self):
        project = self.root / "project"
        for name, data in self.files.items():
            path = project / (name if name.startswith("server/") else "mod/" + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        before = self.snapshot(project)
        result = packaging.deploy.check(project, self.target)
        self.assertTrue(result["development_validation"]["sanitized_defaults"])
        self.assertEqual(self.snapshot(project), before)
        self.assertEqual(self.snapshot(self.target), self.original)

    def load_isolated(self, config=None, legacy=None):
        path = Path(WORKSHOP_ROOT) / "server/config_loader.py"
        if not path.is_file():
            self.skipTest("Workshop loader unavailable")
        source = path.read_text(encoding="utf-8")
        server = self.root / "loader-server"
        server.mkdir(exist_ok=True)
        local = self.root / "local"
        user = local / "AI.Sovenok"
        user.mkdir(parents=True)
        if config is not None:
            (user / "config.json").write_text(config, encoding="utf-8")
        if legacy is not None:
            (server / "config.json").write_text(legacy, encoding="utf-8")
        module = types.ModuleType("isolated_workshop_loader")
        module.__file__ = str(server / "config_loader.py")
        with patch.dict("os.environ", {"LOCALAPPDATA": str(local)}):
            exec(compile(source, module.__file__, "exec"), module.__dict__)
        return module, user, server

    def test_fresh_config_created_at_import_once(self):
        module, user, server = self.load_isolated()
        self.assertEqual(module.DEFAULT_CONFIG, packaging.deploy.POLICY["static_defaults"])
        self.assertEqual(json.loads((user / "config.json").read_text()), module.DEFAULT_CONFIG)
        before = self.snapshot(user)
        identity = module.cfg
        module.reload_all()
        self.assertIs(module.cfg, identity)
        self.assertEqual(self.snapshot(user), before)
        self.assertFalse((server / "config.json").exists())
        self.assertFalse((server / "keys.json").exists())
        self.assertFalse((user / "keys.json").exists())
        self.assertEqual(module.keys, {"cerebras_api_key": ""})

    def test_existing_config_never_overlaid_or_rewritten(self):
        module, user, _ = self.load_isolated('{ "llm": {"provider": "custom"}, "player_name": "test" }')
        before = self.snapshot(user)
        module.reload_all()
        self.assertEqual(module.cfg, {"llm": {"provider": "custom"}, "player_name": "test"})
        self.assertEqual(self.snapshot(user), before)

    def test_empty_config_preserved_even_with_legacy(self):
        module, user, _ = self.load_isolated('{}', '{"host":"legacy"}')
        module.reload_all()
        self.assertEqual(module.cfg, {})
        self.assertEqual((user / "config.json").read_text(), '{}')

    def test_legacy_config_migrated_without_overlay(self):
        legacy = '{ "llm": {"provider":"custom"} }'
        module, user, server = self.load_isolated(legacy=legacy)
        self.assertEqual(module.cfg, json.loads(legacy))
        self.assertEqual((user / "config.json").read_text(), legacy)
        self.assertEqual((server / "config.json").read_text(), legacy)

    def test_malformed_config_fallback_isolated_without_rewrite(self):
        module, user, _ = self.load_isolated('{bad')
        baseline = copy.deepcopy(module.DEFAULT_CONFIG)
        module.cfg["tts"]["narrator_voice"]["fish"] = "modified"
        self.assertEqual(module.DEFAULT_CONFIG, baseline)
        identity = module.cfg
        module.reload_all()
        self.assertIs(module.cfg, identity)
        self.assertEqual(module.cfg, baseline)
        self.assertEqual((user / "config.json").read_text(), '{bad')
        self.assertIsNot(module.cfg["tts"]["narrator_voice"], module.DEFAULT_CONFIG["tts"]["narrator_voice"])

    def test_missing_config_fallback_isolated_on_write_failure(self):
        module, user, _ = self.load_isolated()
        (user / "config.json").unlink()
        with patch("builtins.open", side_effect=PermissionError("test read-only directory")):
            module.reload_all()
            module.cfg["tts"]["narrator_voice"]["fish"] = "modified"
            module.reload_all()
        self.assertEqual(module.cfg, module.DEFAULT_CONFIG)
        self.assertFalse((user / "config.json").exists())

    def test_development_loader_keeps_local_config(self):
        source = Path(__file__).with_name("config_loader.py").read_text(encoding="utf-8")
        server = self.root / "dev-server"
        server.mkdir()
        (server / "config.json").write_text('{}')
        module = types.ModuleType("isolated_dev_loader")
        module.__file__ = str(server / "config_loader.py")
        with patch.dict("os.environ", {"LOCALAPPDATA": str(self.root / "unused")}):
            exec(compile(source, module.__file__, "exec"), module.__dict__)
            module.reload_all()
        self.assertEqual(module.cfg, {})
        self.assertFalse((self.root / "unused").exists())


if __name__ == "__main__":
    unittest.main()
