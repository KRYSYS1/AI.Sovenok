"""Offline clock regressions using the actual Python and label hooks in both clients."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import builtins
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from unittest.mock import Mock, patch

from test_cameo_clothing import ROOTS, StoreDict, StoreList, load


class GameClockTests(unittest.TestCase):
    def test_clock_badge_uses_expression_not_text_interpolation(self):
        for root in ROOTS:
            with self.subTest(root=root):
                with io.open(os.path.join(root, "es_ai_screens.rpy"), encoding="utf-8") as stream:
                    source = stream.read()
                self.assertNotIn("[es_ai_clock_text()]", source)
                match = re.search(r'^\s*text (es_ai_clock_text\(\)) size 18', source, re.M)
                self.assertIsNotNone(match)
                for value in ("23:00", "08:05", ""):
                    self.assertEqual(eval(match.group(1), {"es_ai_clock_text": lambda: value}), value)

    def settings_tree(self, root):
        path = (os.path.join(os.path.dirname(__file__), "settings_window.py")
                if root == ROOTS[0] else os.path.join(root, "server", "settings_window.py"))
        with io.open(path, encoding="utf-8-sig") as stream:
            return ast.parse(stream.read(), filename=path)

    def test_settings_clock_click_focus(self):
        class Entry:
            def __init__(self):
                self.selection_clear = Mock()

        class Text:
            pass

        for root in ROOTS:
            tree = self.settings_tree(root)
            handler = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                           and n.name == "_outside_click")
            owner = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                         and handler in n.body)
            binding = next(n for n in owner.body if isinstance(n, ast.Expr)
                           and isinstance(n.value, ast.Call)
                           and any(isinstance(a, ast.Name) and a.id == "_outside_click"
                                   for a in n.value.args))
            for field in ("time", "step"):
                for target in ("canvas", "button", "entry", "text", "model", "icon", "lookup"):
                    with self.subTest(root=root, field=field, target=target):
                        time_entry, step_entry, model_entry = Entry(), Entry(), Entry()
                        icon, lookup_icon, canvas, button = object(), object(), object(), object()
                        focused = time_entry if field == "time" else step_entry
                        window = Mock()
                        window.focus_get.return_value = focused
                        env = dict(root=window, tk=types.SimpleNamespace(Entry=Entry, Text=Text),
                                   clock_time_f=types.SimpleNamespace(widget=time_entry),
                                   clock_step_f=types.SimpleNamespace(widget=step_entry),
                                   mag_icon=icon, model_entry=model_entry, lookup_icons={lookup_icon},
                                   close_models=Mock(), close_lookup=Mock())
                        exec(compile(ast.Module(body=[handler, binding], type_ignores=[]),
                                     "settings-focus", "exec"), env)
                        window.bind.assert_called_once_with("<Button-1>", env["_outside_click"], add=True)
                        clicked = dict(canvas=canvas, button=button, entry=Entry(), text=Text(),
                                       model=model_entry, icon=icon, lookup=lookup_icon)[target]
                        env["_outside_click"](types.SimpleNamespace(widget=clicked))
                        if target in ("canvas", "button"):
                            window.focus_set.assert_called_once_with()
                            focused.selection_clear.assert_called_once_with()
                        else:
                            window.focus_set.assert_not_called()
                            focused.selection_clear.assert_not_called()
                        window.focus_set.reset_mock()
                        window.focus_get.return_value = model_entry
                        env["_outside_click"](types.SimpleNamespace(widget=canvas))
                        window.focus_set.assert_not_called()
                        window.focus_get.return_value = None
                        env["_outside_click"](types.SimpleNamespace(widget=canvas))
                        window.focus_set.assert_not_called()

    def test_settings_clock_validation_after_blur(self):
        for root in ROOTS:
            tree = self.settings_tree(root)
            nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                     and n.name in ("clock_values", "clock_step")]
            time_var, step_var = Mock(), Mock()
            env = dict(clock_time_var=time_var, clock_step_var=step_var, clock_on=[True], clock_show_time=[True],
                       clock_read_config=lambda: {"game_clock": {"revision": 3}}, set_status=Mock())
            exec(compile(ast.Module(body=nodes, type_ignores=[]), "settings-validation", "exec"), env)
            for time, step, valid in (("08:00", "5", True), ("23:59", "120", True),
                                      ("00:00", "0", True), ("24:00", "5", False),
                                      ("08:60", "5", False), ("0800", "5", False),
                                      ("08:00", "", False), ("08:00", "121", False),
                                      ("08:00", "1.5", False)):
                with self.subTest(root=root, time=time, step=step):
                    time_var.get.return_value, step_var.get.return_value = time, step
                    value = env["clock_values"](reset=True)
                    self.assertEqual(value is not None, valid)
                    step_var.set.reset_mock()
                    env["clock_step"](1)
                    if valid:
                        self.assertEqual(value["revision"], 4)
                        step_var.set.assert_called_once_with(str(min(120, int(step) + 1)))
                    else:
                        step_var.set.assert_not_called()

    def environment(self, root):
        # Each install must load its real source, not the previous install's
        # mocked config stream from another subtest.
        for mock_patch in getattr(self, "_clock_patches", []):
            mock_patch.stop()
        self._clock_patches = []

        def start_patch(mock_patch):
            mock_patch.start()
            self._clock_patches.append(mock_patch)
            self.addCleanup(mock_patch.stop)

        self.config = {"game_clock": dict(enabled=True, start_time="08:00",
                                           minutes_per_exchange=5, revision=0)}
        self.paths, self.draws, self.calls, self.requests = [], [], [], []
        renpy = types.SimpleNamespace(scene=lambda: self.draws.append("scene"),
            show=lambda bg: self.draws.append(bg), with_statement=lambda *a: None,
            restart_interaction=Mock(), pause=Mock(), transition=Mock(),
            has_image=lambda bg: bg in self.images)
        self.images = {"bg ext_square_day", "bg ext_square_sunset", "bg ext_square_night"}
        env = dict(dict=StoreDict, list=StoreList,
                   unicode=getattr(builtins, "unicode", str),
                   basestring=getattr(builtins, "basestring", str),
                   long=getattr(builtins, "long", int),
                   _es_ai_cameo_builtins=builtins, renpy=renpy, dissolve=None,
                   persistent=types.SimpleNamespace(es_ai_tts=False),
                   ES_AI_SERVER_DIR=root, es_ai_chat_active=[True],
                   es_ai_char_id="un", ES_AI_ROMANCEABLE=[],
                    es_ai_internal_speaking=[False], es_ai_log=lambda *a: None)
        env.update(es_ai_public_record=lambda *a: None, es_ai_public_snapshot=lambda: [])
        from test_cameo_clothing import install_delivery_say
        install_delivery_say(root, env)
        load(os.path.join(root, "es_ai_cameo.rpy"), env,
             {"es_ai_request_trace", "es_ai_party_context", "es_ai_cameo_clothing_request", "es_ai_clothing_cover_choice"})
        env["ES_AI_CHARS"] = [("un", "un", "")]
        load(os.path.join(root, "es_ai_api.rpy"), env,
             {"es_ai_story_ack_record", "es_ai_story_ack_snapshot", "ES_AI_STORY_ACKS"})
        load(os.path.join(root, "es_ai_locations.rpy"), env)
        env["ES_AI_FREE_SCENE"][0] = True
        env.update(es_ai_refresh_girls=lambda: self.calls.append("refresh"),
                   day_time=lambda: self.calls.append("day"),
                   sunset_time=lambda: self.calls.append("sunset"),
                   night_time=lambda: self.calls.append("night"))
        # Exercise the independent resolver without consulting real user files.
        start_patch(patch.dict(os.environ, {"LOCALAPPDATA": "stub-local-data"}))
        user_config = os.path.join("stub-local-data", "AI.Sovenok", "config.json")
        existing = os.path.exists
        def clock_env_exists(path, *a, **k):
            if path == user_config:
                return root == WORKSHOP_ROOT
            return existing(path, *a, **k)
        start_patch(patch.object(os.path, "exists", clock_env_exists))

        def config_open(path, *args, **kwargs):
            self.paths.append(path)
            return io.StringIO(json.dumps(self.config))

        start_patch(patch("io.open", config_open))
        start_patch(patch.dict(sys.modules, {"__builtin__": builtins}))
        return env

    def test_independent_clock_path_and_night_config(self):
        for root in ROOTS:
            with self.subTest(root=root):
                env = self.environment(root)
                self.assertNotIn("es_ai_user_config_path", env)
                user_path = os.path.join("stub-local-data", "AI.Sovenok", "config.json")
                with patch.object(os.path, "exists", lambda path: path == user_path):
                    self.assertEqual(env["es_ai_clock_config_path"](), user_path)
                    self.config["game_clock"].update(start_time="22:00", revision=8)
                    env["es_ai_clock_sync"]()
                    self.assertEqual(self.paths[-1], user_path)
                    self.assertEqual(env["es_ai_clock_snapshot"](),
                                     dict(enabled=True, time="22:00", phase="night"))
                    self.assertIn("bg ext_square_night", self.draws)
                with patch.object(os.path, "exists", return_value=False):
                    self.assertEqual(env["es_ai_clock_config_path"](),
                                     os.path.join(root, "config.json"))
                with patch.dict(os.environ, {"LOCALAPPDATA": ""}):
                    self.assertEqual(env["es_ai_clock_config_path"](),
                                     os.path.join(root, "config.json"))

    def test_clock_without_cameo_alias_and_with_bom(self):
        for root in ROOTS:
            env = self.environment(root)
            del env["_es_ai_cameo_builtins"]
            env.update(min="15", max="59")
            self.config["game_clock"].update(start_time="23:00", revision=9)
            text = "\ufeff" + json.dumps(self.config)
            with patch("io.open", side_effect=lambda *a, **k: io.StringIO(text)):
                env["es_ai_clock_sync"]()
            self.assertEqual(env["es_ai_clock_snapshot"](),
                             dict(enabled=True, time="23:00", phase="night"))
            self.assertIn("bg ext_square_night", self.draws)

    def test_bundled_python2_clock_codec_regression(self):
        executable = os.path.join(GAME_ROOT, "lib", "windows-x86_64", "python.exe")
        if not os.path.exists(executable):
            self.skipTest("Game's bundled Python 2 is not installed")
        names = {"es_ai_clock_config_path", "es_ai_clock_settings", "es_ai_clock_phase",
                 "es_ai_clock_sync", "es_ai_clock_snapshot", "es_ai_clock_begin",
                  "es_ai_clock_complete", "es_ai_clock_text"}
        with tempfile.TemporaryDirectory(prefix="esai-clock-") as directory:
            user_dir = os.path.join(directory, "AI.Sovenok")
            os.mkdir(user_dir)
            path = os.path.join(user_dir, "config.json")
            for bom in (False, True):
                with io.open(path, "w", encoding="utf-8") as stream:
                    stream.write(("\ufeff" if bom else "") + json.dumps({"game_clock": dict(
                        enabled=True, start_time="23:00", minutes_per_exchange=5, revision=9)}))
                for root in ROOTS:
                    with self.subTest(root=root, bom=bom):
                        with io.open(os.path.join(root, "es_ai_locations.rpy"), encoding="utf-8") as stream:
                            source = stream.read()
                        functions = []
                        for block in re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:]:
                            block = textwrap.dedent(block)
                            for node in ast.parse(block).body:
                                if isinstance(node, ast.FunctionDef) and node.name in names:
                                    functions.append(ast.get_source_segment(block, node))
                        script = "# -*- coding: utf-8 -*-\n" + "\n\n".join(functions) + '''
import codecs
assert __import__('sys').version_info[:2] == (2, 7)
try:
    codecs.lookup('utf-8-sig')
except LookupError:
    pass
else:
    raise AssertionError('Expected the bundled runtime without utf-8-sig')
class StoreDict(dict):
    pass
dict = StoreDict
min, max = '15', '59'
ES_AI_SERVER_DIR = 'unused-fallback'
ES_AI_CLOCK = dict(minutes=None, revision=None, enabled=False, lines=0, generation=0)
ES_AI_TIME = ['day']
def es_ai_apply_time_phase(phase, *args):
    ES_AI_TIME[0] = phase
assert '_es_ai_cameo_builtins' not in globals()
settings = es_ai_clock_sync()
assert settings == dict(enabled=True, show_time=True, start_time='23:00', minutes_per_exchange=5, revision=9), settings
assert es_ai_clock_snapshot() == dict(enabled=True, time='23:00', phase='night')
token = es_ai_clock_begin()
ES_AI_CLOCK['lines'] += 1
es_ai_clock_complete(0, token)
assert es_ai_clock_snapshot() == dict(enabled=True, time='23:05', phase='night')
ES_AI_CLOCK['show_time'] = False
assert es_ai_clock_text() == ''
print('Python 2 clock: 23:00 night -> 23:05 night')
'''
                        result = subprocess.run([executable, "-"], input=script.encode("utf-8"),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=dict(os.environ, LOCALAPPDATA=directory), timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                        self.assertIn(b"23:05 night", result.stdout)

    def test_night_snapshot_reaches_server_prompt(self):
        for root in ROOTS:
            env = self.environment(root)
            self.config["game_clock"].update(start_time="23:00", revision=9)
            env["es_ai_clock_sync"]()
            server_path = (os.path.join(os.path.dirname(__file__), "main.py")
                           if root == ROOTS[0] else os.path.join(root, "server", "main.py"))
            server = dict(re=re)
            # Read the real server before the client's config-open mock applies.
            with patch("io.open", builtins.open):
                load(server_path, server, {"clock_prompt", "game_clock_valid"}, rpy=False)
            prompt = server["clock_prompt"](env["es_ai_clock_snapshot"]())
            self.assertIn("AUTHORITATIVE CURRENT GAME CLOCK", prompt)
            self.assertIn("Time: 23:00. Phase: night.", prompt)
            self.assertEqual(server["clock_prompt"](dict(enabled=False)), "")

    def test_display_only_toggle_preserves_progression_and_phase(self):
        for root in ROOTS:
            server_path = (os.path.join(os.path.dirname(__file__), "main.py")
                           if root == ROOTS[0] else os.path.join(root, "server", "main.py"))
            server = dict(re=re)
            with patch("io.open", builtins.open):
                load(server_path, server, {"clock_prompt", "game_clock_valid"}, rpy=False)
            env = self.environment(root)
            self.config["game_clock"].update(start_time="21:58", revision=7)
            token = env["es_ai_clock_begin"]()
            self.assertEqual(env["es_ai_clock_text"](), "21:58")
            self.config["game_clock"]["show_time"] = False
            env["es_ai_clock_sync"]()
            self.assertEqual(env["es_ai_clock_text"](), "")
            self.assertEqual(env["es_ai_clock_begin"](), token)
            env["ES_AI_CLOCK"]["lines"] += 1
            env["es_ai_clock_complete"](0, token)
            snapshot = env["es_ai_clock_snapshot"]()
            self.assertEqual(snapshot, dict(enabled=True, time="22:03", phase="night"))
            self.assertIn("Time: 22:03. Phase: night.", server["clock_prompt"](snapshot))
            self.assertIn("bg ext_square_night", self.draws)
            self.assertEqual(env["ES_AI_CLOCK"]["revision"], 7)
            self.config["game_clock"]["show_time"] = True
            env["es_ai_clock_sync"]()
            self.assertEqual(env["es_ai_clock_text"](), "22:03")
            for invalid in (None, 0, 1, "false", [], {}):
                self.config["game_clock"]["show_time"] = invalid
                self.assertIs(env["es_ai_clock_settings"]()["show_time"], True)

    def test_server_display_flag_strict_validation_and_persistence(self):
        for root in ROOTS:
            path = (os.path.join(os.path.dirname(__file__), "main.py")
                    if root == ROOTS[0] else os.path.join(root, "server", "main.py"))
            env = dict(re=re, cfg={"game_clock": {"enabled": True, "revision": 7}},
                       config_loader=types.SimpleNamespace(save_config=Mock()))
            with patch("io.open", builtins.open):
                load(path, env, {"game_clock_valid", "game_clock_settings", "config_set"}, rpy=False)
                with io.open(path, encoding="utf-8-sig") as stream:
                    tree = ast.parse(stream.read())
            whitelist = next(n for n in tree.body if isinstance(n, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == "_CFG_SECTIONS" for t in n.targets))
            exec(compile(ast.Module(body=[whitelist], type_ignores=[]), path, "exec"), env)
            self.assertIs(env["game_clock_settings"](None)["show_time"], True)
            for value in (False, True):
                result = env["config_set"](dict(section="game_clock", key="show_time", value=value))
                self.assertTrue(result["ok"])
                self.assertIs(env["cfg"]["game_clock"]["show_time"], value)
                self.assertEqual(env["cfg"]["game_clock"]["revision"], 7)
            env["config_loader"].save_config.assert_has_calls([unittest.mock.call(), unittest.mock.call()])
            for invalid in (None, 0, 1, "false", [], {}):
                result = env["config_set"](dict(section="game_clock", key="show_time", value=invalid))
                self.assertFalse(result["ok"])
                self.assertIs(env["game_clock_settings"]({"show_time": invalid})["show_time"], True)
            self.assertEqual(env["config_loader"].save_config.call_count, 2)

    def test_config_revision_pause_and_rollover(self):
        for root in ROOTS:
            with self.subTest(root=root):
                e = self.environment(root)
                sync, snapshot = e["es_ai_clock_sync"], e["es_ai_clock_snapshot"]
                sync(redraw=False)
                self.assertIs(type(e["ES_AI_CLOCK"]), StoreDict)
                self.assertEqual(snapshot(), dict(enabled=True, time="08:00", phase="morning"))
                self.assertEqual(self.paths[-1], os.path.join("stub-local-data", "AI.Sovenok", "config.json") if root == WORKSHOP_ROOT
                                  else os.path.join(root, "config.json"))
                self.assertEqual(e["persistent"].sprite_time, "day")
                self.assertFalse(self.draws)
                token = e["es_ai_clock_begin"]()
                e["ES_AI_CLOCK"]["lines"] += 3
                e["es_ai_clock_complete"](0, token)
                self.assertEqual(snapshot()["time"], "08:05")
                self.assertFalse(self.draws)
                self.config["game_clock"].update(start_time="23:58")
                sync()
                self.assertEqual(snapshot()["time"], "08:05")
                self.config["game_clock"]["enabled"] = False
                sync()
                e["es_ai_set_time"]("ночь")
                e["es_ai_clock_complete"](0, token)
                self.assertEqual(snapshot()["time"], "08:05")
                self.assertEqual(e["es_ai_clock_text"](), "")
                self.config["game_clock"]["enabled"] = True
                sync()
                self.assertEqual(snapshot()["time"], "08:05")
                self.config["game_clock"]["revision"] = 1
                sync()
                self.assertEqual(snapshot()["time"], "23:58")
                before = e["ES_AI_CLOCK"]["lines"]
                token = e["es_ai_clock_begin"]()
                e["ES_AI_CLOCK"]["lines"] += 1
                e["es_ai_clock_complete"](before, token)
                self.assertEqual(snapshot()["time"], "00:03")
                self.config["game_clock"]["minutes_per_exchange"] = 0
                e["es_ai_clock_complete"](before, token)
                self.assertEqual(snapshot()["time"], "00:03")
                patch.stopall()

    def test_invalid_config_and_legacy(self):
        for root in ROOTS:
            e = self.environment(root)
            for invalid in (None, [], "bad", {"game_clock": []},
                            {"game_clock": dict(enabled="false", start_time="99:90",
                             minutes_per_exchange="bad", revision=True)}):
                self.config = invalid
                self.assertEqual(e["es_ai_clock_settings"](),
                    dict(enabled=False, show_time=True, start_time="08:00", minutes_per_exchange=5, revision=0))
            self.config = {"game_clock": dict(minutes_per_exchange=900, revision=-5, start_time="6:05")}
            self.assertEqual(e["es_ai_clock_settings"]()["minutes_per_exchange"], 120)
            self.assertEqual(e["es_ai_clock_settings"]()["revision"], 0)
            for value, phase in ((" УТРО ", "morning"), ("day", "day"), ("вечер", "sunset"),
                                 ("ночь", "night"), ("evening", "sunset"), ("день", "day")):
                # Emulate Python 2's str(unicode) failure at the action boundary.
                def ascii_str(value):
                    return str(value).encode("ascii").decode("ascii")
                e["str"] = ascii_str
                e["es_ai_apply_actions"]({"time": value})
                self.assertEqual(e["ES_AI_TIME"][0], phase)
            self.config = {"game_clock": {"enabled": True}}
            e["es_ai_clock_sync"]()
            e["es_ai_apply_actions"]({"time": "night"})
            self.assertEqual(e["ES_AI_TIME"][0], "morning")
            patch.stopall()

    def test_phases_preserve_scene_and_asset_fallbacks(self):
        for root in ROOTS:
            e = self.environment(root)
            e.update(ES_AI_CAMEO_NEARBY={"square": [{"id": "sh"}]},
                     ES_AI_CAMEO_ACTIVE=[{"id": "dv", "turns": 3}],
                     ES_AI_RECENT_LINES=["context"])
            e["ES_AI_SHOWN"][:] = [{"id": "un"}, {"id": "dv", "cameo": True}]
            e["ES_AI_GIRL_LAYOUT"][:] = ["stable", {"dv": 0.5}]
            keys = ("ES_AI_SHOWN", "ES_AI_CAMEO_NEARBY", "ES_AI_CAMEO_ACTIVE",
                    "ES_AI_RECENT_LINES", "ES_AI_LOC_CUR", "ES_AI_GIRL_LAYOUT", "ES_AI_DRESS")
            saved = {k: copy.deepcopy(e[k]) for k in keys}
            for time, phase in ((359, "night"), (360, "morning"), (599, "morning"),
                                (600, "day"), (1079, "day"), (1080, "sunset"),
                                (1319, "sunset"), (1320, "night"), (1440, "night")):
                self.assertEqual(e["es_ai_clock_phase"](time), phase)
                e["es_ai_apply_time_phase"](phase)
                self.assertEqual({k: e[k] for k in keys}, saved)
            self.images = {"bg ext_square_day"}
            e["es_ai_apply_time_phase"]("sunset")
            self.assertEqual(e["es_ai_loc_bg"](e["es_ai_location"]()), "bg ext_square_day")
            e["ES_AI_TIME"][0] = "morning"
            self.assertEqual(e["es_ai_loc_bg"](e["es_ai_location"]()), "bg ext_square_day")
            for loc_id in ("houses", "camp_gate", "bus_inside"):
                e["ES_AI_TIME"][0] = "sunset"
                loc = e["ES_AI_LOCATION_INDEX"][loc_id]
                self.images = set(loc["time_bgs"]["sunset"])
                self.assertEqual(e["es_ai_loc_bg"](loc), loc["time_bgs"]["sunset"][0])
            for loc_id, assets, expected in (
                    ("camp_gate", ("ext_camp_entrance_day", "ext_camp_entrance_night"), "ext_camp_entrance_night"),
                    ("library", ("int_library_day", "ext_library_night"), "int_library_day"),
                    ("library", ("int_library_day", "int_library_night", "ext_library_sunset"), "int_library_night"),
                    ("library_ext", ("ext_library_day", "ext_library_night", "int_library_night"), "ext_library_night"),
                    ("library_ext", ("ext_library_day", "int_library_night"), "ext_library_day"),
                    ("boathouse", ("ext_boathouse_day", "ext_boathouse_night"), "ext_boathouse_night"),
                    ("aidpost", ("ext_aidpost_day", "ext_aidpost_night"), "ext_aidpost_night"),
                    ("club_room", ("int_clubs_male_day", "int_clubs_male2_night"), "int_clubs_male2_night"),
                    ("club_room", ("int_clubs_male_day", "int_clubs_male_sunset", "int_clubs_male2_night"), "int_clubs_male_sunset"),
                    ("square", ("ext_square_day", "ext_square_sunset", "ext_square_night"), "ext_square_sunset"),
                    ("square", ("ext_square_day",), "ext_square_day"),
                    ("stage_big", ("ext_stage_normal_day", "ext_stage_big_night"), "ext_stage_big_night"),
                    ("stage_big", ("ext_stage_big_night",), "ext_stage_big_night"),
                    ("stage_big", ("ext_stage_normal_day",), "ext_stage_normal_day"),
                    ("camp_gate", ("ext_camp_entrance_day", "ext_no_bus_night"), "ext_camp_entrance_day")):
                with self.subTest(root=root, location=loc_id, assets=assets):
                    self.images = {"bg " + bg for bg in assets}
                    e["ES_AI_TIME"][0] = "sunset"
                    self.assertEqual(e["es_ai_loc_bg"](e["ES_AI_LOCATION_INDEX"][loc_id]), "bg " + expected)
            # Timeless overrides remain fallbacks, not substitutes for real sunset/night.
            loc = {"bgs": ["bg custom_day"], "time_bgs": {
                "sunset": ["bg custom_timeless", "bg custom_day", "bg custom_sunset"],
                "night": ["bg custom_special_night"]}}
            for assets, expected in (
                    (("custom_timeless", "custom_day"), "custom_timeless"),
                    (("custom_timeless", "custom_day", "custom_special_night"), "custom_special_night"),
                    (("custom_day", "custom_night", "custom_special_night"), "custom_special_night"),
                    (("custom_timeless", "custom_special_night", "custom_sunset"), "custom_sunset"),
                    (("custom_day",), "custom_day"),
                    ((), "custom_day")):
                with self.subTest(root=root, assets=assets):
                    self.images = {"bg " + bg for bg in assets}
                    self.assertEqual(e["es_ai_loc_bg"](loc), "bg " + expected)
            self.images = {"bg only_night"}
            self.assertEqual(e["es_ai_loc_bg"]({"bgs": ["bg only_night"]}), "bg only_night")
            self.images = {"bg ext_stage_normal_day", "bg ext_stage_big_night"}
            for phase, expected in (("morning", "ext_stage_normal_day"),
                                    ("day", "ext_stage_normal_day"),
                                    ("night", "ext_stage_big_night")):
                e["ES_AI_TIME"][0] = phase
                self.assertEqual(e["es_ai_loc_bg"](e["ES_AI_LOCATION_INDEX"]["stage_big"]), "bg " + expected)
            patch.stopall()

    def test_request_snapshots_and_fresh_revisions(self):
        for root in ROOTS:
            # Load before installing the in-memory config reader.
            api, cameo = {}, {}
            load(os.path.join(root, "es_ai_api.rpy"), api,
                 {"es_ai_chat_async", "es_ai_initiative_async", "es_ai_say_girl"})
            load(os.path.join(root, "es_ai_cameo.rpy"), cameo,
                 {"es_ai_cameo_line", "es_ai_cameo_speak"})
            e = self.environment(root)
            for name, fn in dict(api, **cameo).items():
                if callable(fn):
                    e[name] = types.FunctionType(fn.__code__, e, name, fn.__defaults__)
            e.update(es_ai_location_context=lambda: "square", es_ai_scene_snapshot=lambda cid: {},
                     ES_AI_STORY_INPUT=dict(pending=None, selection=None, choice=None),
                     ES_AI_CAMEO_PLAYER_TEXT=[""],
                     es_ai_cameo_name=lambda cid: cid, es_ai_recent_snapshot=lambda n: [],
                     es_ai_girl_enter=lambda *a: None, es_ai_sanitize_text=lambda s: s,
                     es_ai_speakers={"un": lambda s: None, "dv": lambda s: None})

            def http(path, payload):
                self.requests.append((path, payload))
                return {"ok": True, "reply": "Hi"}

            e["es_ai_http"] = http
            e["es_ai_run_async"] = lambda kind, fn: types.SimpleNamespace(done=True, error=None, result=fn())
            for call in (lambda: e["es_ai_chat_async"]("un", "hi"),
                         lambda: e["es_ai_initiative_async"]("un"),
                         lambda: e["es_ai_cameo_line"]("dv", "un", False)):
                call()
                self.assertEqual(self.requests[-1][1]["clock"]["time"], "08:00")
            self.config["game_clock"].update(revision=1, start_time="21:59")
            job = e["es_ai_chat_async"]("un", "hi")
            self.assertEqual(self.requests[-1][1]["clock"],
                             dict(enabled=True, time="21:59", phase="sunset"))
            before = e["ES_AI_CLOCK"]["lines"]
            e["es_ai_say_girl"]("un", "  ")
            e["es_ai_cameo_speak"]("dv", "")
            self.assertEqual(e["ES_AI_CLOCK"]["lines"], before)
            e["es_ai_say_girl"]("un", "Hi")
            e["es_ai_cameo_speak"]("dv", "Hi")
            e["es_ai_clock_complete"](before, job.result["_clock_revision"])
            self.assertEqual(e["es_ai_clock_snapshot"]()["time"], "22:04")
            for endpoint in ("es_ai_chat_async", "es_ai_initiative_async"):
                for change, cameo_sync in (("revision", False), ("revision", True),
                                           ("enable", False), ("toggle", True)):
                    self.config["game_clock"].update(enabled=True)
                    e["es_ai_clock_sync"]()
                    before = e["ES_AI_CLOCK"]["lines"]

                    def waiting_http(path, payload):
                        self.assertNotIn("_clock_revision", payload)
                        if change == "revision":
                            self.config["game_clock"]["revision"] += 1
                            self.config["game_clock"]["start_time"] = "12:00"
                        else:
                            self.config["game_clock"]["enabled"] = False
                            if change == "toggle":
                                e["es_ai_clock_sync"]()
                                self.config["game_clock"]["enabled"] = True
                        return {"ok": True, "reply": "Hi"}

                    e["es_ai_http"] = waiting_http
                    job = (e[endpoint]("un", "hi") if endpoint == "es_ai_chat_async"
                           else e[endpoint]("un"))
                    token = job.result["_clock_revision"]
                    e["es_ai_http"] = http
                    if cameo_sync:
                        e["es_ai_cameo_line"]("dv", "un", False)
                        self.assertEqual(job.result["_clock_revision"], token)
                    e["ES_AI_CLOCK"]["lines"] += 2
                    previous_minutes = e["ES_AI_CLOCK"]["minutes"]
                    e["es_ai_clock_complete"](before, token)
                    expected = 720 if change == "revision" else previous_minutes
                    self.assertEqual(e["ES_AI_CLOCK"]["minutes"], expected)
                    # A new request can advance normally after the reset/toggle.
                    self.config["game_clock"]["enabled"] = True
                    fresh = e["es_ai_chat_async"]("un", "hi")
                    before = e["ES_AI_CLOCK"]["lines"]
                    e["ES_AI_CLOCK"]["lines"] += 1
                    e["es_ai_clock_complete"](before, fresh.result["_clock_revision"])
                    self.assertEqual(e["ES_AI_CLOCK"]["minutes"], (expected + 5) % 1440)
            patch.stopall()

    def test_label_completion_hooks(self):
        for root in ROOTS:
            with io.open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read()
            greeting = source.split("label es_ai_pick:")[1].split("label es_ai_settings_loop:")[0]
            self.assertNotIn("es_ai_clock_complete", greeting)
            self.assertLess(source.index("es_ai_clock_sync(redraw=False"), source.index('es_ai_set_location("square")'))
            blocks = [source.split("    $ _clock_lines = ES_AI_CLOCK")[1].split("    jump es_ai_chat_input")[0],
                      source.split("label es_ai_chat_initiative:")[1].split("    jump es_ai_chat_input")[0]]
            blocks[0] = '    $ _clock_lines = ES_AI_CLOCK' + blocks[0]
            blocks[1] = blocks[1].split("    if _ini is None:")[1].split("    else:", 1)[1]
            for i, block in enumerate(blocks):
                self.assertEqual(block.count("es_ai_clock_complete"), 1)
                code = textwrap.dedent(re.sub(r"(?m)^(\s*)\$ ", r"\1", block))
                code = re.sub(r"(?m)^(\s*)jump es_ai_pick$", r"\1raise AssertionError('unexpected detach')", code)
                for suppress, main, cameo, expected in ((False, "Hi", True, 5),
                        (True, "", True, 5), (False, "", False, 0)):
                    e = self.environment(root)
                    e["es_ai_clock_sync"](redraw=False)
                    result = dict(reply=main, suppress_main_reply=suppress,
                                  _clock_revision=e["es_ai_clock_begin"]())
                    e.update(_res=result, _ini=result, _inp="hi", es_ai_char_id="un",
                             es_ai_delivery_flush=lambda: None,
                             es_ai_char_name=lambda cid: cid,
                             es_ai_apply_actions=lambda *a: None)

                    def say(*args, **kwargs):
                        if args[1].strip():
                            e["ES_AI_CLOCK"]["lines"] += 1

                    def cameos(*args):
                        if cameo:
                            e["ES_AI_CLOCK"]["lines"] += 3

                    e.update(es_ai_say_girl=say, es_ai_try_cameo=cameos, es_ai_story_choices_menu=lambda: None)
                    exec(compile(code, "reply-label", "exec"), e)
                    self.assertEqual(e["ES_AI_CLOCK"]["minutes"], 480 + expected)
                    patch.stopall()

    def test_failures_and_greeting_do_not_advance(self):
        for root in ROOTS:
            api = {}
            load(os.path.join(root, "es_ai_api.rpy"), api,
                 {"es_ai_chat_async", "es_ai_initiative_async", "es_ai_ask_girl",
                  "es_ai_initiative_girl", "es_ai_say_girl"})
            e = self.environment(root)
            for name, fn in api.items():
                if callable(fn):
                    e[name] = types.FunctionType(fn.__code__, e, name, fn.__defaults__)
            e.update(es_ai_location_context=lambda: "square", es_ai_scene_snapshot=lambda cid: {},
                     ES_AI_STORY_INPUT=dict(pending=None, selection=None, choice=None),
                     es_ai_context_snapshot=lambda: [], set_es_ai_error=lambda *a: None,
                     es_ai_girl_enter=lambda *a: None, es_ai_sanitize_text=lambda s: s,
                     es_ai_speakers={"un": lambda s: None})

            def run(kind, fn):
                try:
                    return types.SimpleNamespace(done=True, result=fn(), error=None)
                except Exception as ex:
                    return types.SimpleNamespace(done=True, result=None, error=str(ex))

            e["es_ai_run_async"] = run
            for response in ({"ok": False, "error": "offline"}, {"ok": True, "reply": ""}):
                e["es_ai_http"] = lambda *a: response
                before = e["ES_AI_CLOCK"]["lines"]
                for call in (lambda: e["es_ai_ask_girl"]("un", "hi"),
                             lambda: e["es_ai_initiative_girl"]("un")):
                    result = call()
                    if response["ok"]:
                        e["es_ai_say_girl"]("un", result["reply"])
                        e["es_ai_clock_complete"](before, result["_clock_revision"])
                    else:
                        self.assertIsNone(result)
                    self.assertEqual(e["ES_AI_CLOCK"]["minutes"], 480)
            e["es_ai_http"] = lambda *a: {"ok": True, "reply": "Greeting"}
            greeting = e["es_ai_initiative_girl"]("un")
            e["es_ai_say_girl"]("un", greeting["reply"])
            self.assertEqual(e["ES_AI_CLOCK"]["minutes"], 480)
            patch.stopall()


if __name__ == "__main__":
    unittest.main()
