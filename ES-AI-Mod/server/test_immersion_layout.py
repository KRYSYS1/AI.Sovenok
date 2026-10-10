"""Persistent offline checks of both immersion builds, with no config/API I/O."""
import ast
import itertools
import types
import unittest
from unittest.mock import Mock

from test_i18n_new_settings import SERVERS, extract
import test_story_settings as story_tests

Widget = story_tests.Widget


class ImmersionLayoutTests(unittest.TestCase):
    def environment(self, server):
        tree, env = story_tests.StorySettingsTests().environment(server)
        names = ("clock_sw clock_lbl clock_apply clock_time_l clock_time_f clock_step_l "
                 "clock_minus clock_step_f clock_plus cameo_sw cameo_lbl cf_l cf_val cf_sl "
                 "cl_l cl_val cl_sl ci_l ci_val ci_sl cx_l cx_val cx_sl pr_sec pn_l pn_f "
                 "persona_l persona_who persona_box pr_save").split()
        env.update({name: Widget() for name in names})
        env.update(H=34, LBL=20, ROW=70, MANAGED=[], PASS=[1], root=Mock(),
                   canvas=Mock(), immersion_bar=Mock(), immersion_scroll=[0, 0, 1],
                   clock_on=[False], cameo_on=[True], pr_chips=[Widget()],
                   prompt_targets=[("player", "KRYSYS", True)], prompt_idx=[0],
                   result_txt={"prompt": Widget()}, flow=lambda chips, x, y, width: y + 34)
        extract([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name in ("lay_clock", "lay_prompt", "scroll_immersion", "toggle_cameo", "toggle_clock")], env)
        return tree, env

    def test_all_flag_combinations_and_collapse_clamp(self):
        for server in SERVERS:
            for width, height in ((820, 640), (960, 740), (1280, 900)):
                _, env = self.environment(server)
                for clock, story, cameo in itertools.product((True, False), repeat=3):
                    env["clock_on"][0], env["story_on"][0], env["cameo_on"][0] = clock, story, cameo
                    env["immersion_scroll"][0] = 10000
                    bottom = height - 78
                    env["lay_prompt"](28, width - 28, 150, bottom)
                    self.assertLessEqual(env["immersion_scroll"][0], env["immersion_scroll"][1])
                    self.assertGreaterEqual(env["persona_box"].geo[3], 140)
                    self.assertLessEqual(env["pr_save"].geo[1] + 34, bottom)
                    self.assertEqual(env["clock_apply"].geo is not None, clock)
                    self.assertEqual(env["story_note"].geo is not None, story)
                    self.assertEqual(env["cf_sl"].geo is not None, cameo)
                    self.assertIsNotNone(env["clock_sw"].geo)
                    self.assertIsNotNone(env["story_sw"].geo)
                    self.assertIsNotNone(env["cameo_sw"].geo)

    def test_combined_toggle_save_defaults_and_no_open_write(self):
        for server in SERVERS:
            tree, env = self.environment(server)
            owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name == "run_settings_window")
            initial = next(n for n in owner.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "cameo_on" for t in n.targets))
            save = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "save_all")
            assignments = [n for n in save.body if isinstance(n, ast.Assign)
                           and ast.unparse(n.targets[0]) in ("cfg['cameo_enabled']", "cfg['cameo_stay']")]
            for cfg in ({}, {"cameo_enabled": True, "cameo_stay": False},
                        {"cameo_enabled": False, "cameo_stay": True}):
                env["cfg"] = dict(cfg)
                extract([initial], env)
                self.assertEqual(env["cameo_on"][0], cfg.get("cameo_enabled", True))
                self.assertEqual(env["cfg"], cfg)
                extract(assignments, env)
                self.assertEqual(env["cfg"]["cameo_stay"], env["cameo_on"][0])
                env["config_loader"].reset_mock()
                for _ in range(2):
                    env["toggle_cameo"]()
                    self.assertEqual(env["cfg"]["cameo_stay"], env["cfg"]["cameo_enabled"])
                self.assertEqual(env["config_loader"].save_config.call_count, 2)
            self.assertFalse(any(isinstance(n, ast.Name) and n.id == "cameo_stay_sw" for n in ast.walk(tree)))
            env["toggle_clock"]()
            env["toggle_story"]()
            self.assertGreaterEqual(env["layout"].call_count, 2)

    def test_custom_scrollbar_drag_page_and_minimum_thumb(self):
        class Canvas:
            def __init__(self, *args, **kwargs):
                self.options = kwargs
                self.lines = []
            def create_line(self, *args, **kwargs):
                self.lines.append(kwargs)
            def bind(self, *args):
                pass
            def coords(self, *args):
                pass

        for server in SERVERS:
            tree, env = self.environment(server)
            env.update(tk=types.SimpleNamespace(Canvas=Canvas), PARCH_HEX="#f7ebcf")
            extract([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                     and n.name == "ImmersionScrollbar"], env)
            bar = env["ImmersionScrollbar"]()
            callback = Mock()
            bar.config(command=callback)
            bar.redraw(types.SimpleNamespace(height=400))
            bar.set(0, .01)
            self.assertGreaterEqual(bar.thumb_size, 24)
            self.assertTrue(all(line["capstyle"] == "round" for line in bar.lines))
            bar.press(types.SimpleNamespace(y=390))
            callback.assert_called_with("scroll", 1, "pages")
            bar.press(types.SimpleNamespace(y=10))
            bar.motion(types.SimpleNamespace(y=10000))
            callback.assert_called_with("moveto", .99)
            bar.set(0, 1)
            self.assertEqual(bar.travel, 0)


if __name__ == "__main__":
    unittest.main()
