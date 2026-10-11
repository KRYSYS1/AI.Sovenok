"""Offline native UI callbacks from both builds; no settings imports or real I/O."""
import ast
import copy
import types
import unittest
from unittest.mock import Mock

import test_i18n_new_settings as i18n_tests

SERVERS = i18n_tests.SERVERS
extract = i18n_tests.extract


class Widget:
    def __init__(self, text="", command=None, *args, **kwargs):
        self.src, self.command = text, command
        self.selected = False
        self.w, self.h, self.nat_w = 52, 26, 100
        self.geo = None

    def set_selected(self, value):
        self.selected = value

    def set_on(self, value):
        self.on = value

    def place(self, x, y, *args, **kwargs):
        self.geo = (x, y, args[0] if args else kwargs.get("width", 100),
                    args[1] if len(args) > 1 else 32)

    def bbox(self):
        x, y, w, h = self.geo
        return x, y, x + w, y + h

    def hide(self):
        self.geo = None


class StorySettingsTests(unittest.TestCase):
    def environment(self, server, value=None, lang="ru"):
        tree, env, _ = i18n_tests.SettingsI18nTests().environment(server)
        owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == "run_settings_window")
        start = next(i for i, n in enumerate(owner.body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "story_initial" for t in n.targets))
        end = next(i for i, n in enumerate(owner.body) if isinstance(n, ast.FunctionDef)
                   and n.name == "lay_clock")
        cfg = {} if value is None else {"story_events": copy.deepcopy(value)}
        env.update(cfg=cfg, ui_lang=[lang], CanvasSwitch=Widget, Txt=Widget, Chip=Widget,
                   F="font", FS="small", CREAM="cream", HINT="hint",
                   refresh_save_btn=Mock(), story_ready=[False], saved_state=[{}],
                   config_loader=Mock(), _post=Mock(), set_status=Mock(), layout=Mock())
        extract(owner.body[start:end], env)
        return tree, env

    def test_defaults_and_invalid_stored_values(self):
        for server in SERVERS:
            for value in (None, [], "bad", False, {}, {"enabled": "false", "intensity": []},
                          {"enabled": 1, "intensity": "invalid"}, {"intensity": {}}):
                with self.subTest(server=server, value=value):
                    _, env = self.environment(server, value)
                    self.assertEqual(env["story_on"], [False])
                    self.assertEqual(env["story_intensity"], ["low"])
                    self.assertEqual([c.selected for _, c in env["story_chips"]], [True, False, False])

    def test_callbacks_exclusive_and_deferred(self):
        for server in SERVERS:
            for lang in ("ru", "en"):
                tree, env = self.environment(server, {"enabled": True, "intensity": "high"}, lang)
                before = copy.deepcopy(env["cfg"])
                env["story_sw"].command()
                self.assertFalse(env["story_on"][0])
                for key, chip in env["story_chips"]:
                    chip.command()
                    self.assertEqual(env["story_intensity"][0], key)
                    self.assertEqual(sum(c.selected for _, c in env["story_chips"]), 1)
                    self.assertTrue(chip.selected)
                env["select_story_intensity"]("invalid")
                self.assertEqual(env["story_intensity"], ["low"])
                self.assertEqual(env["cfg"], before)
                env["config_loader"].save_config.assert_not_called()
                env["_post"].assert_not_called()

    def test_save_config_and_existing_reload_path(self):
        for server in SERVERS:
            tree, env = self.environment(server)
            save = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "save_all")
            # Execute actual story assignment and persistence/reload statements only.
            assignment = next(n for n in save.body if isinstance(n, ast.Assign)
                              and ast.unparse(n.targets[0]) == "cfg['story_events']")
            persist = next(n for n in ast.walk(save) if isinstance(n, ast.Expr)
                           and ast.unparse(n.value) == "config_loader.save_config()")
            reload = next(n for n in save.body if isinstance(n, ast.Try)
                          and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                                  and c.func.id == "_post" for c in ast.walk(n)))
            env["notify"] = True
            for enabled in (False, True):
                for intensity in ("low", "medium", "high"):
                    env["story_on"][0] = enabled
                    env["select_story_intensity"](intensity)
                    extract([assignment, persist, reload], env)
                    self.assertEqual(env["cfg"]["story_events"], dict(enabled=enabled, intensity=intensity))
                    env["_post"].assert_called_with("/reload")
            self.assertEqual(env["config_loader"].save_config.call_count, 6)

    def test_reset_respects_settings_selection(self):
        for server in SERVERS:
            tree, env = self.environment(server, {"enabled": True, "intensity": "high"})
            reset = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "reset_all")
            branch = next(n for n in reset.body if isinstance(n, ast.If)
                          and isinstance(n.test, ast.Name) and n.test.id == "want_settings")
            story_branch = copy.deepcopy(branch)
            story_branch.body = [n for n in story_branch.body if
                                 (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "story_on[0]") or
                                 (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                                  ast.unparse(n.value.func) in ("story_sw.set_on", "select_story_intensity"))]
            for selected in (False, True):
                env["want_settings"] = selected
                extract([story_branch], env)
                self.assertEqual(env["story_on"][0], not selected)
                self.assertEqual(env["story_intensity"][0], "low" if selected else "high")

    def test_bilingual_story_labels_and_wrapped_layout(self):
        for server in SERVERS:
            for lang in ("ru", "en"):
                _, env = self.environment(server, lang=lang)
                for name in ("story_lbl", "story_note"):
                    text = env["tr"](env[name].src)
                    self.assertEqual(any("\u0400" <= c <= "\u04ff" for c in text), lang == "ru")
                self.assertEqual([env["tr"](c.src) for _, c in env["story_chips"]],
                                 ["Occasional", "Moderate", "Frequent"] if lang == "en" else
                                 ["\u0420\u0435\u0434\u043a\u043e", "\u0423\u043c\u0435\u0440\u0435\u043d\u043d\u043e", "\u0410\u043a\u0442\u0438\u0432\u043d\u043e"])
                env["flow"] = lambda chips, x, y, width: y + 34 * len(chips)
                env["story_on"][0] = True
                for width in (744, 924, 1224):
                    end = env["lay_story"](28, 28 + width, 150)
                    self.assertEqual(env["story_note"].geo[2], width)
                    self.assertGreater(env["story_note"].geo[1], 150 + env["story_sw"].h)
                    self.assertGreater(end, env["story_note"].bbox()[3])

    def test_scroll_bounds_and_wheel_scope(self):
        for server in SERVERS:
            tree, env = self.environment(server)
            env.update(immersion_scroll=[0, 900, 400], cur_tab=[3], canvas=object(), immersion_bar=object())
            extract([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                     and n.name in ("scroll_immersion", "immersion_wheel")], env)
            for action, value, units, expected in (("moveto", "1", None, 900),
                    ("scroll", "-100", "units", 0), ("scroll", "1", "pages", 400)):
                env["scroll_immersion"](action, value, units)
                self.assertEqual(env["immersion_scroll"][0], expected)
            event = types.SimpleNamespace(widget=env["canvas"], delta=-120)
            self.assertEqual(env["immersion_wheel"](event), "break")
            env["cur_tab"][0] = 0
            self.assertIsNone(env["immersion_wheel"](event))

    def test_full_immersion_layout_scrolls_without_prompt_overlap(self):
        names = ("activity_sw activity_lbl auto_primary_sw auto_primary_lbl clock_sw clock_lbl clock_show_sw clock_show_lbl clock_time_l clock_time_f clock_step_l "
                  "clock_minus clock_step_f clock_plus cameo_sw cameo_lbl "
                  "cf_l cf_val cf_sl cl_l cl_val cl_sl ci_l ci_val ci_sl "
                 "cx_l cx_val cx_sl pr_sec pn_l pn_f persona_l persona_who persona_box pr_save").split()
        for server in SERVERS:
            for lang in ("ru", "en"):
                tree, env = self.environment(server, lang=lang)
                env.update({name: Widget() for name in names})
                env.update(H=34, LBL=20, ROW=70, MANAGED=[], PASS=[1], root=Mock(),
                            clock_on=[True], cameo_on=[True], story_on=[True],
                           canvas=Mock(), immersion_bar=Mock(), immersion_scroll=[0, 0, 1],
                           pr_chips=[Widget() for _ in range(15)], prompt_targets=[("player", "Name", True)],
                           prompt_idx=[0], result_txt={"prompt": Widget()},
                           measure=lambda text, font: len(text) * 8)
                def flow(chips, x, y, width):
                    cx = x
                    for chip in chips:
                        if cx + chip.nat_w > x + width:
                            cx, y = x, y + 44
                        chip.place(cx, y)
                        cx += chip.nat_w + 8
                    return y + 34
                env["flow"] = flow
                extract([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                         and n.name in ("lay_clock", "lay_prompt", "scroll_immersion")], env)
                for width, height in ((820, 640), (960, 740), (1280, 900)):
                    env["immersion_scroll"][0] = 0
                    bottom = height - 78
                    env["lay_prompt"](28, width - 28, 150, bottom)
                    self.assertGreater(env["immersion_scroll"][1], 0)
                    self.assertGreater(env["pr_save"].geo[1], env["persona_box"].geo[1])
                    self.assertGreaterEqual(env["persona_box"].geo[3], 140)
                    self.assertGreater(env["cl_l"].geo[1], env["cf_sl"].geo[1])
                    maximum = env["immersion_scroll"][1]
                    env["scroll_immersion"]("moveto", "1")
                    env["lay_prompt"](28, width - 28, 150, bottom)
                    self.assertEqual(env["immersion_scroll"][1], maximum)
                    self.assertLessEqual(env["pr_save"].geo[1] + 34, bottom)


if __name__ == "__main__":
    unittest.main()
