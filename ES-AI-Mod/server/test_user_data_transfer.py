import ast
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

import ui_i18n
import user_data_transfer as transfer


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()

    def write(self, name, value):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def archive(self, entries):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        content = stream.getvalue()
        for name, _ in entries:
            if isinstance(name, str) and "\\" in name:
                content = content.replace(name.replace("\\", "/").encode(), name.encode())
        stream = io.BytesIO(content)
        stream.seek(0)
        return stream

    def test_round_trip_optional_keys_and_exclusions(self):
        for name in ("config.json", "es_characters.json", "story_events.json",
                     "memory/public_scene.json", "memory/conversations/un.json"):
            self.write(name, {})
        self.write("keys.json", {"test_api_key": "synthetic-test-value"})
        for name in ("delivery_outbox.json", "story_pending.json", "import_backups/old/config.json",
                     "cache_tts/test.json", "settings_window_error.log"):
            self.write(name, {})
        files = transfer.export_files(self.data)
        self.assertEqual(len(files), 5)
        self.assertNotIn("keys.json", files)
        self.assertIn("keys.json", transfer.export_files(self.data, True))
        archive = self.root / "export.zip"
        transfer.write_archive(archive, files)
        self.assertEqual(transfer.read_archive(archive), files)

    def test_reject_unsafe_archive_before_writes(self):
        original = self.write("config.json", {"old": True}).read_bytes()
        for name, data in (("../config.json", b"{}"), ("/config.json", b"{}"),
                           ("C:/config.json", b"{}"), ("memory\\bad.json", b"{}"),
                           ("server.py", b"{}"), ("story_pending.json", b"{}"), ("memory/CON.json", b"{}"),
                           ("keys.json", b'{"key":true}'), ("config.json", b'{"llm":[]}'),
                           ("config.json", b'{"game_clock":{"enabled":1}}'),
                           ("memory/test.json", b"null"), ("config.json", b'{"x":NaN}')):
            with self.subTest(name=name, data=data), self.assertRaises(ValueError):
                transfer.read_archive(self.archive([("es_characters.json", b"{}"), (name, data)]))
        self.assertEqual((self.data / "config.json").read_bytes(), original)
        self.assertFalse((self.data / "es_characters.json").exists())

    def test_duplicate_symlink_and_size_limits(self):
        with self.assertRaises(ValueError):
            transfer.read_archive(self.archive([("config.json", b"{}"), ("config.json", b"{}")]))
        link = zipfile.ZipInfo("config.json")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            transfer.read_archive(self.archive([(link, b"{}")]))
        for limit, value in (("MAX_FILE", 1), ("MAX_TOTAL", 1), ("MAX_FILES", 0)):
            with patch.object(transfer, limit, value), self.assertRaises(ValueError):
                transfer.read_archive(self.archive([("config.json", b"{}")]))

    def test_backup_merge_and_rollback_preserve_metadata(self):
        original = self.write("config.json", {"old": True})
        self.write("keys.json", {"key": "synthetic"})
        before = original.stat().st_mtime_ns
        backup = transfer.import_files(self.data, {"config.json": b'{"new":true}'})
        self.assertEqual(json.loads((backup / "config.json").read_text()), {"old": True})
        self.assertEqual((backup / "config.json").stat().st_mtime_ns, before)
        self.assertEqual(json.loads((self.data / "keys.json").read_text()), {"key": "synthetic"})
        previous = original.read_bytes()
        previous_time = original.stat().st_mtime_ns
        replace = transfer.os.replace
        calls = [0]

        def fail_second(source, destination):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError("synthetic write failure")
            replace(source, destination)

        with patch.object(transfer.os, "replace", side_effect=fail_second), self.assertRaises(OSError):
            transfer.import_files(self.data, {"config.json": b"{}", "memory/conversations/un.json": b"{}"})
        self.assertEqual(original.read_bytes(), previous)
        self.assertEqual(original.stat().st_mtime_ns, previous_time)
        self.assertFalse((self.data / "memory").exists())
        self.assertNotIn("import_backups", " ".join(transfer.export_files(self.data)))

    def test_invalid_batch_does_not_change_any_file(self):
        self.write("config.json", {"old": True})
        with self.assertRaises(ValueError):
            transfer.import_files(self.data, {"config.json": b"{}", "keys.json": b'{"key":false}'})
        self.assertEqual(json.loads((self.data / "config.json").read_text()), {"old": True})
        self.assertFalse((self.data / "import_backups").exists())

    def test_footer_labels_translated_and_ordered(self):
        for ru, en in (("Экспорт", "Export"), ("Импорт", "Import"), ("Конфиги", "Configs")):
            self.assertEqual(ui_i18n.tr(ru, "en"), en)
            self.assertEqual(ui_i18n.tr(ru, "ru"), ru)
        source = Path(__file__).with_name("settings_window.py").read_text(encoding="utf-8-sig")
        self.assertIn("b_hist.place(x0, upper_y)", source)
        self.assertIn("b_folder.place(x0, transfer_y)", source)
        self.assertIn("upper_y - 18", source)
        tree = ast.parse(source)
        owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_settings_window")
        functions = [n for n in owner.body if isinstance(n, ast.FunctionDef) and
                     n.name in ("transfer_directory", "open_config_folder")]
        for workshop in (False, True):
            loader = Mock(user_data_dir=Mock(return_value="stub-user-folder")) if workshop else object()
            os_mock = Mock(path=transfer.os.path, environ={"LOCALAPPDATA": "stub-local"})
            env = {"config_loader": loader, "BASE_DIR": "stub-server", "os": os_mock}
            exec(compile(ast.Module(body=functions, type_ignores=[]), "folder", "exec"), env)
            env["open_config_folder"]()
            expected = "stub-user-folder" if workshop else transfer.os.path.join("stub-local", "AI.Sovenok")
            os_mock.startfile.assert_called_once_with(expected)
            self.assertEqual(env["transfer_directory"](), "stub-user-folder" if workshop else "stub-server")

    def test_import_closes_without_save_and_errors_stay_open(self):
        import tkinter.filedialog
        import tkinter.messagebox
        source = Path(__file__).with_name("settings_window.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_settings_window")
        nodes = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "import_user_data"]
        helper = Mock(read_archive=Mock(return_value={"keys.json": b'{"key":"synthetic"}'}))
        env = dict(user_data_transfer=helper, root=Mock(), config_loader=Mock(), _post=Mock(),
                   transfer_directory=lambda: "stub-only", tr=lambda text: text, save_all=Mock())
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "import-ui", "exec"), env)
        for confirmed, failed in ((False, False), (True, True), (True, False)):
            env["root"].reset_mock()
            helper.reset_mock()
            helper.import_files.side_effect = OSError("synthetic") if failed else None
            with patch.object(tkinter.filedialog, "askopenfilename", return_value="stub.zip"), \
                    patch.object(tkinter.messagebox, "askyesno", return_value=confirmed) as confirm, \
                    patch.object(tkinter.messagebox, "showinfo"), patch.object(tkinter.messagebox, "showerror"):
                env["import_user_data"]()
            self.assertIn("ключи API", confirm.call_args.args[1])
            self.assertEqual(env["root"].destroy.call_count, int(confirmed and not failed))
            self.assertEqual(helper.import_files.call_count, int(confirmed))
            env["save_all"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
