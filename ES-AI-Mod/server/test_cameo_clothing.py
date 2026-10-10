"""Offline cameo clothing checks for both installs and Python 2 Ren'Py stores."""
import ast
import io
import os
import pickle
import random
import re
import sys
import textwrap
import types
import unittest
import zlib
from unittest.mock import patch
try:
    import __builtin__ as builtins
except ImportError:
    import builtins

DEV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSHOP = r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310"
ROOTS = (os.path.join(DEV, "mod"), WORKSHOP)


class StoreDict(dict):
    pass


class StoreList(list):
    pass


class Stub(object):
    pass


def load(path, env, names=None, rpy=True):
    with io.open(path, encoding="utf-8-sig") as stream:
        source = stream.read()
    blocks = re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:] if rpy else [source]
    nodes = []
    for block in blocks:
        if rpy:
            block = "\n".join(line for line in block.splitlines()
                              if not line.strip() or line.startswith((" ", "\t")))
        for node in ast.parse(textwrap.dedent(block)).body:
            if isinstance(node, ast.FunctionDef) and (names is None or node.name in names):
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    (t.id.startswith(("_ACTION_", "_DRESS_", "_EMOTION_")) or
                     (t.id.startswith("ES_AI_") and (names is None or t.id in {
                         "ES_AI_EMOTIONS", "ES_AI_EMOTION_RU", "ES_AI_DRESSES"}))) for t in node.targets):
                nodes.append(node)
    module = ast.Module(body=nodes, type_ignores=[]) if sys.version_info[0] >= 3 else ast.Module(body=nodes)
    eval(compile(module, path, "exec"), env)


