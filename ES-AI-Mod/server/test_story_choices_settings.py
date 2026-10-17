"""Offline story-choice UI state, persistence and layout regression checks."""
import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, mock_open, patch

import test_story_settings as story_tests
import test_settings_save_state as save_tests

SERVERS = story_tests.SERVERS
extract = story_tests.extract


class StoryChoicesSettingsTests(unittest.TestCase):
    def test_real_tk_repository_and_temporary_copy_offline(self):
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix="story-choices-ui-") as directory:
            target = Path(directory)
            shutil.copy2(source / "settings_window.py", target / "settings_window.py")
            shutil.copy2(source / "es_characters.json", target / "es_characters.json")
            with patch.object(save_tests, "DEV", source), patch.object(save_tests, "WORKSHOP", target):
                save_tests.SettingsSaveStateTests().test_real_tk_both_copies_offline()

    def test_strict_boolean_defaults(self):
        for server in SERVERS:
            for value in (None, False, 0, 1, "true", "false", [], {}, True):
                with self.subTest(server=server, value=value):
                    _, env = story_tests.StorySettingsTests().environment(
                        server, {"enabled": True, "choices_enabled": value})
                    self.assertEqual(env["story_choices"], [value is True])

    def test_child_hidden_preserved_and_deferred(self):
        for server in SERVERS:
            _, env = story_tests.StorySettingsTests().environment(
                server, {"enabled": True, "intensity": "high", "choices_enabled": True})
            def flow(chips, x, y, width):
                for chip in chips:
                    chip.place(x, y)
                    x += chip.w + 8
                return y + 34
            env["flow"] = flow
            for enabled in (True, False, True):
                if env["story_on"][0] != enabled:
                    env["story_sw"].command()
                env["lay_story"](28, 792, 150)
                self.assertTrue(env["story_choices"][0])
                for name in ("story_choices_sw", "story_choices_lbl"):
                    self.assertEqual(env[name].geo is not None, enabled)
                if enabled:
                    self.assertEqual(env["story_choices_sw"].geo[0], 28 + 24)
                    self.assertGreater(env["story_choices_sw"].geo[1], env["story_sw"].bbox()[3])
                    self.assertGreater(env["story_chips"][0][1].geo[1],
                                       env["story_choices_sw"].bbox()[3])
            env["story_choices_sw"].command()
            self.assertFalse(env["story_choices"][0])
            self.assertFalse(env["story_choices_sw"].on)
            self.assertEqual(env["cfg"]["story_events"],
                             dict(enabled=True, intensity="high", choices_enabled=True))
            env["config_loader"].save_config.assert_not_called()
            env["_post"].assert_not_called()

    def test_full_save_choices_independent_and_baseline(self):
        for server in SERVERS:
            for parent in (False, True):
                for choices in (False, True):
                    env, data, _ = save_tests.SettingsSaveStateTests().environment(server)
                    env["story_on"][0] = parent
                    env["story_choices"][0] = choices
                    env["story_intensity"][0] = "high"
                    env["refresh_save_state"]()
                    self.assertEqual(env["b_save"].kind, "primary")
                    with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                        self.assertTrue(env["save_all"]())
                    self.assertEqual(env["cfg"]["story_events"],
                                     dict(enabled=parent, intensity="high", choices_enabled=choices))
                    self.assertEqual(env["saved_state"][0], env["settings_snapshot"]())
                    self.assertEqual(env["b_save"].kind, "chip")

    def test_actual_label_retranslates_without_recreation(self):
        for server in SERVERS:
            tree, env = story_tests.StorySettingsTests().environment(server)
            env.update(canvas=Mock(), MANAGED=[], I18N_WIDGETS=[], OUT8=())
            extract([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                     and n.name in ("Managed", "Txt")], env)
            owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name == "run_settings_window")
            label = next(n for n in owner.body if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "story_choices_lbl"
                                 for t in n.targets))
            extract([label], env)
            widget = env["story_choices_lbl"]
            self.assertIn(widget, env["I18N_WIDGETS"])
            for lang, expected in (("en", "Story choices"), ("ru", "Сюжетные выборы")):
                env["ui_lang"][0] = lang
                widget.retranslate()
                self.assertIs(env["story_choices_lbl"], widget)
                self.assertEqual(env["canvas"].itemconfig.call_args.kwargs["text"], expected)


if __name__ == "__main__":
    unittest.main()
