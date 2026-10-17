"""Persistent offline checks of both immersion builds, with no config/API I/O."""
import ast
import copy
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
        names = ("activity_sw activity_lbl auto_primary_sw auto_primary_lbl clock_sw clock_lbl clock_show_sw clock_show_lbl clock_time_l clock_time_f clock_step_l "
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
                    for name in ("clock_time_l", "clock_time_f", "clock_step_l", "clock_step_f",
                                 "clock_minus", "clock_plus", "clock_show_sw", "clock_show_lbl"):
                        self.assertEqual(env[name].geo is not None, clock, name)
                    if clock:
                        self.assertGreater(env["clock_show_sw"].geo[0], env["clock_sw"].geo[0])
                        self.assertGreater(env["clock_time_f"].geo[1], env["clock_show_sw"].bbox()[3])
                        self.assertGreater(env["clock_step_f"].geo[0],
                                           env["clock_time_f"].geo[0] + env["clock_time_f"].geo[2])
                    self.assertEqual(env["story_note"].geo is not None, story)
                    for name in ("story_choices_sw", "story_choices_lbl"):
                        self.assertEqual(env[name].geo is not None, story, name)
                    if story:
                        self.assertEqual(env["story_choices_sw"].geo[0] - env["story_sw"].geo[0],
                                          24)
                        self.assertGreater(env["story_choices_sw"].geo[1], env["story_sw"].bbox()[3])
                        self.assertGreater(env["story_note"].geo[1], env["story_choices_sw"].bbox()[3])
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

    def test_exact_child_coordinates_and_preserved_right_edge(self):
        for server in SERVERS:
            for left in (28, 53):
                tree, env = self.environment(server)
                extract([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                         and n.name == "flow"], env)
                for clock, story, cameo in itertools.product((True, False), repeat=3):
                    env["clock_on"][0], env["story_on"][0], env["cameo_on"][0] = clock, story, cameo
                    before = copy.deepcopy(env["cfg"])
                    env["lay_prompt"](left, 792, 150, 562)
                    child_left, right = left + 24, 772
                    for name in ("clock_sw", "story_sw", "cameo_sw", "auto_primary_sw",
                                 "activity_sw", "pr_sec", "pn_l", "pn_f", "persona_l", "persona_box"):
                        self.assertEqual(env[name].geo[0], left, name)
                    if clock:
                        for name in ("clock_show_sw", "clock_time_l", "clock_time_f"):
                            self.assertEqual(env[name].geo[0], child_left, name)
                        self.assertEqual(env["clock_show_lbl"].geo[0], child_left + 52 + 8)
                        for name in ("clock_step_l", "clock_minus"):
                            self.assertEqual(env[name].geo[0], child_left + 140, name)
                        self.assertEqual(env["clock_step_f"].geo[0], child_left + 140 + 106)
                        self.assertEqual(env["clock_plus"].geo[0], child_left + 140 + 176)
                        self.assertLessEqual(env["clock_plus"].bbox()[2], right)
                    for name in ("story_choices_sw", "story_choices_lbl", "story_note"):
                        self.assertEqual(env[name].geo is not None, story, name)
                    for _, chip in env["story_chips"]:
                        self.assertEqual(chip.geo is not None, story)
                        if story:
                            self.assertGreaterEqual(chip.geo[0], child_left)
                            self.assertLessEqual(chip.bbox()[2], right)
                    if story:
                        self.assertEqual(env["story_choices_sw"].geo[0], child_left)
                        self.assertEqual(env["story_choices_lbl"].geo[0], child_left + 52 + 8)
                        self.assertEqual(env["story_chips"][0][1].geo[0], child_left)
                        self.assertEqual(env["story_note"].geo[0], child_left)
                        self.assertEqual(env["story_note"].bbox()[2], right)
                    for prefix in ("cf", "cl", "ci", "cx"):
                        for suffix in ("l", "val", "sl"):
                            self.assertEqual(env[prefix + "_" + suffix].geo is not None, cameo)
                        if cameo:
                            self.assertEqual(env[prefix + "_l"].geo[0], child_left)
                            self.assertEqual(env[prefix + "_sl"].geo[0], child_left)
                            self.assertEqual(env[prefix + "_sl"].bbox()[2], right)
                            self.assertEqual(env[prefix + "_val"].geo[0], right)
                    self.assertEqual(env["cfg"], before)
                    env["config_loader"].save_config.assert_not_called()
                    env["_post"].assert_not_called()

    def test_native_tk_minimum_width_bilingual_snapshot(self):
        import tkinter as tk
        import tkinter.font as tkfont

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest("Tk display unavailable: %s" % error)
        self.addCleanup(root.destroy)
        root.geometry("820x640")
        for server in SERVERS:
            for lang in ("ru", "en"):
                with self.subTest(server=server, lang=lang):
                    tree, env = self.environment(server)
                    canvas = tk.Canvas(root, width=820, height=640, highlightthickness=0)
                    canvas.pack()
                    self.addCleanup(canvas.destroy)
                    photo = tk.PhotoImage(master=root, width=52, height=26)
                    font = ("Arial", 10)
                    env.update(tk=tk, root=root, canvas=canvas, ui_lang=[lang],
                               F=font, FS=("Arial", 9), FL=("Arial", 9), FB=("Arial", 10, "bold"),
                               CREAM="#ffffff", OUTLINE="#000000", LABEL="#ffffff", SECTION="#ffffff",
                               HINT="#ffffff", OUT8=(), I18N_WIDGETS=[], _seq=[0],
                               PARCH_HEX="#f7ebcf", PARCH=(247, 235, 207), PARCH_FOCUS=(247, 235, 207),
                               PARCH_FOCUS_HEX="#f7ebcf", PARCH_EDGE=(0, 0, 0, 255),
                               HONEY_EDGE=(0, 0, 0, 255), pill=lambda *a, **kw: (None, 0),
                               CHIP_STYLES={key: (None, None, "#ffffff", False)
                                            for key in ("normal", "selected")},
                               toggle_photos={"on": photo, "off": photo}, _set_cursor=Mock(),
                               measure=lambda text, f: tkfont.Font(root=root, font=f).measure(text))
                    extract([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                             and n.name in ("Managed", "Txt", "Chip", "Field", "Slider", "CanvasSwitch")], env)
                    extract([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                             and n.name in ("label", "flow")], env)
                    env.update(clock_time_var=tk.StringVar(root, "08:00"),
                               clock_step_var=tk.StringVar(root, "5"), clock_show_time=[True],
                               toggle_clock_show_time=Mock(), clock_step=Mock(),
                               field=lambda var: env["Field"](tk.Entry(root, textvariable=var)))
                    owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                 and n.name == "run_settings_window")
                    # Instantiate the production controls without importing settings or doing I/O.
                    for first, last in (("clock_sw", "clock_plus"), ("story_initial", "story_note"),
                                        ("cameo_sw", "cameo_lbl"), ("cf_l", "cx_sl")):
                        start = next(i for i, n in enumerate(owner.body) if isinstance(n, ast.Assign)
                                     and any(isinstance(t, ast.Name) and t.id == first for t in n.targets))
                        end = next(i for i, n in enumerate(owner.body) if isinstance(n, ast.Assign)
                                   and any(isinstance(t, ast.Name) and t.id == last for t in n.targets))
                        if first == "cf_l":
                            for key in ("freq", "lines", "interject", "ctx"):
                                env["cameo_" + key + "_var"] = tk.DoubleVar(root, 25)
                                env["_cameo_" + key] = Mock()
                        extract(owner.body[start:end + 1], env)
                    env["MANAGED"] = []  # Inspect full content coordinates before viewport clipping.
                    for key in ("clock_on", "story_on", "cameo_on"):
                        env[key][0] = True
                    env["lay_prompt"](28, 792, 150, 562)
                    root.update_idletasks()
                    snapshot = {name: canvas.bbox(getattr(env[name], "tag", None) or env[name].id)
                                for name in ("clock_time_l", "clock_step_l", "clock_show_lbl",
                                             "story_choices_lbl", "story_note", "cf_l", "cl_l", "ci_l", "cx_l")}
                    self.assertEqual(canvas.coords(env["clock_sw"].img_id)[0], 28)
                    self.assertEqual(canvas.coords(env["story_sw"].img_id)[0], 28)
                    self.assertEqual(canvas.coords(env["clock_show_sw"].img_id)[0], 52)
                    self.assertEqual(canvas.coords(env["story_choices_sw"].img_id)[0], 52)
                    for name, box in snapshot.items():
                        self.assertGreaterEqual(box[0], 51, name)
                        self.assertLessEqual(box[2], 773, name)
                    self.assertLess(snapshot["clock_time_l"][2], snapshot["clock_step_l"][0])
                    self.assertLess(env["clock_time_f"].geo[0] + 110, env["clock_step_f"].geo[0])
                    self.assertLessEqual(env["clock_plus"].x + env["clock_plus"].w, 772)
                    self.assertEqual(env["story_chips"][0][1].x, 52)
                    self.assertEqual(len({chip.y for _, chip in env["story_chips"]}), 1)
                    for prefix in ("cf", "cl", "ci", "cx"):
                        self.assertEqual(canvas.coords(env[prefix + "_l"].id)[0], 52)
                        self.assertEqual(env[prefix + "_sl"].x0 - 11, 52)
                        self.assertEqual(env[prefix + "_sl"].x1 + 11, 772)
                    expanded_max = env["immersion_scroll"][1]
                    env["immersion_scroll"][0] = expanded_max
                    before = (env["clock_time_var"].get(), env["clock_step_var"].get(),
                              env["clock_show_time"][:], env["story_choices"][:], env["story_intensity"][:])
                    for key in ("clock_on", "story_on", "cameo_on"):
                        env[key][0] = False
                    env["lay_prompt"](28, 792, 150, 562)
                    self.assertLess(env["immersion_scroll"][1], expanded_max)
                    self.assertEqual(env["immersion_scroll"][0], env["immersion_scroll"][1])
                    for name in ("clock_time_l", "clock_time_f", "clock_step_l", "clock_step_f",
                                 "clock_minus", "clock_plus", "clock_show_sw", "clock_show_lbl",
                                 "story_choices_sw", "story_choices_lbl", "story_note",
                                 "cf_l", "cf_val", "cf_sl", "cl_l", "cl_val", "cl_sl",
                                 "ci_l", "ci_val", "ci_sl", "cx_l", "cx_val", "cx_sl"):
                        self.assertFalse(env[name].visible, name)
                    self.assertTrue(all(not chip.visible for _, chip in env["story_chips"]))
                    self.assertEqual(before, (env["clock_time_var"].get(), env["clock_step_var"].get(),
                                             env["clock_show_time"], env["story_choices"], env["story_intensity"]))
                    env["config_loader"].save_config.assert_not_called()
                    env["_post"].assert_not_called()
                    canvas.destroy()

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
