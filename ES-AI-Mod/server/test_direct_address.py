"""Offline regressions: execute server functions with fake dependencies, no config/API I/O."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch


WORKSHOP = Path(r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310\server\main.py")


class DirectAddressTests(unittest.TestCase):
    def test_both_servers(self):
        for path in (Path(__file__).with_name("main.py"), WORKSHOP):
            with self.subTest(server=str(path)):
                self.check_server(path)

    def check_server(self, path):
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        roster = json.loads(path.with_name("es_characters.json").read_text(encoding="utf-8-sig"))["characters"]
        store = types.ModuleType("characters_store")
        store.characters = lambda: roster
        store.get_character = lambda cid: next(c for c in roster if c["id"] == cid)
        store.map_emotion = lambda cid, emotion: emotion
        store.reply_rules = lambda ch: "rules"
        store.player_block = lambda: ""
        functions = {"normalize_location", "detect_location_in_text", "parse_action_tags",
                     "normalize_dress", "parse_cameo_tags", "resolve_direct_address",
                        "resolve_cameo_intent", "scene_prompt", "scene_encounter", "chat", "scene_event", "scene_diagnostics",
                         "cameo", "get_config_state", "_mask_key", "clock_prompt",
                         "game_clock_valid", "game_clock_settings"}
        nodes = [node for node in tree.body if (
            isinstance(node, ast.FunctionDef) and node.name in functions) or (
            isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                                                (t.id.startswith("_") or t.id in ("SCENE_BUILD", "SCENE_SOURCE"))
                                                for t in node.targets))]
        env = {"re": re, "json": json, "time": time, "cfg": {}, "os": os,
               "__file__": str(path), "BASE_DIR": str(path.parent),
               "config_loader": types.SimpleNamespace()}
        conversation = types.ModuleType("conversation")
        conversation.build_history_block = Mock(side_effect=lambda *args, **kwargs: [{"role": "system", "content": "test"}])
        conversation.add_exchange = Mock()
        conversation.maybe_compress = lambda *args: None
        llm = types.ModuleType("llm_client")
        llm.sanitize_in_character = lambda text: text
        llm.strip_prompt_leak = lambda text, prompt: text
        llm.quick_summarize = lambda *args: None
        env["threading"] = types.SimpleNamespace(Lock=threading.Lock,
            Thread=lambda **kwargs: types.SimpleNamespace(start=lambda: None))
        with patch.dict(sys.modules, {"characters_store": store, "conversation": conversation, "llm_client": llm}):
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
            events = []
            real_event = env["scene_event"]
            def fake_event(origin, status, ids=None, debug=None, **fields):
                events.append(dict(origin=origin, status=status, chosen_cameo=ids or [], **fields))
                if debug is not None:
                    debug.update(origin=origin, status=status, chosen_cameo=ids or [], **fields)
            env["scene_event"] = fake_event
            # File writes work even when stdout fails, for both storage policies.
            with tempfile.TemporaryDirectory() as directory:
                env["BASE_DIR"] = directory
                for loader in (types.SimpleNamespace(), types.SimpleNamespace(user_data_dir=lambda: directory)):
                    env["config_loader"] = loader
                    with patch("builtins.print", side_effect=OSError("no console")):
                        real_event("startup", "loaded")
                records = Path(directory, "scene_debug.log").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(records), 2)
                self.assertIn(str(path).replace("\\", "\\\\"), records[0])
                self.assertIn(env["SCENE_BUILD"], records[0])
            resolve = env["resolve_direct_address"]
            scene = {"enabled": True, "present": ["mt", "sl"], "available": [c["id"] for c in roster],
                     "invitable": [c["id"] for c in roster],
                     "capacity": 2, "location_id": "square"}
            examples = {
                "а вы Ольга Дмитриевна как - не против?": "mt",
                "Ольга Дмитриевна!": "mt", "ОЛЬГА ДМИТРИЕВНА!": "mt",
                "Привет Ульяна!": "us", "Привет, Ульяна!": "us",
                "Эй, Алиса, подойди к нам": "dv", "Алиса, подойди к нам": "dv",
                "Алис, ты как?": "dv", "Ульян!": "us", "Славь, тебе помочь?": "sl",
                "Лен, подойди": "un", "Мику!": "mi", "Жень!": "mz",
                "Виола!": "cs", "Юль!": "uv", "Электроник!": "el", "Шурик!": "sh",
                "Вожатая, вы не против?": "mt", "А ты Алиса как?": "dv",
                "Ладно. Ольга Дмитриевна!": "mt", "Алиса ты как?": "dv",
                "Лена тебе помочь?": "un", "Алиса подойди к нам": "dv",
                "Ольга   Дмитриевна!": "mt", "Алиса ... ты как?": "dv",
                "Алиса, подойди": "dv", "Алиса, ты тут?": "dv", "Алиса!": "dv",
                "Алиса, кажется, ты уже уходишь?": "dv",
                "Алиса, нет, подожди!": "dv",
            }
            for text, cid in examples.items():
                with self.subTest(text=text):
                    self.assertEqual(resolve(text, scene, "player"), [cid])
            passive = ["где Электроник?", "пошли к вожатой", "Алиса сказала",
                       "Алиса сказала, что ты придешь", "Алиса, сказала Лена",
                       "Ольга Дмитриевна здесь", "Вожатая идет к нам", "Вожатая сказала",
                       "Ленин!", "Ленинград", "Женька", "Ульяна ушла", "Я видел Алису",
                       "Там кто-то купается, давай присоединимся", "Алиса думает, что ты прав",
                       "Алиса, кажется, уже ушла.", "Алиса, наверное, сказала, что ты прав.",
                       "Электроник, похоже, уже ушёл.", "Алиса? Нет, я спрашивал про Лену.",
                       "Алиса? нет, не она.", "Алиса?! Нет! Я про Лену."]
            for text in passive:
                with self.subTest(passive=text):
                    self.assertIsNone(resolve(text, scene, "player"))
            self.assertEqual(resolve("Ольга Дмитриевна!", dict(scene, capacity=0), "un"), ["mt"])
            for capacity in (0, -1, "2", True, None):
                self.assertEqual(resolve("Ульяна!", dict(scene, capacity=capacity), "un"), [])
            self.assertIsNone(resolve("Ольга Дмитриевна!", scene, "mt"))
            self.assertEqual(resolve("Ульяна!", dict(scene, invitable=[]), "un"), [])
            for invalid in (None, {}, dict(scene, enabled=False), dict(scene, enabled=1)):
                self.assertEqual(resolve("Ольга Дмитриевна!", invalid, "un"), [])
            moving = dict(scene, destinations={"beach": ["us"]}, destination_capacity={"beach": 1})
            self.assertEqual(resolve("Ульяна!", moving, "un", "square", "beach"), ["us"])
            self.assertEqual(resolve("Ольга Дмитриевна!", moving, "un", "square", "beach"), ["mt"])
            self.assertEqual(resolve("Ульяна!", scene, "un", "square", "beach"), [])
            self.assertEqual(resolve("Ульяна!", dict(moving, destination_capacity={"beach": 0}), "un", "square", "beach"), [])
            named = "Алиса! Мику! Алиса!"
            self.assertEqual(resolve(named, scene, "un"), ["dv", "mi"])
            self.assertEqual(resolve(named, dict(scene, capacity=1), "un"), ["dv"])
            self.assertEqual(resolve(named, dict(scene, capacity=0, present=["mi"]), "un"), ["mi"])
            self.assertEqual(resolve(named, dict(scene, capacity=1, present=["mi"]), "un"), ["dv", "mi"])
            self.assertEqual(resolve(named, scene, "dv"), ["mi"])
            self.assertEqual(resolve(named, dict(moving, destination_capacity={"beach": 2}),
                                     "un", "square", "beach"), ["dv", "mi"])
            self.assertEqual(resolve(named, moving, "un", "square", "beach"), ["dv"])
            self.assertEqual(resolve(named, dict(scene, destination_capacity={"bus_stop": 2}),
                                     "un", "square", "bus_stop"), ["dv", "mi"])
            self.assertEqual(resolve("Алиса! Мику! Ульяна! Славя! Женя! Виола! Шурик!",
                                     dict(scene, capacity=6, max_extra=6, present=[]), "un"),
                             ["dv", "mi", "us", "sl", "mz", "cs"])
            self.assertEqual(env["parse_cameo_tags"]("Hi [action:cameo:mt]", scene, "un"), ("Hi", ["mt"]))
            self.assertEqual(env["parse_action_tags"]("Hi [action:goto:beach]"), ("Hi", "beach", None, None))
            beach = dict(scene, present=["un"], available=["us", "mi", "dv"], location_id="beach")
            for text, cid in (("Привет Шурик!", "sh"), ("Шурик привет! Пошли купаться!", "sh"),
                              ("а вон и Шурик подходит к нам", "sh"),
                              ("О Ольга Дмитриевна, привет!", "mt")):
                self.assertEqual(resolve(text, beach, "un"), [cid])
                self.assertEqual(resolve(text, dict(beach, capacity=0), "un"), [])
                self.assertEqual(resolve(text, dict(beach, enabled=False), "un"), [])
            for text in ("где Шурик?", "Шурик сказал", "а вон и Шурик сказал", "Шурик подходит к нам?",
                         "а вон и Шурик подходит к нам?"):
                self.assertIsNone(resolve(text, beach, "un"))
            self.assertEqual(env["parse_cameo_tags"]("Hi [action:cameo:sh,mt,sh]", beach, "un"),
                             ("Hi", ["sh", "mt"]))
            self.assertEqual(env["parse_cameo_tags"]("Hi [action:cameo:sh,mt]", dict(beach, capacity=1), "un"),
                             ("Hi", ["sh"]))

            calls = []
            # A location mention is not player movement, in either routing path.
            movement_scene = dict(scene, present=["mz", "dv"], traveling=["mz", "dv"],
                                  destination_capacity={"beach": 6, "square": 6})
            llm.chat = lambda messages, **kwargs: '{"cameo":[]}' if kwargs else "Я тебя слышу."
            for text in ("Женя тебе нравится пляж?", "где пляж", "Женя иди почитай книжку"):
                with self.subTest(location_mention=text):
                    out = env["chat"]({"character": "un", "text": text, "scene": movement_scene})
                    self.assertNotIn("goto", out)
                    self.assertIs(out["travel_all"], False)
                    if text.startswith("Женя"):
                        self.assertEqual(out["cameo"], ["mz"])
                        self.assertIs(out["suppress_main_reply"], True)
            for text, destination, collective in (("Алиса пошли на пляж", "beach", False),
                                                   ("пошлите все на площадь", "square", True),
                                                   ("let's go to the пляж", "beach", False)):
                with self.subTest(player_movement=text):
                    out = env["chat"]({"character": "un", "text": text, "scene": movement_scene})
                    self.assertEqual(out["goto"], destination)
                    self.assertIs(out["travel_all"], collective)
            llm.chat = lambda messages, **kwargs: '{"cameo":[]}' if kwargs else "Пойдём. [action:goto:beach]"
            out = env["chat"]({"character": "un", "text": "где пляж", "scene": movement_scene})
            self.assertEqual(out["goto"], "beach", "Model-generated goto remains unchanged")
            response = ["(нормально) Я подожду. [action:cameo:sl] [action:goto:library]"]

            def fake_chat(messages, **kwargs):
                calls.append((messages, kwargs))
                self.assertFalse(kwargs, "Direct address must not invoke the intent classifier")
                return response[0]

            llm.chat = fake_chat
            farewell_scene = dict(scene, present=["el", "sh", "mt"], capacity=0)
            with patch.object(llm, "chat", side_effect=AssertionError("farewell primary LLM")), \
                    patch.object(conversation, "build_history_block", side_effect=AssertionError("farewell history")), \
                    patch.object(conversation, "add_exchange", side_effect=AssertionError("farewell exchange")):
                for text in ("Электроник, ладно пока!", "пока Электроник", "Электроник, до встречи",
                             "Электроник, можешь идти", "до свидания Электроник", "Электроник уходи"):
                    for current, expected in ((farewell_scene, ["el"]),
                            (dict(scene, present=[], capacity=6), []),
                            (dict(scene, present=[], invitable=[]), []),
                            (None, []), (dict(farewell_scene, enabled=False), [])):
                        with self.subTest(farewell=text, present=expected, scene=current):
                            out = env["chat"]({"character": "un", "text": text, "scene": current})
                            self.assertTrue(out["ok"])
                            self.assertEqual(out["reply"], "")
                            self.assertEqual(out["cameo"], expected)
                            self.assertEqual(out["cameo_leave"], expected)
                            self.assertIs(out["cameo_requested"], True)
                            self.assertIs(out["suppress_main_reply"], True)
                for text, expected, leaving in (
                        ("Электроник, пока! Шурик, привет!", ["el", "sh"], ["el"]),
                        ("Электроник! Шурик, пока!", ["el", "sh"], ["sh"]),
                        ("Электроник и Шурик, до встречи!", ["el", "sh"], ["el", "sh"]),
                        ("Электроник, Шурик, пока!", ["el", "sh"], ["el", "sh"]),
                        ("Электроник пока! Шурик привет!", ["el", "sh"], ["el"])):
                    out = env["chat"]({"character": "un", "text": text,
                                        "scene": farewell_scene})
                    self.assertEqual(out["cameo"], expected)
                    self.assertEqual(out["cameo_leave"], leaving)
                out = env["chat"]({"character": "un", "text": "Электроник пока! Шурик привет!",
                                   "scene": dict(scene, present=["el"], capacity=1)})
                self.assertEqual(out["cameo"], ["el", "sh"])
                self.assertEqual(out["cameo_leave"], ["el"])
                out = env["chat"]({"character": "un", "text": "Электроник, привет!", "scene": farewell_scene})
                self.assertEqual(out["cameo"], ["el"])
                self.assertNotIn("cameo_leave", out)
                out = env["chat"]({"character": "un", "text": "Электроник, пока подожди", "scene": farewell_scene})
                self.assertNotIn("cameo_leave", out)
            captured_leave = []
            llm.chat = lambda messages, **kwargs: (captured_leave.append(messages) or
                "(нормально) До встречи! [action:dress:cover] [action:goto:beach] [action:cameo:sh]")
            out = env["cameo"]({"character": "el", "active": "Лена", "mode": "leave",
                                "context": [{"who": "Семён", "what": "Электроник, пока!"}]})
            self.assertEqual(out["reply"], "До встречи!")
            self.assertEqual(out["dress"], "cover")
            self.assertNotIn("goto", out)
            self.assertNotIn("cameo", out)
            prompt = captured_leave[0][0]["content"]
            self.assertIn("brief farewell", prompt)
            self.assertIn("не сочиняй реплики других персонажей", prompt)
            self.assertNotIn("можешь остаться", prompt)
            provider = types.ModuleType("tts_client")
            provider.available_providers = lambda: {}
            loader = types.ModuleType("config_loader")
            loader.keys = {}
            with patch.dict(sys.modules, {"tts_client": provider, "stt_client": provider, "config_loader": loader}):
                self.assertEqual(env["get_config_state"]()["config"]["cameo_max_extra"], 6)
                env["cfg"]["cameo_max_extra"] = 3
                self.assertEqual(env["get_config_state"]()["config"]["cameo_max_extra"], 3)
                env["cfg"].clear()
            self.assertEqual(env["scene_encounter"]({"capacity": 6})["max_extra"], 6)
            llm.chat = lambda messages, **kwargs: '{"cameo":[]}' if kwargs else "До встречи."
            out = env["chat"]({"character": "un", "text": "пока", "scene": farewell_scene})
            self.assertNotIn("cameo_leave", out)
            self.assertFalse(out.get("suppress_main_reply", False))
            for text, current, model_reply, destination in (
                    ("Лена пока", farewell_scene, "До встречи.", None),
                    ("Лена отведи туда", scene, "Пойдем. [action:goto:beach]", "beach"),
                    ("Электроник пока! Лена, ты как?", dict(scene, present=[]),
                     "Все хорошо. [action:cameo:el]", None)):
                with self.subTest(main_reply=text):
                    llm.chat = Mock(return_value=model_reply)
                    out = env["chat"]({"character": "un", "text": text, "scene": current})
                    self.assertTrue(out["ok"])
                    self.assertTrue(out["reply"])
                    self.assertFalse(out.get("suppress_main_reply", False))
                    self.assertNotIn("cameo_leave", out)
                    self.assertNotIn("cameo", out)
                    self.assertEqual(out.get("goto"), destination)
                    self.assertIsNone(out["scene_debug"]["direct_result"])
                    if text.startswith("Лена"):
                        self.assertEqual(out["scene_debug"]["address_reason"], "active")
                    llm.chat.assert_called_once()
            conversation.build_history_block.reset_mock()
            conversation.add_exchange.reset_mock()
            llm.chat = fake_chat
            for text, cid in (("Привет Шурик!", "sh"), ("Шурик привет! Пошли купаться!", "sh"),
                              ("а вон и Шурик подходит к нам", "sh"),
                              ("О Ольга Дмитриевна, привет!", "mt")):
                with contextlib.redirect_stdout(io.StringIO()):
                    out = env["chat"]({"character": "un", "text": text, "scene": beach, "location": "beach"})
                self.assertEqual(out["cameo"], [cid])
                self.assertIn(out.get("goto"), (None, "beach"))
                self.assertEqual(out["reply"], "")
                self.assertIs(out["suppress_main_reply"], True)
                self.assertIs(out["cameo_requested"], True)
            calls.clear()
            payload = {"character": "un", "text": "а вы Ольга Дмитриевна как - не против?",
                       "scene": dict(scene, capacity=0), "location": "square"}
            with contextlib.redirect_stdout(io.StringIO()) as diagnostics:
                out = env["chat"](payload)
            self.assertEqual(out["cameo"], ["mt"])
            self.assertNotIn("goto", out)
            self.assertEqual(len(calls), 0)
            conversation.build_history_block.assert_not_called()
            conversation.add_exchange.assert_not_called()
            self.assertEqual(out["scene_debug"]["origin"], "address")
            self.assertEqual(out["scene_debug"]["status"], "selected")
            self.assertEqual(out["scene_debug"]["source"], str(path))
            response[0] = "[action:cameo:sl]"
            with contextlib.redirect_stdout(io.StringIO()):
                out = env["chat"](payload)
            self.assertEqual(out["cameo"], ["mt"])
            self.assertEqual(out["reply"], "")
            self.assertEqual(len(calls), 0)
            response[0] = "Hi [action:cameo:sl]"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertNotIn("cameo", env["chat"](dict(payload, scene=None)))
                self.assertNotIn("cameo", env["chat"](dict(payload, text="Ульяна!")))
                out = env["chat"](dict(payload, text="Ульяна, пойдем на пляж!", scene=moving))
            self.assertEqual(out["cameo"], ["us"])
            self.assertEqual(out["goto"], "beach")
            for current, expected in ((scene, ["dv", "mi"]), (dict(scene, capacity=0, present=[]), [])):
                out = env["chat"](dict(payload, text=named, scene=current))
                self.assertEqual(out.get("cameo", []), expected)
                self.assertIs(out["cameo_requested"], True)
                self.assertEqual(out["scene_debug"]["direct_result"], expected)
                self.assertEqual(out["scene_debug"]["address_id"], "dv")
            out = env["chat"](dict(payload, text="Алиса! Мику! Пойдем на пляж!",
                                   scene=dict(moving, destination_capacity={"beach": 2})))
            self.assertEqual(out["cameo"], ["dv", "mi"])
            self.assertEqual(out["goto"], "beach")
            self.assertIs(out["suppress_main_reply"], True)
            # Successful routing must not depend on the primary model or write fake exchanges.
            with patch.object(llm, "chat", side_effect=AssertionError("primary LLM called")), \
                    patch.object(conversation, "build_history_block", side_effect=AssertionError("primary history built")), \
                    patch.object(conversation, "add_exchange", side_effect=AssertionError("fake exchange")):
                for text, current in ((named, scene), ("Ольга Дмитриевна!", dict(scene, capacity=0)),
                        ("Алиса! Мику! Ульяна! Славя! Женя! Виола!", dict(scene, capacity=6, max_extra=6, present=[])),
                        ("Ульяна, пойдем на пляж!", moving)):
                    routed = env["chat"](dict(payload, text=text, scene=current))
                    self.assertTrue(routed["ok"])
                    self.assertEqual(routed["reply"], "")
                    self.assertTrue(routed["cameo"])
                    self.assertIs(routed["suppress_main_reply"], True)
                    self.assertEqual(routed["scene_debug"]["status"], "selected")
                    self.assertEqual(events[-1]["resolution_origin"], "address")
            for current, active, reason in ((None, "un", "no-scene"),
                    (dict(scene, enabled=False), "un", "disabled"),
                    (dict(scene, capacity=0), "un", "capacity"),
                    (dict(scene, invitable=[]), "un", "not-invitable"),
                    (scene, "us", "active"), (scene, "un", "invitable")):
                out = env["chat"]({"character": active, "text": "Ульяна", "scene": current})
                debug = out["scene_debug"]
                self.assertEqual(debug["address_id"], "us")
                self.assertEqual(debug["address_reason"], reason)
                self.assertEqual(debug["direct_result"], ["us"] if reason == "invitable" else
                                 None if reason == "active" else [])
                self.assertEqual(debug["scene_received"], current is not None)
                self.assertEqual(out.get("suppress_main_reply", False), reason == "invitable")
                if reason != "invitable":
                    self.assertTrue(out["reply"])
                    self.assertEqual(conversation.add_exchange.call_args.args,
                                     (active, "Ульяна", out["reply"]))
            llm.chat = lambda *a, **k: (_ for _ in ()).throw(TimeoutError("secret provider body"))
            out = env["chat"](dict(payload, text="Ульяна!"))
            self.assertEqual(out["scene_debug"]["failure"], "TimeoutError")
            self.assertNotIn("secret", json.dumps(out["scene_debug"]))
            for raw, status, failure in (("not json", "failure", "JSONDecodeError"),
                    ('{"cameo":["unknown"]}', "no-selection", None)):
                llm.chat = lambda *a, **k: raw
                debug = {}
                self.assertEqual(env["resolve_cameo_intent"]("group", "", scene, "un", "square",
                    None, [], time.monotonic(), debug), [])
                self.assertEqual(debug["status"], status)
                self.assertEqual(debug.get("failure"), failure)
            debug = {}
            llm.chat = lambda *a, **k: (_ for _ in ()).throw(TimeoutError("secret"))
            env["resolve_cameo_intent"]("group", "", scene, "un", "square", None, [], time.monotonic(), debug)
            self.assertEqual(debug["failure"], "TimeoutError")
            self.assertEqual(env["parse_cameo_tags"]("Hi [action:cameo:unknown]", scene, "un"), ("Hi", []))
            # Generic observations remain delegated to the existing classifier.
            calls.clear()
            llm.chat = lambda messages, **kwargs: (calls.append(kwargs) or (
                '{"cameo":["us"]}' if kwargs else "Пойдем посмотрим."))
            with contextlib.redirect_stdout(io.StringIO()):
                out = env["chat"](dict(payload, text="Там кто-то купается, давай присоединимся", scene=moving))
            self.assertEqual(out["cameo"], ["us"])
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[1])
            # Observed groups may use the full roster, not the narrow bathhouse random pool.
            bath = dict(beach, location_id="bathhouse", available=["mt", "us"])
            captured = []

            def group_chat(messages, **kwargs):
                captured.append(json.loads(messages[1]["content"]))
                return '{"cameo":["sh","el"]}'

            llm.chat = group_chat
            with contextlib.redirect_stdout(io.StringIO()):
                selected = env["resolve_cameo_intent"]("Вон парни в бане, присоединимся", "", bath,
                                                      "un", "bathhouse", None, [], time.monotonic())
            self.assertEqual(selected, ["sh", "el"])
            self.assertEqual(captured[0]["available"], ["mt", "us"])
            self.assertIn("sh", captured[0]["eligible_ids"])
            self.assertIn("el", captured[0]["invitable"])
            self.assertNotIn("un", captured[0]["eligible_ids"])
            with contextlib.redirect_stdout(io.StringIO()):
                selected = env["resolve_cameo_intent"]("Вон парни", "", dict(bath, capacity=1),
                                                      "un", "bathhouse", None, [], time.monotonic())
            self.assertEqual(selected, ["sh"])

            # Sample the actual client weights, then accept the matching stub group.
            import random
            import builtins
            import textwrap
            client = path.parent.parent / "es_ai_cameo.rpy" if path == WORKSHOP else path.parents[1] / "mod/es_ai_cameo.rpy"
            blocks = re.split(r"^init [^\n]*python:\s*\n", client.read_text(encoding="utf-8-sig"), flags=re.M)[1:]
            draw = next(n for block in blocks for n in ast.parse(textwrap.dedent(block)).body
                        if isinstance(n, ast.FunctionDef) and n.name == "es_ai_cameo_group_size")
            rng_env = {"_es_random": random.Random(42), "_es_ai_cameo_builtins": builtins}
            exec(compile(ast.Module(body=[draw], type_ignores=[]), str(client), "exec"), rng_env)
            candidates = ["sh", "el", "dv", "us", "mi", "sl"]
            large = dict(scene, present=[], capacity=6, max_extra=6, group_size=5,
                         destination_capacity={"beach": 6, "library": 1},
                         destination_group_sizes={"beach": 4, "library": 1})
            sizes = set()
            for _ in range(150):
                size = rng_env["es_ai_cameo_group_size"](6)
                sizes.add(size)
                current = dict(large, group_size=size)
                def suggested_chat(messages, **kwargs):
                    if kwargs:
                        data = json.loads(messages[1]["content"])
                        self.assertEqual(kwargs["override_max_tokens"], 100)
                        return json.dumps({"cameo": candidates[:data["group_size"]]})
                    return "Hi"
                llm.chat = suggested_chat
                out = env["chat"]({"character": "un", "text": "Join the nearby group",
                                   "location": "square", "scene": current})
                self.assertEqual(out["cameo"], candidates[:size])
                self.assertNotIn("[", out["reply"])
                self.assertEqual(out["scene_debug"]["group_size"], size)
                tagged = "Hi [action:cameo:%s]" % ",".join(candidates[:size])
                self.assertEqual(env["parse_cameo_tags"](tagged, current, "un"), ("Hi", candidates[:size]))
            self.assertTrue({3, 4, 5} <= sizes)
            llm.chat = suggested_chat
            self.assertEqual(env["resolve_cameo_intent"]("group", "", large, "un", "square",
                "beach", [], time.monotonic()), candidates[:4])
            tags = "Hi [action:cameo:%s,mt] [cameo:unknown]" % ",".join(candidates)
            self.assertEqual(env["parse_cameo_tags"](tags, large, "un"), ("Hi", candidates))
            self.assertEqual(env["parse_cameo_tags"](tags, dict(large, capacity=1, present=["el"]), "un"),
                             ("Hi", ["sh", "el"]))
            self.assertEqual(env["parse_cameo_tags"](tags, dict(large, capacity=0, present=candidates), "un"),
                             ("Hi", candidates))
            self.assertEqual(env["parse_cameo_tags"](tags, large, "un", "library", "square"), ("Hi", ["sh"]))
            for invalid in (0, -1, True, "6", None):
                blocked = dict(large, destination_capacity={"beach": invalid})
                self.assertEqual(resolve("Ульяна!", blocked, "un", "square", "beach"), [])
                self.assertEqual(env["parse_cameo_tags"](tags, blocked, "un", "beach", "square"), ("Hi", []))
            self.assertEqual(resolve("Ульяна!", large, "un", "square", "beach"), ["us"])
            self.assertEqual(env["scene_encounter"](dict(large, capacity=99))["capacity"], 6)
            self.assertEqual(env["scene_encounter"](dict(large, max_extra=3))["capacity"], 3)
            llm.chat = lambda *a, **k: json.dumps({"cameo": candidates})
            self.assertEqual(env["resolve_cameo_intent"]("named group", "", dict(large, group_size=0),
                "un", "square", None, [], time.monotonic()), candidates)
            llm.chat = lambda *a, **k: json.dumps({"cameo": candidates + ["mt"]})
            self.assertEqual(env["resolve_cameo_intent"]("group", "", large,
                "un", "square", None, [], time.monotonic()), [])

    def test_both_clients(self):
        import builtins
        import random
        import textwrap

        for root in (Path(__file__).parents[1] / "mod", WORKSHOP.parent.parent):
            with self.subTest(client=str(root)):
                source = root.joinpath("es_ai_cameo.rpy").read_text(encoding="utf-8-sig")
                # Only execute Python init blocks; no Ren'Py, settings or network access.
                blocks = re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:]
                trees = [ast.parse(textwrap.dedent(block)) for block in blocks]
                names = {"es_ai_scene_snapshot", "es_ai_try_cameo", "es_ai_maybe_cameo",
                          "es_ai_cameo_capacity", "es_ai_cameo_group_size", "es_ai_cameo_deliver_group",
                          "es_ai_recent_push"}
                nodes = [n for tree in trees for n in tree.body if
                         (isinstance(n, ast.FunctionDef) and n.name in names) or
                         (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                          t.id == "ES_AI_CAMEO_BY_LOC" for t in n.targets))]
                roster = json.loads(WORKSHOP.with_name("es_characters.json").read_text(encoding="utf-8-sig"))["characters"]
                st = {"cameo_max_extra": 2, "cameo_stay": True, "cameo_stay_lines": 2,
                      "cameo_ctx": 70, "cameo_freq": 100}
                shown = [{"id": "un"}]
                spoken = []
                logs = []
                enabled = [True]
                env = {"_es_ai_cameo_builtins": builtins, "_es_random": random,
                       "basestring": str, "long": int, "ES_AI_CHARS": [(c["id"], c["name"], "") for c in roster],
                       "ES_AI_SHOWN": shown, "ES_AI_LOC_CUR": ["beach"], "ES_AI_CAMEO_CD": [0],
                         "ES_AI_CAMEO_COOLDOWN": 5, "ES_AI_CAMEO_ACTIVE": [], "ES_AI_CAMEO_NEARBY": {},
                        "ES_AI_LOC_OWNERS": {}, "ES_AI_CAMEO_PAIRS": [],
                       "ES_AI_CAMEO_P_COMPANION": 0, "ES_AI_ROMANCEABLE": [],
                       "es_ai_read_cameo_settings": lambda: st, "es_ai_cameo_on": lambda: enabled[0],
                       "es_ai_recent_snapshot": lambda n: [], "es_ai_recent_push": lambda *a: None,
                       "es_ai_cameo_name": lambda cid: cid, "es_ai_log": logs.append,
                       "es_ai_cameo_line": lambda *a, **k: {"reply": "Hi"},
                       "es_ai_cameo_enter": lambda cid, emo, **k: shown.append({"id": cid}),
                        "es_ai_cameo_speak": lambda cid, *a: spoken.append(cid),
                       "es_ai_cameo_tick": lambda *a: None, "es_ai_is_romantic_moment": lambda *a: False,
                       "es_ai_cameo_chance": lambda *a: 1,
                       "renpy": types.SimpleNamespace(with_statement=lambda *a: None), "dissolve": None}
                exec(compile(ast.Module(body=nodes, type_ignores=[]), str(root), "exec"), env)
                env.update({"unicode": str, "ES_AI_RECENT_LINES": [], "ES_AI_RECENT_MAX": 70})
                env["ES_AI_LOCATION_INDEX"] = dict.fromkeys(list(env["ES_AI_CAMEO_BY_LOC"]) + ["bus_stop"], {})
                snapshot = env["es_ai_scene_snapshot"]("un")
                self.assertIn("bus_stop", snapshot["destination_capacity"])
                self.assertIn("bus_stop", snapshot["destination_group_sizes"])
                self.assertEqual(set(snapshot["destination_capacity"]), set(env["ES_AI_LOCATION_INDEX"]))
                self.assertEqual(set(snapshot["destination_group_sizes"]), set(env["ES_AI_LOCATION_INDEX"]))
                self.assertNotIn("bus_stop", snapshot["destinations"])
                self.assertEqual(set(snapshot["available"]),
                                 {"us", "mi", "dv", "sl", "el", "sh", "mz", "mt", "cs"})
                self.assertIn("sh", snapshot["invitable"])
                self.assertNotIn("un", snapshot["invitable"])
                env["es_ai_try_cameo"]("un", "Шурик!", {"reply": "", "suppress_main_reply": True,
                    "cameo_requested": True, "cameo": ["sh"]})
                self.assertEqual(spoken, ["sh"])
                self.assertEqual(env["ES_AI_RECENT_LINES"][0], {"who": "Игрок", "what": "Шурик!"})
                self.assertFalse(any(line["who"] == "un" for line in env["ES_AI_RECENT_LINES"]))
                self.assertIn("un", [g["id"] for g in shown])
                for present in (["un", "el", "sh"], ["un", "el"]):
                    shown[:] = [{"id": cid} for cid in present]
                    spoken.clear()
                    modes = []
                    def cameo_line(cid, *args, **kwargs):
                        modes.append((cid, kwargs.get("mode")))
                        return {"reply": "Hi"}
                    def leave(cid):
                        shown[:] = [g for g in shown if g["id"] != cid]
                    with patch.dict(env, {"es_ai_cameo_line": cameo_line,
                            "es_ai_cameo_leave": leave,
                            "es_ai_cameo_tick": lambda *a: self.fail("mixed request ticked"),
                            "es_ai_maybe_cameo": lambda *a: self.fail("mixed request randomized")}):
                        env["es_ai_try_cameo"]("un", "Электроник пока! Шурик привет!",
                            {"reply": "", "suppress_main_reply": True, "cameo_requested": True,
                             "cameo": ["el", "sh"], "cameo_leave": ["el"]})
                    self.assertEqual(spoken, ["el", "sh"])
                    self.assertEqual(modes[0], ("el", "leave"))
                    self.assertEqual({g["id"] for g in shown}, {"un", "sh"})
                shown[:] = [{"id": "un"}]
                spoken.clear()
                logs.clear()
                env["es_ai_try_cameo"]("un", "", {"cameo": ["sh", "sh", "mt", "bogus", "un"]})
                self.assertTrue(spoken)
                self.assertTrue(set(spoken) <= {"sh", "mt"})
                self.assertTrue({"sh", "mt"} <= {g["id"] for g in shown})
                self.assertIn('"status": "missing-scene-debug"', logs[0])
                spoken.clear()
                env["es_ai_try_cameo"]("un", "", {"cameo": ["el", "sh"]})
                self.assertEqual(spoken, ["sh"], "Present calls work even at full capacity")
                enabled[0] = False
                spoken.clear()
                env["es_ai_try_cameo"]("un", "", {"cameo": ["sh"]})
                self.assertEqual(spoken, [])
                logs.clear()
                env["es_ai_try_cameo"]("un", "", {"scene_debug": {"build": "test", "source": "x" * 1000,
                    "direct_result": [], "status": "blocked", "api_body": "secret"}})
                received = json.loads(logs[0].split("scene server: ", 1)[1])
                self.assertEqual(received["direct_result"], [])
                self.assertEqual(len(received["source"]), 512)
                self.assertNotIn("api_body", received)
                with patch.dict(env, {"es_ai_cameo_tick": lambda *a: self.fail("blocked request ticked"),
                                      "es_ai_maybe_cameo": lambda *a: self.fail("blocked request randomized")}):
                    enabled[0] = True
                    env["es_ai_try_cameo"]("un", "", {"cameo_requested": True})
                    env["es_ai_try_cameo"]("un", "", {"cameo_requested": True, "cameo": []})
                    cleared = []
                    env["es_ai_cameo_clear"] = lambda: cleared.append(True)
                    st["cameo_stay"] = False
                    env["es_ai_try_cameo"]("un", "", {"cameo_requested": True})
                    self.assertEqual(cleared, [True])
                    st["cameo_stay"] = True
                original_flag = env["es_ai_cameo_on"]
                env["es_ai_cameo_on"] = lambda: (_ for _ in ()).throw(RuntimeError("test failure"))
                env["es_ai_try_cameo"]("un", "", {})
                self.assertIn("cameo error: RuntimeError", logs[-1])
                self.assertIn("Traceback (most recent call last)", logs[-1])
                env["es_ai_cameo_on"] = original_flag
                enabled[0] = True
                shown[:] = [{"id": "un"}]
                for _ in range(20):
                    env["ES_AI_CAMEO_CD"][0] = 0
                    self.assertTrue(set(env["es_ai_maybe_cameo"]("un", False)) <= set(snapshot["available"]))
                # Explicit destination arrivals suppress random arrivals for known IDs outside its pool.
                loc_source = root.joinpath("es_ai_locations.rpy").read_text(encoding="utf-8-sig")
                blocks = re.split(r"^init [^\n]*python:\s*\n", loc_source, flags=re.M)[1:]
                func = next(n for block in blocks for n in ast.parse(textwrap.dedent(block)).body
                            if isinstance(n, ast.FunctionDef) and n.name == "es_ai_apply_actions")
                arrivals = []
                env.update({"ES_AI_LOC_CUR": ["square"], "ES_AI_LOC_LAST_CHAR": ["un"],
                            "ES_AI_LOC_LAST_EMO": [None], "es_ai_location_id": lambda x: x,
                            "es_ai_location_from_dialog": lambda *a: None,
                            "es_ai_set_location": lambda *a, **k: arrivals.append(k["cameo_arrive"]),
                            "es_ai_dress_from_context": lambda *a: None, "es_ai_location": lambda: {}})
                exec(compile(ast.Module(body=[func], type_ignores=[]), str(root), "exec"), env)
                env["es_ai_apply_actions"]({"goto": "beach", "cameo": ["sh"]})
                self.assertEqual(arrivals, [False])

    def test_chat_client_speech_guard(self):
        import textwrap

        for root in (Path(__file__).parents[1] / "mod", WORKSHOP.parent.parent):
            source = root.joinpath("es_ai_chat.rpy").read_text(encoding="utf-8-sig")
            # Execute the actual action/speech/cameo statements from the Ren'Py label.
            block = source.split('    $ es_ai_apply_actions(_res, _inp)', 1)[1].split('    jump es_ai_chat_input', 1)[0]
            block = '    $ es_ai_apply_actions(_res, _inp)' + block
            code = textwrap.dedent(re.sub(r"(?m)^(\s*)\$ ", r"\1", block))
            for result, expected in (({"reply": "", "suppress_main_reply": True}, ["actions", "cameo"]),
                    ({"reply": "normal"}, ["actions", "say", "cameo"]),
                    ({"reply": "blocked", "cameo_requested": True}, ["actions", "say", "cameo"])):
                with self.subTest(client=str(root), result=result):
                    calls = []
                    env = {"_res": result, "_inp": "player line", "es_ai_char_id": "un",
                           "_clock_lines": 0, "es_ai_clock_complete": lambda *a: None,
                           "es_ai_apply_actions": lambda *a: calls.append("actions"),
                           "es_ai_say_girl": lambda *a: calls.append("say"),
                           "es_ai_try_cameo": lambda *a: calls.append("cameo")}
                    exec(compile(code, str(root / "es_ai_chat.rpy"), "exec"), env)
                    self.assertEqual(calls, expected)


if __name__ == "__main__":
    unittest.main()