class ClothingTests(unittest.TestCase):
    def environment(self, root):
        persistent = Stub()
        persistent.es_ai_tts = False
        renpy = Stub()
        renpy.with_statement = lambda *a: None
        renpy.hide = lambda *a: None
        env = {"_es_ai_cameo_builtins": builtins, "_es_random": random.Random(7),
               "dict": StoreDict, "list": StoreList, "persistent": persistent,
               "renpy": renpy, "dissolve": None,
               "basestring": getattr(builtins, "basestring", str),
               "unicode": getattr(builtins, "unicode", str), "long": getattr(builtins, "long", int)}
        load(os.path.join(root, "es_ai_cameo.rpy"), env)
        env["ES_AI_LOCATION_INDEX"] = dict.fromkeys(list(env["ES_AI_CAMEO_BY_LOC"]) + ["bus_stop"], {})
        env.update(ES_AI_SHOWN=[{"id": "sl"}], ES_AI_LOC_CUR=["beach"],
                   ES_AI_LOC_LAST_CHAR=["sl"], es_ai_chat_active=[True],
                   ES_AI_CHARS=[(c, c, "") for c in ("sl", "dv", "us", "el", "sh")],
                   ES_AI_ROMANCEABLE=["sl", "dv"], ES_AI_DRESS=["swim"],
                    ES_AI_TIME=["night"], ES_AI_CLOCK=dict(enabled=False, lines=0),
                    es_ai_location=lambda: {"dress": "swim"},
                   es_ai_refresh_girls=lambda: None, es_ai_sanitize_text=lambda s: s,
                   es_ai_internal_speaking=[False],
                   es_ai_speakers={c: lambda s: None for c in ("dv", "us", "el", "sh")},
                   es_ai_log=lambda s: None, es_ai_cameo_on=lambda: True,
                   es_ai_set_dress=lambda *a: None)
        settings = dict(env["ES_AI_CAMEO_DEFAULTS"])
        settings.update(cameo_freq=100, cameo_interject=100, cameo_stay_lines=4)
        env["es_ai_read_cameo_settings"] = lambda: settings
        return env

    def test_defaults_and_overrides(self):
        for root in ROOTS:
            env = self.environment(root)
            enter, speak = env["es_ai_cameo_enter"], env["es_ai_cameo_speak"]
            for cid in ("dv", "us"):
                enter(cid, "surprise")
                g = next(g for g in env["ES_AI_SHOWN"] if g["id"] == cid)
                self.assertEqual(g["dress"], "swim")
                speak(cid, "Hi", "laugh")
                self.assertEqual(g["dress"], "swim")
                speak(cid, "Hi", dress=" COVER ")
                self.assertEqual(g["dress"], "pioneer")
                speak(cid, "Hi", "smile")
                enter(cid, "normal")
                self.assertEqual(g["dress"], "pioneer")
                speak(cid, "Hi", "smile", {"swim": True})
                self.assertEqual(g["dress"], "pioneer")
                speak(cid, "Hi", dress="sport")
                self.assertEqual(g["dress"], "sport")
            env["ES_AI_SHOWN"][:] = []
            env["es_ai_location"] = lambda: {"romantic": True}
            enter("us", "smile")
            self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])
            enter("us", "normal", dress="swim")
            self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "swim")

    def test_all_delivery_paths(self):
        for root in ROOTS:
            for path in ("arrive", "explicit", "random", "tick"):
                env = self.environment(root)
                delivered = []
                def line(cid, *a, **k):
                    delivered.append(cid)
                    return {"reply": "Hi", "emotion": "smile", "dress": "cover"}
                env["es_ai_cameo_line"] = line
                env["es_ai_maybe_cameo"] = lambda *a, **k: ["dv", "us"]
                env["es_ai_is_romantic_moment"] = lambda *a: False
                if path == "arrive":
                    env["es_ai_cameo_on_arrive"]()
                elif path == "tick":
                    env["es_ai_cameo_enter"]("dv", "normal", True, 4)
                    env["es_ai_cameo_enter"]("us", "normal", True, 4)
                    env["es_ai_cameo_tick"]("sl")  # Newly entered NPCs skip this exchange.
                    env["es_ai_cameo_tick"]("sl")
                else:
                    env["es_ai_cameo_tick"] = lambda *a: None
                    env["es_ai_try_cameo"]("sl", "Hi", {"cameo": ["dv", "us"]} if path == "explicit" else {})
                self.assertTrue(delivered, (root, path))
                for g in env["ES_AI_SHOWN"]:
                    if g.get("cameo"):
                        self.assertEqual(g["dress"], "pioneer" if g["id"] in delivered else "swim")
                # Existing direct-address NPCs must consume dress, not be re-entered.
                env["es_ai_cameo_line"] = lambda *a, **k: {"reply": "Hi", "dress": "swim"}
                for cid in ("dv", "us"):
                    env["es_ai_try_cameo"]("sl", "Hi", {"cameo": [cid]})
                self.assertEqual([g["dress"] for g in env["ES_AI_SHOWN"] if g.get("cameo")],
                                 ["swim", "swim"])

    def test_travel_preserves_company_and_resets_only_destination_dress(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai_locations.rpy"), env)
            env["renpy"].scene = lambda: None
            env["renpy"].show = lambda *a: None
            env["es_ai_refresh_girls"] = lambda: None
            env["es_ai_loc_bg"] = lambda loc: "bg"
            env["es_ai_cameo_on_arrive"] = lambda: None
            env["ES_AI_SHOWN"][:] = [{"id": "sl", "emo": "normal"}] + [
                {"id": cid, "emo": "smile", "cameo": True, "dress": "pioneer"}
                for cid in ("dv", "us", "el", "sh", "mi", "un")]
            env["ES_AI_CAMEO_ACTIVE"][:] = [{"id": g["id"], "turns": 8, "skip_tick": True}
                                           for g in env["ES_AI_SHOWN"][1:]]
            before = [dict(a) for a in env["ES_AI_CAMEO_ACTIVE"]]
            env["ES_AI_CAMEO_CD"][0] = 4
            env["ES_AI_RECENT_LINES"][:] = [{"who": "old", "what": "old beach dialogue"}]
            for destination, dress in (("beach", "swim"), ("mt_room", None),
                                       ("playground", "sport"), ("square", None)):
                env["es_ai_set_location"](destination, travel_all=True)
                self.assertEqual(len(env["ES_AI_SHOWN"]), 7)
                self.assertEqual(env["ES_AI_CAMEO_ACTIVE"], before)
                self.assertEqual(env["ES_AI_CAMEO_CD"], [4])
                self.assertTrue(all(g["dress"] == dress for g in env["ES_AI_SHOWN"][1:]))
                self.assertEqual(len(env["ES_AI_RECENT_LINES"]), 1)
                self.assertIn("company moved together", env["ES_AI_RECENT_LINES"][0]["what"])
                snapshot = env["es_ai_scene_snapshot"]("sl")
                self.assertEqual(snapshot["capacity"], 0)
                self.assertEqual(snapshot["destination_capacity"]["mt_room"], 2)
                self.assertEqual(set(snapshot["traveling"]), {g["id"] for g in env["ES_AI_SHOWN"][1:]})
                self.assertTrue(all(not set(ids) & set(snapshot["traveling"])
                                    for ids in snapshot["destinations"].values()))
            env["es_ai_girls_reset"]()
            env["es_ai_set_location"]("beach")
            self.assertEqual(env["ES_AI_SHOWN"], [])
            self.assertEqual(env["ES_AI_CAMEO_ACTIVE"], [])
            self.assertEqual(env["ES_AI_RECENT_LINES"], [])

    def test_no_random_departure_and_legacy_budget_is_ignored(self):
        for root in ROOTS:
            env = self.environment(root)
            env["es_ai_read_cameo_settings"]()["cameo_interject"] = 0
            for cid in ("dv", "us", "el", "sh"):
                env["es_ai_cameo_enter"](cid, "normal", True, 1)
            # Old saves have no dwell counter. An exhausted budget must not evict them.
            env["ES_AI_CAMEO_ACTIVE"][:] = [{"id": a["id"], "lines_left": 0}
                                           for a in env["ES_AI_CAMEO_ACTIVE"]]
            rng = env["_es_random"]
            with patch.object(rng, "random", return_value=0.0) as draw:
                for _ in range(100):
                    env["es_ai_cameo_tick"]("sl")
                draw.assert_not_called()
                self.assertEqual(len(env["ES_AI_CAMEO_ACTIVE"]), 4)
            for a in env["ES_AI_CAMEO_ACTIVE"]:
                a["skip_tick"] = True
            with patch.object(rng, "random", return_value=0.0) as draw:
                env["es_ai_cameo_tick"]("sl")
                draw.assert_not_called()

    def test_explicit_farewells_precede_random_actions_and_never_summon_absent_npcs(self):
        for root in ROOTS:
            for leaving in (["dv"], ["dv", "us", "el", "sh"], ["mi"]):
                env = self.environment(root)
                for cid in ("dv", "us", "el", "sh"):
                    env["es_ai_cameo_enter"](cid, "normal", True, 1)
                delivered = []
                def line(cid, *args, **kwargs):
                    self.assertEqual(kwargs["mode"], "leave")
                    self.assertIn(cid, [g["id"] for g in env["ES_AI_SHOWN"]])
                    delivered.append(cid)
                    return None
                env["es_ai_cameo_line"] = line
                env["es_ai_cameo_tick"] = lambda *a: self.fail("Farewell ticked")
                env["es_ai_maybe_cameo"] = lambda *a: self.fail("Farewell summoned")
                env["es_ai_try_cameo"]("sl", "Bye", {
                    "cameo_leave": leaving, "cameo": leaving, "cameo_requested": True})
                expected = set(leaving) & {"dv", "us", "el", "sh"}
                self.assertEqual(len(delivered), min(2, len(expected)))
                self.assertFalse(expected & {g["id"] for g in env["ES_AI_SHOWN"]})
                self.assertNotIn("mi", [g["id"] for g in env["ES_AI_SHOWN"]])

    def test_missing_max_setting_defaults_to_six_without_writes(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai_cameo.rpy"), env, {"es_ai_read_cameo_settings", "es_ai_user_config_path"})
            env["ES_AI_SERVER_DIR"] = "unused"
            for config, expected in (("{}", 6), ('{"cameo_max_extra":99}', 6),
                                     ('{"cameo_max_extra":2}', 2)):
                with patch("io.open", side_effect=lambda *a, **k: io.StringIO(config)) as opened:
                    self.assertEqual(env["es_ai_read_cameo_settings"]()["cameo_max_extra"], expected)
                    self.assertTrue(all(call.args[1] == "r" for call in opened.call_args_list))

    def test_sprite_preference_and_male_fallback(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai.rpy"), env,
                 {"es_ai_resolve_sprite", "es_ai_fallback_emotion"})
            images = {"dv normal swim", "dv angry pioneer", "us normal swim close", "us laugh pioneer",
                      "el normal pioneer", "sh normal pioneer"}
            env["renpy"].has_image = lambda tag: tag in images
            resolve = env["es_ai_resolve_sprite"]
            self.assertEqual(resolve("dv", "angry", "swim"), "dv normal swim")
            self.assertEqual(resolve("us", "laugh", "swim"), "us normal swim close")
            for cid in ("el", "sh"):
                self.assertEqual(resolve(cid, "normal", "swim"), cid + " normal pioneer")
            self.assertEqual(resolve("dv", "angry"), "dv angry pioneer")

    def test_participant_layout(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai_locations.rpy"), env)
            rendered, hidden = {}, []
            env["Transform"] = lambda **kwargs: kwargs
            env["ES_AI_HEIGHTS"] = {"us": 140, "sl": 180}
            env["es_ai_resolve_sprite"] = lambda cid, emo, dress_pref=None: cid + " " + emo
            env["es_ai_log"] = lambda s: self.fail(s)
            env["renpy"].show = lambda tag, at_list, zorder: rendered.update(
                {tag.split()[0]: (at_list[0], zorder)})
            env["renpy"].hide = hidden.append
            refresh = env["es_ai_refresh_girls"]
            ids = ["sl", "dv", "us", "el", "sh", "mi", "un"]
            for n in range(8):
                env["ES_AI_SHOWN"][:] = [{"id": cid, "emo": "normal", "cameo": i > 0}
                                          for i, cid in enumerate(ids[:n])]
                rendered.clear()
                refresh()
                self.assertEqual(set(rendered), set(ids[:n]))
                self.assertFalse(hidden)
                before = dict(rendered)
                cache = env["ES_AI_GIRL_LAYOUT"][1]
                env["ES_AI_SHOWN"].reverse()
                refresh()
                self.assertEqual(rendered, before)
                self.assertIs(env["ES_AI_GIRL_LAYOUT"][1], cache)
                if not n:
                    continue
                positions = sorted(v[0]["xpos"] for v in rendered.values())
                self.assertTrue(all(0.08 <= x <= 0.92 for x in positions))
                self.assertTrue(all(v[0]["xanchor"] == 0.5 for v in rendered.values()))
                if n == 1:
                    self.assertEqual(positions, [0.5])
                if n >= 4:
                    self.assertGreaterEqual(positions[-1] - positions[0], 0.74)
                if n > 4:
                    front = [v for v in rendered.values() if v[0]["zoom"] == 0.88]
                    rear = [v for v in rendered.values() if v[0]["zoom"] == 0.75]
                    self.assertEqual(len(front), 4)
                    self.assertEqual(len(rear), n - 4)
                    self.assertTrue(all(v[0]["yoffset"] == -25 for v in rear))
                    self.assertGreater(min(v[1] for v in front), max(v[1] for v in rear))
                    self.assertIn(rendered["sl"], front)
                if n > 1:
                    order = [g["id"] for g in env["ES_AI_SHOWN"]]
                    env["es_ai_cameo_speak"]("dv", "Hi", "smile", "cover")
                    self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], order)
                    self.assertEqual({cid: v[0] for cid, v in rendered.items()},
                                     {cid: v[0] for cid, v in before.items()})
                    self.assertEqual(rendered["dv"][1], before["dv"][1] + 2000)
                    self.assertIs(env["ES_AI_GIRL_LAYOUT"][1], cache)
                if n > 4:
                    rear_id = next(cid for cid, v in before.items() if v[0]["zoom"] == 0.75)
                    env["es_ai_cameo_speak"](rear_id, "Hi")
                    self.assertGreater(rendered[rear_id][1],
                                       max(v[1] for cid, v in rendered.items() if cid != rear_id))
                    self.assertEqual({cid: v[0] for cid, v in rendered.items()},
                                     {cid: v[0] for cid, v in before.items()})
                    self.assertIs(env["ES_AI_GIRL_LAYOUT"][1], cache)
            old_key = env["ES_AI_GIRL_LAYOUT"][0]
            for g in env["ES_AI_SHOWN"]:
                g["cameo"] = g["id"] != rear_id
                g.pop("focused", None)
            refresh()
            self.assertNotEqual(env["ES_AI_GIRL_LAYOUT"][0], old_key)
            self.assertEqual(env["ES_AI_GIRL_LAYOUT"][0][:2], old_key[:2])
            self.assertEqual(env["ES_AI_GIRL_LAYOUT"][0][2], rear_id)
            self.assertIsNot(env["ES_AI_GIRL_LAYOUT"][1], cache)
            self.assertEqual(rendered[rear_id][0]["zoom"], 0.88)
            self.assertAlmostEqual(rendered[rear_id][0]["xpos"], 0.38)
            cache = env["ES_AI_GIRL_LAYOUT"][1]
            env["ES_AI_LOC_CUR"][0] = "beach"
            refresh()
            self.assertIsNot(env["ES_AI_GIRL_LAYOUT"][1], cache)
            env["es_ai_girls_reset"]()
            self.assertEqual(env["ES_AI_GIRL_LAYOUT"], [None, {}])
            for n in (2, 3):
                spans = []
                for seed in range(100):
                    env["_es_random"].seed(seed)
                    env["ES_AI_GIRL_LAYOUT"][:] = [None, {}]
                    env["ES_AI_SHOWN"][:] = [{"id": cid, "emo": "normal", "cameo": i > 0}
                                              for i, cid in enumerate(ids[:n])]
                    rendered.clear()
                    refresh()
                    xs = [v[0]["xpos"] for v in rendered.values()]
                    spans.append(max(xs) - min(xs))
                self.assertTrue(any(span < 0.45 for span in spans))
                self.assertTrue(any(span > 0.60 for span in spans))

    def test_shipped_swim_assets(self):
        archive = r"D:\Program Files (x86)\Steam\steamapps\common\Everlasting Summer\game\archive.rpa"
        with io.open(archive, "rb") as stream:
            header = stream.readline().split()
            stream.seek(int(header[1], 16))
            index = pickle.loads(zlib.decompress(stream.read()))
        names = [name.decode("utf-8") if isinstance(name, bytes) else name for name in index]
        for cid in ("dv", "us"):
            self.assertTrue(any("/" + cid + "/" in name and "swim" in name for name in names), cid)
        for cid in ("el", "sh"):
            self.assertFalse(any("/" + cid + "/" in name and "swim" in name for name in names), cid)
            self.assertTrue(any("/" + cid + "/" in name and "normal" in name for name in names), cid)

    @unittest.skipIf(sys.version_info[0] < 3, "Server uses Python 3")
    def test_server_dress_only(self):
        for path in (os.path.join(DEV, "server/main.py"), os.path.join(WORKSHOP, "server/main.py")):
            env = {"re": re, "cfg": {}}
            load(path, env, {"cameo", "parse_action_tags", "parse_cameo_tags", "normalize_dress",
                             "clock_prompt", "game_clock_valid"}, False)
            llm = types.ModuleType("llm_client")
            store = types.ModuleType("characters_store")
            store.get_character = lambda cid: {"persona": "persona", "name": cid}
            store.map_emotion = lambda cid, emo: emo
            store.reply_rules = lambda ch: "AGE SAFETY RULES"
            store.player_block = lambda: ""
            llm.sanitize_in_character = lambda s: s
            llm.strip_prompt_leak = lambda s, p: s
            captured = []
            previous = {key: sys.modules.get(key) for key in ("llm_client", "characters_store")}
            sys.modules.update(llm_client=llm, characters_store=store)
            try:
                for signal, expected in ((" SWIM ", "swim"), ("cover", "cover"), ("sport", "sport"),
                                         ("notswim", None), ("swim garbage", None), ("???", None)):
                    def chat(messages, **kwargs):
                        captured.append(messages[0]["content"])
                        return "(smile) Hi [action:dress:%s] [action:goto:beach] [action:time:night] [action:cameo:dv]" % signal
                    llm.chat = chat
                    out = env["cameo"]({"character": "us", "location": "beach"})
                    self.assertEqual(out["reply"], "Hi")
                    self.assertEqual(out.get("dress"), expected)
                    self.assertFalse(set(out) & {"goto", "time", "cameo"})
                self.assertIn("AGE SAFETY RULES", captured[0])
                self.assertIn("ordinary, non-sexual", captured[0])
                self.assertIn("Never emit goto, time or cameo", captured[0])
            finally:
                for key, value in previous.items():
                    if value is None:
                        sys.modules.pop(key, None)
                    else:
                        sys.modules[key] = value


if __name__ == "__main__":
    unittest.main()
