"""Offline cameo clothing checks for both installs and Python 2 Ren'Py stores."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import io
import json
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
WORKSHOP = WORKSHOP_ROOT
ROOTS = (os.path.join(DEV, "mod"),) + existing_paths((WORKSHOP,))
REQUEST_CASES = (
    ("Славя надень форму а не купальник", "cover"),
    ("Славя сними купальник и надень форму", "cover"),
    ("Славя не надевай купальник", None),
    ("Славя надень купальник а не форму", "swim"),
    ("Славя, надень форму, а не купальник", "cover"),
    ("Славя, не надень купальник", None),
    ("Славя, не надевай купальник и надень форму", "cover"),
    ("Славя, надень купальник и затем надень форму", "cover"),
    ("Славя, не прикройся", None),
    ("Славя, сними купальник", "cover"),
    ("Славя, купальник красивый, надень форму", "cover"),
    ("Славя привет. Лена надень купальник", None),
    ("Неславя надень купальник", None),
    ("sl, put on a uniform not a swimsuit", None),
    ("sl, put on a swimsuit but not a uniform", "swim"),
    ("sl, don't put on a swimsuit", None),
    ("sl, take off swimsuit and put on uniform", "cover"),
)


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
                     (t.id.startswith("ES_AI_") and (names is None or t.id in names or t.id in {
                         "ES_AI_EMOTIONS", "ES_AI_EMOTION_RU", "ES_AI_DRESSES"}))) for t in node.targets):
                nodes.append(node)
    module = ast.Module(body=nodes, type_ignores=[]) if sys.version_info[0] >= 3 else ast.Module(body=nodes)
    eval(compile(module, path, "exec"), env)


def install_delivery_say(root, env):
    """Adapt legacy text-only test speakers; production requires a real Character."""
    env.update(_delivery_builtins=builtins, config=types.SimpleNamespace(character_callback=None))
    load(os.path.join(root, "es_ai_delivery.rpy"), env, {"es_ai_delivery_say"})
    actual = env["es_ai_delivery_say"]
    env["es_ai_delivery_flush"] = lambda **kw: None

    def say(speaker, text, cid, raw, ack=None, choices=None):
        class Character:
            display_args = {"callback": None}

            def __call__(self, value, callback):
                result = speaker(value)
                callback("show_done", interact=True, type="say")
                return result
        return actual(Character(), text, cid, raw, ack, choices)
    env["es_ai_delivery_say"] = say


class ClothingTests(unittest.TestCase):
    def environment(self, root):
        persistent = Stub()
        persistent.es_ai_tts = False
        renpy = Stub()
        renpy.with_statement = lambda *a: None
        renpy.hide = lambda *a: None
        renpy.has_image = lambda tag, exact=False: tag.split()[0] not in ("el", "sh", "mz", "cs")
        env = {"_es_ai_cameo_builtins": builtins, "_es_random": random.Random(7),
               "dict": StoreDict, "list": StoreList, "persistent": persistent,
               "renpy": renpy, "dissolve": None,
               "basestring": getattr(builtins, "basestring", str),
               "unicode": getattr(builtins, "unicode", str), "long": getattr(builtins, "long", int)}
        load(os.path.join(root, "es_ai_cameo.rpy"), env)
        load(os.path.join(root, "es_ai_locations.rpy"), env,
             {"es_ai_default_dress", "es_ai_clothing_night", "es_ai_no_swimming"})
        load(os.path.join(root, "es_ai_api.rpy"), env,
             {"es_ai_story_ack_record", "es_ai_story_ack_snapshot", "ES_AI_STORY_ACKS",
              "ES_AI_STORY_INPUT", "es_ai_story_choices_record"})
        env["es_ai_clock_snapshot"] = lambda: dict(enabled=False, time="08:00", phase="day")
        env["ES_AI_FREE_SCENE"] = [True]
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
        env["ES_AI_SERVER_DIR"] = os.path.join(DEV, "server") if root == ROOTS[0] else os.path.join(root, "server")
        env["es_ai_cameo_adult_home_ids"] = lambda: {"sl", "mt"}
        install_delivery_say(root, env)
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
            self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "us, put on a swimsuit"
            enter("us", "normal", dress="swim")
            self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "swim")

    def test_library_rejects_unsolicited_and_legacy_swim(self):
        for root in ROOTS:
            env = self.environment(root)
            env["ES_AI_LOC_CUR"][0] = "library"
            env["es_ai_location"] = lambda: {"romantic": True, "dress": None}
            env["ES_AI_RECENT_LINES"][:] = [{"who": "Player", "what": "sl, put on a swimsuit"}]
            env["ES_AI_SHOWN"][:] = []
            env["ES_AI_CAMEO_NEARBY"]["beach"] = [{"id": "sl", "dress": "swim"}]
            env["es_ai_cameo_enter"]("sl", "normal", dress="swim")
            g = env["ES_AI_SHOWN"][0]
            self.assertIsNone(g["dress"])
            self.assertNotIn("beach", env["ES_AI_CAMEO_NEARBY"])
            g["dress"] = "swim"  # Legacy save has no authorized reason.
            env["es_ai_cameo_enter"]("sl", "smile")
            self.assertIsNone(g["dress"])
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "Славя, надень купальник"
            env["es_ai_cameo_enter"]("sl", "smile")
            self.assertEqual(g["dress"], "swim")
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
            env["es_ai_cameo_park"]("sl", announce=False)
            env["es_ai_cameo_enter"]("sl", "normal")
            self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "swim")
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "Лена, надень купальник"
            self.assertIsNone(env["es_ai_cameo_clothing_request"]("sl"))
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
            env["es_ai_cameo_park"]("sl", announce=False)
            env["ES_AI_LOC_CUR"][0] = "square"
            env["es_ai_cameo_enter"]("sl", "normal", dress="swim")
            self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])

    def test_privacy_handoff_preserves_each_existing_outfit(self):
        import copy
        import test_clothing_long_session as long_session
        for root in ROOTS:
            for active in ("sl", "mi"):
                for initial in (None, "swim"):
                    with self.subTest(root=root, active=active, initial=initial):
                        env = long_session.ClothingLongSessionTests().environment(root)
                        env["_images"].add("mi normal swim")
                        env["ES_AI_LOC_CUR"][0] = "un_room"
                        env["ES_AI_TIME"][0] = "night"
                        env["ES_AI_CLOCK"].update(enabled=True, minutes=59)
                        env["es_ai_cameo_adult_home_ids"] = lambda: {"sl", "mi", "un"}
                        env["ES_AI_LOC_LAST_CHAR"][0] = active
                        env["es_ai_char_id"] = active
                        env["ES_AI_DRESS"][0] = initial if active == "mi" else None
                        env["ES_AI_SHOWN"][:] = [dict(id=cid, emo="normal", cameo=cid != active,
                            dress=initial if cid == "mi" else None,
                            dress_reason="night_home" if cid == "mi" and initial else "location",
                            dress_location="un_room") for cid in (active, "mi" if active == "sl" else "sl", "un")]
                        env["es_ai_refresh_girls"]()
                        sl = copy.deepcopy(next(g for g in env["ES_AI_SHOWN"] if g["id"] == "sl"))
                        response = dict(id="mi", privacy=True, scene_depart=["sl", "un"],
                                        dress=None, reply="Пойдём на пляж")
                        if active != "mi":
                            response["switch_primary"] = "mi"
                        env["es_ai_apply_actions"](response, "Славя я хочу побыть наедине с Мику")
                        self.assertEqual(env["ES_AI_LOC_CUR"][0], "un_room")
                        self.assertEqual(env["ES_AI_LOC_LAST_CHAR"][0], "mi")
                        self.assertEqual(env["ES_AI_DRESS"][0], initial)
                        self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["mi"])
                        self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "mi normal " + (initial or "pioneer"))
                        self.assertEqual(env["ES_AI_CAMEO_NEARBY"]["un_room"], [])
                        self.assertEqual(set(env["ES_AI_SCENE_ABSENT"]["un_room"]), {"sl", "un"})
                        env["es_ai_apply_actions"]({}, "давай останемся наедине")
                        self.assertEqual(env["ES_AI_DRESS"][0], initial)

    def test_night_home_draw_once_and_cover_cancels(self):
        homes = {"sl": "sl_room", "mz": "sl_room", "un": "un_room", "mi": "un_room",
                 "dv": "dv_room", "us": "dv_room", "mt": "mt_room"}
        for root in ROOTS:
            for cid, home in homes.items():
                env = self.environment(root)
                env["ES_AI_SHOWN"][:] = []
                env["ES_AI_LOC_CUR"][0] = home
                env["es_ai_location"] = lambda: {"dress": None, "romantic": True}
                env["ES_AI_CLOCK"].update(enabled=True, minutes=22 * 60)
                with patch.object(env["_es_random"], "random", return_value=0.499) as draw:
                    env["es_ai_cameo_enter"](cid, "normal", True)
                    g = env["ES_AI_SHOWN"][0]
                    self.assertEqual(g["dress"], None if cid == "mz" else "swim")
                    self.assertEqual(draw.call_count, 0 if cid == "mz" else 1)
                    env["es_ai_cameo_enter"](cid, "smile", True)
                    env["es_ai_cameo_park"](cid, announce=False)
                    env["es_ai_cameo_enter"](cid, "normal", True)
                    self.assertEqual(draw.call_count, 0 if cid == "mz" else 1)
                    env["es_ai_cameo_enter"](cid, "normal", dress="cover")
                    self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "pioneer")
                    self.assertNotEqual(env["ES_AI_SHOWN"][0]["dress_reason"], "night_home")
            for loc, minute, value, expected_calls in (("sl_room", 21 * 60, .1, 1),
                    ("sl_room", 6 * 60, .1, 1), ("sl_room", 5 * 60 + 59, .5, 1),
                    ("library", 23 * 60, 0, 0), ("club_room", 23 * 60, 0, 0),
                    ("un_room", 23 * 60, 0, 0), ("aidpost_inside", 23 * 60, 0, 0)):
                env = self.environment(root)
                env["ES_AI_SHOWN"][:] = []
                env["ES_AI_LOC_CUR"][0] = loc
                env["es_ai_location"] = lambda: {"dress": None}
                env["ES_AI_CLOCK"].update(enabled=True, minutes=minute)
                with patch.object(env["_es_random"], "random", return_value=value) as draw:
                    env["es_ai_cameo_enter"]("sl", "normal")
                    self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])
                    self.assertEqual(draw.call_count, expected_calls)
            env = self.environment(root)
            env["ES_AI_SHOWN"][:] = []
            env["ES_AI_LOC_CUR"][0] = "sl_room"
            env["es_ai_location"] = lambda: {"dress": None}
            with patch.object(env["_es_random"], "random", return_value=0) as draw:
                env["es_ai_cameo_enter"]("sl", "normal", romantic=True)
                draw.assert_not_called()
                self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])

    def test_day_changing_adult_boundaries_and_no_reroll(self):
        for root in ROOTS:
            for cid, home in (("sl", "sl_room"), ("mt", "mt_room"), ("dv", "dv_room"),
                              ("un", "un_room"), ("mi", "un_room")):
                for value, expected in ((.099, "swim"), (.1, None)):
                    env = self.environment(root)
                    env["es_ai_cameo_adult_home_ids"] = lambda: {"sl", "mt", "dv", "un", "mi"}
                    env["ES_AI_SHOWN"][:] = []
                    env["ES_AI_LOC_CUR"][0] = home
                    env["ES_AI_TIME"][0] = "day"
                    env["es_ai_location"] = lambda: {"dress": None}
                    with patch.object(env["_es_random"], "random", return_value=value) as draw:
                        env["es_ai_cameo_enter"](cid, "normal", True)
                        g = env["ES_AI_SHOWN"][0]
                        self.assertEqual(g["dress"], expected)
                        self.assertEqual(g["dress_reason"], "home_changing" if expected else "location")
                        env["es_ai_cameo_enter"](cid, "smile", True, dress=expected)
                        env["es_ai_cameo_park"](cid, announce=False)
                        env["es_ai_cameo_enter"](cid, "normal", True)
                        self.assertEqual(draw.call_count, 1)
                        if expected:
                            env["es_ai_cameo_enter"](cid, "normal", dress="cover")
                            env["es_ai_cameo_enter"](cid, "normal", dress="swim")
                            self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "pioneer")
                    record = {"id": cid, "dress_reason": "home_changing", "dress_location": home}
                    env["ES_AI_TIME"][0] = "night"
                    self.assertIsNone(env["es_ai_cameo_dress"]("swim", "swim", record))
                    record["dress_reason"] = "night_home"
                    env["ES_AI_TIME"][0] = "day"
                    self.assertIsNone(env["es_ai_cameo_dress"]("swim", "swim", record))
            for cid, loc, assets, romantic in (("us", "dv_room", True, False),
                    ("dv", "dv_room", True, False), ("un", "un_room", True, False),
                    ("mi", "un_room", True, False), ("cs", "aidpost_inside", True, False),
                    ("sl", "library", True, False), ("sl", "sl_room", False, False),
                    ("sl", "sl_room", True, True)):
                env = self.environment(root)
                env["ES_AI_SHOWN"][:] = []
                env["ES_AI_LOC_CUR"][0] = loc
                env["ES_AI_TIME"][0] = "day"
                env["es_ai_location"] = lambda: {"dress": None}
                env["renpy"].has_image = lambda tag: assets
                with patch.object(env["_es_random"], "random", return_value=0) as draw:
                    env["es_ai_cameo_enter"](cid, "normal", romantic=romantic)
                    draw.assert_not_called()
                    self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])
                record = {"id": cid, "dress_reason": "home_changing", "dress_location": loc}
                if cid not in ("sl", "mt") or loc != "sl_room":
                    self.assertIsNone(env["es_ai_cameo_dress"]("swim", "swim", record))

    def test_server_home_changing_age_clock_and_privacy(self):
        for path in existing_paths((os.path.join(DEV, "server/main.py"), os.path.join(WORKSHOP, "server/main.py"))):
            env = {"re": re, "cfg": {}}
            load(path, env, {"cameo", "parse_action_tags", "parse_cameo_tags", "normalize_dress",
                             "clock_prompt", "game_clock_valid"}, False)
            llm = types.ModuleType("llm_client")
            store = types.ModuleType("characters_store")
            store.map_emotion = lambda cid, emo: emo
            store.reply_rules = lambda ch: "AGE SAFETY RULES"
            store.player_block = lambda: ""
            llm.sanitize_in_character = lambda s: s
            llm.strip_prompt_leak = lambda s, p: s
            captured = []
            llm.chat = lambda messages, **kwargs: captured.append(messages[0]["content"]) or "(smile) Please wait. [action:dress:swim] [action:aside]"
            with patch.dict(sys.modules, llm_client=llm, characters_store=store,
                            scene_memory=types.SimpleNamespace(ingest=lambda events: None, prompt=lambda cid: "")):
                for age in (18, 27, 17, 14, None, "18", True):
                    store.get_character = lambda cid: {"name": cid, "persona": "I am 18 years old.", "age": age}
                    request = {"character": "sl", "location_id": "sl_room", "dress": "swim",
                               "dress_reason": "home_changing", "clock": {"enabled": True, "time": "12:00", "phase": "day"}}
                    out = env["cameo"](request)
                    adult = age in (18, 27)
                    self.assertEqual(out.get("dress"), "swim" if adult else None)
                    self.assertIn("AUTHORITATIVE CURRENT CLOTHING: " + ("swim" if adult else "pioneer"), captured[-1])
                    if adult:
                        self.assertIn("Allow privacy", captured[-1])
                        self.assertIn("No body or sexual descriptions", captured[-1])
                        self.assertIn("never describe changing clothes", captured[-1])
                        self.assertIn("otherwise wait outside", captured[-1])
                        self.assertTrue(out["aside"])
                store.get_character = lambda cid: {"name": cid, "persona": "", "age": 18}
                for cid, home in (("mi", "un_room"), ("un", "un_room"), ("dv", "dv_room")):
                    self.assertEqual(env["cameo"](dict(request, character=cid, location_id=home)).get("dress"), "swim")
                for changes in ({"clock": None}, {"clock": {"enabled": True, "time": "23:00", "phase": "day"}},
                        {"clock": {"enabled": True, "time": "12:00", "phase": "night"}},
                        {"clock": {"time": "bad", "phase": "day"}}, {"location_id": "library"},
                        {"dress": "pioneer"}, {"character": "us", "location_id": "dv_room"},
                        {"character": "uv", "location_id": "un_room"},
                        {"romantic": True}, {"dress_reason": "night_home"}):
                    self.assertIsNone(env["cameo"](dict(request, **changes)).get("dress"))

    def test_structured_home_age_loader_and_user_path_precedence(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai_cameo.rpy"), env, {"es_ai_cameo_adult_home_ids"})
            env["es_ai_user_config_path"] = lambda: os.path.join("user-data", "config.json")
            roster = [{"id": cid, "name": cid, "age": 18, "persona": "not used"}
                      for cid in ("sl", "mt", "mi", "un", "dv", "us", "uv", "el", "sh", "mz", "cs")]
            for age, eligible in ((18, True), (17, False), (None, False), ("18", False), (True, False)):
                roster[0].update(age=age, persona="I am 18 years old.")
                with patch("io.open", side_effect=lambda *a, **k: io.StringIO(json.dumps({"characters": roster}))) as opener:
                    ids = env["es_ai_cameo_adult_home_ids"]()
                self.assertEqual("sl" in ids, eligible)
                self.assertEqual(ids - {"sl"}, {"mt", "mi", "un", "dv", "mz", "cs"})
                expected = os.path.join("user-data", "es_characters.json") if root == WORKSHOP else os.path.join(env["ES_AI_SERVER_DIR"], "es_characters.json")
                self.assertEqual(opener.call_args.args[0], expected)
            with patch("io.open", side_effect=[IOError("missing"), io.StringIO(json.dumps({"characters": roster}))]) as opener:
                ids = env["es_ai_cameo_adult_home_ids"]()
                self.assertEqual(opener.call_count, 2 if root == WORKSHOP else 1)
                self.assertEqual(ids, {"mt", "mi", "un", "dv", "mz", "cs"} if root == WORKSHOP else set())
            for raw in ('{}', '{"characters": {}}', 'x' * 1048577):
                with patch("io.open", side_effect=lambda *a, **k: io.StringIO(raw)):
                    self.assertEqual(env["es_ai_cameo_adult_home_ids"](), set())

    def test_day_explicit_exclusions_even_with_customized_adult_age(self):
        for root in ROOTS:
            for cid in ("us", "uv"):
                env = self.environment(root)
                env["es_ai_cameo_adult_home_ids"] = lambda: {"us", "uv"}
                env["ES_AI_CAMEO_HOMES"]["uv"] = "dv_room"
                env["ES_AI_SHOWN"][:] = []
                env["ES_AI_LOC_CUR"][0] = "dv_room"
                env["ES_AI_TIME"][0] = "day"
                env["es_ai_location"] = lambda: {"dress": None}
                with patch.object(env["_es_random"], "random", return_value=0) as draw:
                    env["es_ai_cameo_enter"](cid, "normal")
                    draw.assert_not_called()
                self.assertIsNone(env["ES_AI_SHOWN"][0]["dress"])

    def test_clothing_request_negation_and_night_cover_persistence(self):
        for root in ROOTS:
            env = self.environment(root)
            for text, expected in REQUEST_CASES:
                with self.subTest(root=root, text=text):
                    env["ES_AI_CAMEO_PLAYER_TEXT"][0] = text
                    self.assertEqual(env["es_ai_cameo_clothing_request"]("sl"), expected)
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
            env["ES_AI_SHOWN"][:] = []
            env["ES_AI_LOC_CUR"][0] = "sl_room"
            env["es_ai_location"] = lambda: {"dress": None}
            with patch.object(env["_es_random"], "random", return_value=0) as draw:
                env["es_ai_cameo_enter"]("sl", "normal", True)
                self.assertEqual(env["ES_AI_SHOWN"][0]["dress_reason"], "night_home")
                env["ES_AI_CAMEO_PLAYER_TEXT"][0] = REQUEST_CASES[0][0]
                env["es_ai_cameo_enter"]("sl", "smile", dress="swim")
                env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
                env["es_ai_cameo_park"]("sl", announce=False)
                env["es_ai_cameo_enter"]("sl", "normal", dress="swim")
                self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "pioneer")
                self.assertEqual(env["ES_AI_SHOWN"][0]["dress_reason"], "player")
                self.assertEqual(draw.call_count, 1)

    def test_server_request_negation_matches_clients(self):
        for path in existing_paths((os.path.join(DEV, "server/main.py"), os.path.join(WORKSHOP, "server/main.py"))):
            env = {"re": re, "cfg": {}}
            load(path, env, {"cameo", "parse_action_tags", "parse_cameo_tags", "normalize_dress",
                             "clock_prompt", "game_clock_valid"}, False)
            llm = types.ModuleType("llm_client")
            store = types.ModuleType("characters_store")
            store.get_character = lambda cid: {"persona": "swim persona trigger", "name": cid}
            store.map_emotion = lambda cid, emo: emo
            store.reply_rules = lambda ch: "AGE SAFETY RULES"
            store.player_block = lambda: "Current player identity"
            llm.sanitize_in_character = lambda s: s
            llm.strip_prompt_leak = lambda s, p: s
            captured = []
            llm.chat = lambda messages, **kwargs: captured.append(messages[0]["content"]) or "(smile) Hi [action:dress:swim]"
            with patch.dict(sys.modules, llm_client=llm, characters_store=store,
                            scene_memory=types.SimpleNamespace(ingest=lambda events: None, prompt=lambda cid: "")):
                for text, expected in REQUEST_CASES:
                    with self.subTest(path=path, text=text):
                        out = env["cameo"]({"character": "sl", "location_id": "library",
                                            "player_text": text, "romantic": False})
                        self.assertEqual(out.get("dress"), expected)
                        self.assertIn("Current player clothing request: %s." % (expected or "none"), captured[-1])
                        self.assertIn("AGE SAFETY RULES", captured[-1])
                        self.assertEqual(out["reply"], "Hi")
                out = env["cameo"]({"character": "sl", "location_id": "sl_room", "dress": "swim",
                                    "dress_reason": "night_home", "player_text": REQUEST_CASES[0][0]})
                self.assertEqual(out["dress"], "cover")
                self.assertIn("AUTHORITATIVE CURRENT CLOTHING: swim", captured[-1])

    def test_payload_reports_clothing_and_asset_fallback(self):
        for root in ROOTS:
            env = self.environment(root)
            env["es_ai_clock_sync"] = lambda **kwargs: None
            env["es_ai_clock_snapshot"] = lambda: {"phase": "night", "time": "23:00"}
            env["ES_AI_LOC_CUR"][0] = "sl_room"
            env["ES_AI_SHOWN"][:] = [{"id": "sl", "dress": "swim", "dress_reason": "night_home",
                                      "tag": "sl normal swim"}]
            captured = []
            env["es_ai_http"] = lambda url, payload: captured.append(payload) or {"ok": True}
            def run(_name, fn):
                return types.SimpleNamespace(done=True, error=None, result=fn())
            env["es_ai_run_async"] = run
            env["es_ai_cameo_line"]("sl", "dv", False)
            self.assertEqual(captured[-1]["dress"], "swim")
            self.assertEqual(captured[-1]["dress_reason"], "night_home")
            self.assertEqual(captured[-1]["location_id"], "sl_room")
            env["ES_AI_SHOWN"][0]["tag"] = "sl normal pioneer"
            env["es_ai_cameo_line"]("sl", "dv", False)
            self.assertEqual(captured[-1]["dress"], "pioneer")

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
                                 ["pioneer" if g.get("cover_choice") else "swim" for g in env["ES_AI_SHOWN"] if g.get("cameo")])

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
            env["renpy"].has_image = lambda tag, exact=False: tag in images if exact else any(image.startswith(tag) for image in images)
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
            env["es_ai_log"] = lambda s: None if s.startswith("sprite id=") else self.fail(s)
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
        archive = os.path.join(GAME_ROOT, "game/archive.rpa")
        if not os.path.isfile(archive):
            self.skipTest("Game archive unavailable")
        with io.open(archive, "rb") as stream:
            header = stream.readline().split()
            stream.seek(int(header[1], 16))
            index = pickle.loads(zlib.decompress(stream.read()))
        names = [name.decode("utf-8") if isinstance(name, bytes) else name for name in index]
        for cid in ("dv", "us"):
            self.assertTrue(any("/" + cid + "/" in name and "swim" in name for name in names), cid)
        for cid in ("el", "sh", "cs"):
            self.assertFalse(any("/" + cid + "/" in name and "swim" in name for name in names), cid)
            self.assertTrue(any("/" + cid + "/" in name and "normal" in name for name in names), cid)

    def test_cs_rest_draw_boundaries_assets_and_no_speaker_needed(self):
        for root in ROOTS:
            for phase, minute, threshold, reason in (("night", 23 * 60, .5, "night_home"),
                    ("day", 12 * 60, .1, "home_changing")):
                for loc in ("aidpost_inside", "aidpost", "library"):
                    for assets in (False, True):
                        for value in (threshold - .001, threshold):
                            with self.subTest(root=root, phase=phase, loc=loc, assets=assets, value=value):
                                env = self.environment(root)
                                self.assertNotIn("cs", env["es_ai_speakers"])
                                env["es_ai_cameo_adult_home_ids"] = lambda: {"cs"}
                                env["ES_AI_SHOWN"][:] = []
                                env["ES_AI_LOC_CUR"][0] = loc
                                env["ES_AI_TIME"][0] = phase
                                env["ES_AI_CLOCK"].update(enabled=True, minutes=minute)
                                env["es_ai_location"] = lambda: {"dress": None}
                                images = {"cs normal swim close"} if assets else {"cs normal"}
                                env["renpy"].has_image = lambda tag: tag in images
                                eligible = loc == "aidpost_inside" and assets
                                expected = "swim" if eligible and value < threshold else None
                                with patch.object(env["_es_random"], "random", return_value=value) as draw:
                                    env["es_ai_cameo_enter"]("cs", "normal", True)
                                    g = env["ES_AI_SHOWN"][0]
                                    self.assertEqual(g["dress"], expected)
                                    self.assertEqual(g["dress_reason"], reason if expected else "location")
                                    env["es_ai_cameo_enter"]("cs", "smile", True)
                                    env["es_ai_cameo_park"]("cs", announce=False)
                                    env["es_ai_cameo_enter"]("cs", "normal", True)
                                    self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], expected)
                                    self.assertEqual(draw.call_count, int(eligible))

    def test_cs_sprite_resolution_uses_only_registered_images(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai.rpy"), env,
                 {"es_ai_resolve_sprite", "es_ai_fallback_emotion"})
            for images, expected in (({"cs normal", "cs smile close"}, "cs normal"),
                    ({"cs normal", "cs normal swim close"}, "cs normal swim close")):
                env["renpy"].has_image = lambda tag, exact=False: tag in images if exact else any(image.startswith(tag) for image in images)
                self.assertEqual(env["es_ai_resolve_sprite"]("cs", "normal", "swim"), expected)

    def test_cs_day_structured_age_and_romantic_exclusion(self):
        for root in ROOTS:
            for age, romantic in ((27, False), (18, False), (17, False),
                    (None, False), ("27", False), (True, False), (27, True)):
                env = self.environment(root)
                load(os.path.join(root, "es_ai_cameo.rpy"), env, {"es_ai_cameo_adult_home_ids"})
                env["es_ai_user_config_path"] = lambda: os.path.join("user-data", "config.json")
                env["ES_AI_SHOWN"][:] = []
                env["ES_AI_LOC_CUR"][0] = "aidpost_inside"
                env["ES_AI_TIME"][0] = "day"
                env["es_ai_location"] = lambda: {"dress": None}
                env["renpy"].has_image = lambda tag: tag == "cs normal swim"
                roster = {"characters": [{"id": "cs", "age": age, "persona": "I am 27."}]}
                with patch("io.open", side_effect=lambda *a, **k: io.StringIO(json.dumps(roster))):
                    with patch.object(env["_es_random"], "random", return_value=0) as draw:
                        env["es_ai_cameo_enter"]("cs", "normal", romantic=romantic)
                        eligible = type(age) is int and age >= 18 and not romantic
                        self.assertEqual(env["ES_AI_SHOWN"][0]["dress"], "swim" if eligible else None)
                        self.assertEqual(draw.call_count, int(eligible))

    def test_cs_server_rest_prompt_and_authorization(self):
        for path in existing_paths((os.path.join(DEV, "server/main.py"), os.path.join(WORKSHOP, "server/main.py"))):
            env = {"re": re, "cfg": {}}
            load(path, env, {"cameo", "parse_action_tags", "parse_cameo_tags", "normalize_dress",
                             "clock_prompt", "game_clock_valid"}, False)
            llm = types.ModuleType("llm_client")
            store = types.ModuleType("characters_store")
            store.map_emotion = lambda cid, emo: emo
            store.reply_rules = lambda ch: "AGE SAFETY RULES"
            store.player_block = lambda: ""
            llm.sanitize_in_character = lambda s: s
            llm.strip_prompt_leak = lambda s, p: s
            captured = []
            llm.chat = lambda messages, **kwargs: captured.append(messages[0]["content"]) or "(normal) Please knock. [action:dress:swim]"
            with patch.dict(sys.modules, llm_client=llm, characters_store=store,
                            scene_memory=types.SimpleNamespace(ingest=lambda events: None, prompt=lambda cid: "")):
                for phase, time, reason in (("night", "23:00", "night_home"),
                        ("day", "12:00", "home_changing")):
                    store.get_character = lambda cid: {"id": cid, "name": "Viola", "age": 27, "persona": "Medical worker."}
                    request = {"character": "cs", "location_id": "aidpost_inside", "dress": "swim",
                               "dress_reason": reason, "clock": {"enabled": True, "phase": phase, "time": time}}
                    out = env["cameo"](request)
                    self.assertEqual(out.get("dress"), "swim")
                    prompt = captured[-1]
                    for text in ("AUTHORITATIVE CURRENT CLOTHING: swim", "medical office",
                            "during a night shift or after a shift", "not your actual residence",
                            "No body or sexual descriptions", "never describe changing clothes",
                            "no assumed consent or romance", "otherwise wait outside", "AGE SAFETY RULES"):
                        self.assertIn(text, prompt)
                    self.assertNotIn("at your own home", prompt)
                    for loc in ("aidpost", "library"):
                        self.assertIsNone(env["cameo"](dict(request, location_id=loc)).get("dress"))
                        self.assertIn("AUTHORITATIVE CURRENT CLOTHING: pioneer", captured[-1])
                    if phase == "day":
                        for age in (18, 17, None, "27", True):
                            store.get_character = lambda cid: {"id": cid, "name": "Viola", "age": age, "persona": "I am 27."}
                            self.assertEqual(env["cameo"](request).get("dress"), "swim" if age == 18 else None)

    @unittest.skipIf(sys.version_info[0] < 3, "Server uses Python 3")
    def test_server_dress_only(self):
        for path in existing_paths((os.path.join(DEV, "server/main.py"), os.path.join(WORKSHOP, "server/main.py"))):
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
                llm.chat = lambda messages, **kwargs: captured.append(messages[0]["content"]) or "(smile) Hi [action:dress:swim]"
                for payload, expected in (
                    ({"romantic": True, "context": [{"who": "Player", "what": "us, put on a swimsuit"}]}, None),
                    ({"player_text": "sl, put on a swimsuit"}, None),
                    ({"player_text": "Ульяна, надень купальник"}, "swim"),
                    ({"player_text": "Ульяна, оденься"}, "cover"),
                    ({"dress": "swim", "dress_reason": "night_home"}, None),
                    ({"location_id": "dv_room", "dress": "swim", "dress_reason": "night_home"}, "swim"),
                    ({"location_id": "dv_room", "dress": "pioneer", "dress_reason": "night_home"}, None),
                    ({"location_id": "dv_room", "dress": "swim", "dress_reason": "night_home",
                      "player_text": "Ульяна, прикройся"}, "cover")):
                    request = {"character": "us", "location": "library", "location_id": "library"}
                    request.update(payload)
                    self.assertEqual(env["cameo"](request).get("dress"), expected)
                self.assertIn("AUTHORITATIVE CURRENT CLOTHING: swim", captured[-1])
                env["cameo"]({"character": "us", "location_id": "dv_room", "dress": "swim",
                              "dress_reason": "night_home"})
                self.assertIn("sleepwear visual proxy", captured[-1])
            finally:
                for key, value in previous.items():
                    if value is None:
                        sys.modules.pop(key, None)
                    else:
                        sys.modules[key] = value


if __name__ == "__main__":
    unittest.main()
