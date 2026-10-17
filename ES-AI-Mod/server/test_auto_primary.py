"""Automatic primary transitions, offline against both installations."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import copy
import json
import os
import re
import sys
import time
import types
import unittest
from unittest.mock import Mock, mock_open, patch

from test_cameo_clothing import ROOTS, load
from test_scene_memory import module_at
from test_primary_scene_switch import PrimarySwitchTests
from test_settings_save_state import SettingsSaveStateTests
from test_player_identity import DEV, WORKSHOP


class AutoPrimaryTests(unittest.TestCase):
    def test_latest_sl_group_farewell_visit_timeline(self):
        # Copied verbatim from the latest sl.json user fields, not model narration.
        sequence = ("ПОшли к Лене", "Ладно, я вас покидаю. Пойду к Электронику.", "А ты что сюда пришла?")
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, location_id="un_room", present=["sl", "un"], nearby=[],
                         destination_capacity=dict(club_room=2), npc_activity_enabled=False)
            grouped = resolver.resolve(sequence[0], scene, "sl", lambda t: None, True)
            self.assertEqual(grouped["goto"], "un_room")
            self.assertIsNone(grouped["visit_primary"])
            self.assertIsNone(grouped["switch_primary"])
            self.assertFalse(grouped["farewell_primary"])
            for verb in ("Пойду", "Пошёл", "Пошел", "Схожу", "Отправлюсь"):
                for target, name in (("el", "Электронику"), ("sh", "Шурику")):
                    text = "%s к %s." % (verb, name)
                    with self.subTest(root=root, text=text):
                        travel = resolver.resolve(text, scene, "sl", lambda t: None, True)
                        self.assertEqual(travel["visit_primary"]["id"], target)
                        self.assertEqual(travel["encounter_direction"], "visit")
                        self.assertFalse(travel["player_travel_blocked"])
                        self.assertEqual(travel["travel_with"], [])
            for text in ("Не пойду к Электронику", "Пойду к Электронику?", "Может пойду к Электронику",
                         'Он сказал: "Пойду к Электронику"', "Он пошёл к Электронику",
                         "Пойду к тебе", "Пойду к Незнакомцу"):
                self.assertIsNone(resolver.resolve(text, scene, "sl", lambda t: None, True)["visit_primary"], text)
            for text in ("я не покидаю вас", '"я вас покидаю"', "Он говорит: я вас покидаю",
                         "Он вас покидает", "Может, я вас покидаю?", "Если я вас покидаю"):
                self.assertFalse(resolver.resolve(text, scene, "sl", lambda t: None, True)["farewell_primary"], text)
            farewell = resolver.resolve("Ладно, я вас покидаю.", scene, "sl", lambda t: None, True)
            self.assertTrue(farewell["farewell_primary"])
            self.assertIsNone(farewell["switch_primary"])
            self.assertIsNone(farewell["visit_primary"])

            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            forbidden = Mock(side_effect=AssertionError("Explicit visit must precede semantic/cameo classifiers"))
            llm, saved = Mock(side_effect=["До завтра!", "Привет! [cameo:el]", "Я здесь занимаюсь схемой."]), Mock()
            histories = Mock(side_effect=lambda cid, *a, **kw: [dict(role="system", content="identity=" + cid)])
            modules = {
                "selected_companions": resolver, "npc_activity": module_at(root, "npc_activity"),
                "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None),
                    parse_choices=lambda t: (t, None), bind_selection=Mock(), acknowledge_direct=Mock(),
                    response_metadata=lambda *a, **kw: {}),
                "conversation": types.SimpleNamespace(build_history_block=histories, add_exchange=saved, maybe_compress=Mock()),
                "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t,
                    strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid),
                    map_emotion=lambda *a: "normal")}
            env.update(detect_location_in_text=lambda t: None, normalize_location=lambda t: t,
                scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                resolve_direct_address=forbidden, resolve_cameo_intent=forbidden, resolve_primary_intent=forbidden,
                scene_prompt=lambda *a: "", clock_prompt=lambda *a: "",
                _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile("NEVER"),
                _ACTION_CAMEO_RE=re.compile(r"\[cameo:[^]]+\]"),
                parse_action_tags=lambda t: (t, None, None, None), parse_cameo_tags=forbidden,
                threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            with patch.dict(sys.modules, modules):
                result = json.loads(json.dumps(env["chat"](dict(character="sl", text=sequence[1], location="un_room", scene=scene))))
            self.assertEqual(result["id"], "el")
            self.assertEqual(result["visit_primary"], dict(id="el", location_id="club_room"))
            self.assertEqual(result["goto"], "club_room")
            self.assertEqual(result["departure"]["id"], "sl")
            self.assertFalse(result.get("cameo"))
            self.assertFalse(result.get("end_conversation"))
            self.assertEqual(result["travel_with"], [])
            self.assertTrue(result["scene_debug"]["visit_recognized"])
            self.assertEqual([call.args[0] for call in histories.call_args_list], ["sl", "el"])
            self.assertIn("ORIGINAL location", llm.call_args_list[0].args[0][0]["content"])
            self.assertIn("source group stay at the origin", llm.call_args_list[1].args[0][0]["content"])
            self.assertEqual([call.args[0] for call in saved.call_args_list], ["sl", "el"])

            client = PrimarySwitchTests().environment(root)
            client["es_ai_pick_id"]("sl")
            client["ES_AI_LOC_CUR"][0] = "un_room"
            client["ES_AI_CAMEO_NEARBY"].clear()
            client["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True)]
            client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            client["renpy"].scene = lambda: None
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read().split("label es_ai_chat_input:\n", 1)[1].split("\n################################################################################", 1)[0]
            lines, spoken = [], []
            for line in source.splitlines():
                stripped = line.lstrip()
                indent = line[:len(line) - len(stripped)]
                if stripped.startswith("$ "):
                    lines.append(indent + stripped[2:])
                elif stripped.startswith(("if ", "else:", "default=es_ai_voice_text")):
                    lines.append(line)
                elif stripped.startswith("jump "):
                    lines.append(indent + "jump(%r)" % stripped[5:])
            class Jump(Exception): pass
            def jump(label):
                raise Jump(label)
            def say(cid, *args, **kw):
                spoken.append((cid, client["ES_AI_LOC_CUR"][0], kw))
                if cid == "sl":
                    self.assertNotIn("el", [g["id"] for g in client["ES_AI_SHOWN"]])
                    self.assertNotIn("el", [g["id"] for g in client["ES_AI_CAMEO_NEARBY"].get("un_room", [])])
            client.update(jump=jump, es_ai_clock_sync=lambda: None, es_ai_char_name=lambda cid: cid,
                es_ai_voice_text="", es_ai_story_input_take=lambda: sequence[1], es_ai_ask_girl=lambda *a: result,
                es_ai_say_girl=say, es_ai_try_cameo=lambda *a: None, es_ai_clock_complete=lambda *a: None,
                es_ai_delivery_flush=lambda: None, es_ai_story_choices_menu=lambda: None)
            with self.assertRaises(Jump):
                exec(compile(__import__("textwrap").dedent("\n".join(lines)), "<latest sl visit>", "exec"), client)
            self.assertEqual([(cid, loc) for cid, loc, kw in spoken], [("sl", "un_room"), ("el", "club_room")])
            self.assertTrue(spoken[0][2]["wait_voice"])
            self.assertEqual(client["es_ai_char_id"], "el")
            self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["el"])
            self.assertEqual({g["id"] for g in client["ES_AI_CAMEO_NEARBY"]["un_room"]}, {"sl", "un"})
            env.update(resolve_direct_address=lambda *a: None, resolve_cameo_intent=lambda *a: [],
                       parse_cameo_tags=lambda t, *a, **kw: (t, []))
            with patch.dict(sys.modules, modules):
                follow = env["chat"](dict(character=client["es_ai_char_id"], text=sequence[2], location="club_room",
                    scene=dict(enabled=True, location_id="club_room", present=["el"], nearby=[])))
            self.assertEqual(follow["id"], "el")
            self.assertEqual(histories.call_args.args[0], "el")
            self.assertNotIn("departure", follow)

    def test_visit_direction_exact_timeline(self):
        for root in ROOTS:
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            llm, saved = Mock(return_value="reply [cameo:dv]"), Mock()
            modules = {
                "selected_companions": module_at(root, "selected_companions"),
                "npc_activity": module_at(root, "npc_activity"),
                "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None),
                    parse_choices=lambda t: (t, None), bind_selection=Mock(), acknowledge_direct=Mock(),
                    response_metadata=lambda *a, **kw: dict(end_conversation=True, suppress_main_reply=True)),
                "conversation": types.SimpleNamespace(build_history_block=lambda *a, **kw: [dict(role="system", content="identity")],
                    add_exchange=saved, maybe_compress=Mock()),
                "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t,
                    strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid),
                    map_emotion=lambda *a: "normal")}
            no_cameo = Mock(side_effect=AssertionError("Visit must never reach cameo classification"))
            env.update(detect_location_in_text=lambda t: None, normalize_location=lambda t: t,
                scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(), resolve_direct_address=no_cameo,
                resolve_cameo_intent=no_cameo, resolve_primary_intent=no_cameo,
                scene_prompt=lambda *a: "", clock_prompt=lambda *a: "",
                _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile(r"NEVER"),
                _ACTION_CAMEO_RE=re.compile(r"\[cameo:[^]]+\]"),
                parse_action_tags=lambda t: (t, None, None, None), parse_cameo_tags=no_cameo,
                threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            text = "Я пойду до Алисы, пока!"
            payload = dict(character="sl", text=text, location="square", scene=dict(enabled=True,
                location_id="square", present=["sl"], nearby=[], destination_nearby={},
                destination_capacity={"dv_room": 2}, npc_activity_enabled=False))
            with patch.dict(sys.modules, modules):
                result = json.loads(json.dumps(env["chat"](payload)))
            self.assertEqual(result["id"], "dv")
            self.assertEqual(result["goto"], "dv_room")
            self.assertEqual(result["visit_primary"], dict(id="dv", location_id="dv_room"))
            self.assertTrue(result["cameo_requested"])
            self.assertFalse(result.get("cameo"))
            self.assertNotIn("[cameo:", result["reply"])
            self.assertFalse(result.get("end_conversation"))
            self.assertEqual(llm.call_count, 2)
            self.assertEqual([call.args[0] for call in saved.call_args_list], ["sl", "dv"])
            client = PrimarySwitchTests().environment(root)
            client["es_ai_pick_id"]("sl")
            client["ES_AI_LOC_CUR"][0] = "square"
            client["ES_AI_CAMEO_NEARBY"].clear()
            client["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal")]
            client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            client["renpy"].scene = lambda: None
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read().split("label es_ai_chat_input:\n", 1)[1].split("\n################################################################################", 1)[0]
            lines = []
            for line in source.splitlines():
                stripped = line.lstrip()
                indent = line[:len(line) - len(stripped)]
                if stripped.startswith("$ "):
                    lines.append(indent + stripped[2:])
                elif stripped.startswith(("if ", "else:", "default=es_ai_voice_text")):
                    lines.append(line)
                elif stripped.startswith("jump "):
                    lines.append(indent + "jump(%r)" % stripped[5:])
            spoken = []
            class Jump(Exception): pass
            def jump(label):
                raise Jump(label)
            def say(cid, *args, **kw):
                spoken.append((cid, client["ES_AI_LOC_CUR"][0], kw))
                if cid == "sl":
                    self.assertNotIn("dv", [g["id"] for g in client["ES_AI_SHOWN"]])
                    self.assertNotIn("dv", [g["id"] for g in client["ES_AI_CAMEO_NEARBY"].get("square", [])])
            client.update(jump=jump, es_ai_clock_sync=lambda: None, es_ai_char_name=lambda cid: cid,
                es_ai_voice_text="", es_ai_story_input_take=lambda: text, es_ai_ask_girl=lambda *a: result,
                es_ai_say_girl=say, es_ai_try_cameo=lambda *a: None, es_ai_clock_complete=lambda *a: None,
                es_ai_delivery_flush=lambda: None, es_ai_story_choices_menu=lambda: None)
            with self.assertRaises(Jump) as jumped:
                exec(compile(__import__("textwrap").dedent("\n".join(lines)), "<visit timeline label>", "exec"), client)
            self.assertEqual(str(jumped.exception), "es_ai_chat_input")
            self.assertEqual([(cid, loc) for cid, loc, kw in spoken], [("sl", "square"), ("dv", "dv_room")])
            self.assertTrue(spoken[0][2]["wait_voice"])
            self.assertEqual(client["es_ai_char_id"], "dv")
            self.assertEqual(client["es_ai_who_name"], "dv")
            self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["dv"])
            self.assertEqual([g["id"] for g in client["ES_AI_CAMEO_NEARBY"]["square"]], ["sl"])
            # The very next request is bound to Alice, never the former primary.
            env["resolve_direct_address"] = lambda *a: None
            env["parse_cameo_tags"] = lambda t, *a, **kw: (env["_ACTION_CAMEO_RE"].sub("", t), [])
            env["resolve_cameo_intent"] = lambda *a: []
            modules["story_events"].response_metadata = lambda *a, **kw: {}
            with patch.dict(sys.modules, modules):
                follow = env["chat"](dict(character=client["es_ai_char_id"], text="пошли до тебя",
                    location="dv_room", scene=dict(enabled=True, present=["dv"], location_id="dv_room")))
            self.assertEqual(follow["id"], "dv")
            self.assertEqual(follow["goto"], "dv_room")
            self.assertNotIn("departure", follow)
            # Known remote location cannot be masked by an arrival/invitation.
            env["resolve_direct_address"] = no_cameo
            for change in (dict(destination_nearby={"beach": ["dv"]}),
                           dict(present=["sl", "dv"], destination_nearby={"square": ["dv"]}),
                           dict(destination_capacity={}), dict(enabled=False)):
                blocked = copy.deepcopy(payload)
                blocked["scene"].update(change)
                before = llm.call_count
                with patch.dict(sys.modules, modules):
                    response = env["chat"](blocked)
                self.assertTrue(response["visit_blocked"])
                self.assertTrue(response["cameo_requested"])
                self.assertFalse(response.get("cameo"))
                self.assertNotIn("goto", response)
                self.assertEqual(llm.call_count, before)
                self.assertEqual(response["scene_debug"]["encounter_direction"], "visit")
            env["cfg"]["scene_auto_primary"] = False
            disabled_payload = copy.deepcopy(payload)
            disabled_payload["text"] = "я пойду до Алисы"
            with patch.dict(sys.modules, modules):
                disabled = env["chat"](disabled_payload)
            self.assertEqual(disabled["id"], "sl")
            self.assertFalse(disabled["end_conversation"])
            self.assertNotIn("goto", disabled)
            self.assertNotIn("visit_primary", disabled)

    def test_direction_and_retrospective_farewell(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["sl"], nearby=[])
            for text in ("Я пойду до Алисы, пока!", "я до Алисы пойду", "я пойду к Алисе"):
                for enabled in (True, False):
                    result = resolver.resolve(text, scene, "sl", lambda t: None, enabled)
                    self.assertEqual(result["visit_primary"]["id"], "dv")
                    self.assertEqual(result["encounter_direction"], "visit")
                    self.assertIsNone(result["switch_primary"])
            invitation = resolver.resolve("позови Алису сюда", scene, "sl", lambda t: None, True)
            self.assertEqual(invitation["encounter_direction"], "invite")
            self.assertIsNone(invitation["visit_primary"])
            for text in ("где Алиса", "я не пойду до Алисы", "я пойду до Алисы?",
                         "Он сказал: я пойду до Алисы", 'Он сказал: «я же попрощался с тобой»',
                         "он попрощался с тобой", "я не попрощался с тобой"):
                result = resolver.resolve(text, scene, "sl", lambda t: None, True)
                self.assertIsNone(result["visit_primary"], text)
                self.assertFalse(result["farewell_primary"], text)
            for text in ("я же попрощался с тобой", "я уже попрощался с тобой"):
                result = resolver.resolve(text, scene, "sl", lambda t: None, True,
                    ["Я пойду до Алисы, пока!", "Ладно"])
                self.assertFalse(result["farewell_primary"])
                self.assertTrue(result["retrospective_farewell"])
                self.assertIsNone(result["visit_primary"])
                self.assertIsNone(result["switch_primary"])
            for follow in ("пошли до тебя", "Пока"):
                pending = resolver.resolve(follow, scene, "sl", lambda t: None, True,
                    ["Я пойду до Алисы, пока!", "Ладно"])
                self.assertEqual(pending["visit_primary"]["id"], "dv", follow)
                self.assertEqual(pending["context_source"], "prior")

    def test_retrospective_keeps_current_npc_without_planning_or_invitations(self):
        for root in ROOTS:
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            forbidden = Mock(side_effect=AssertionError("Past goodbye must not plan actions"))
            llm = Mock(return_value="О чём ты? [cameo:dv]")
            saved = Mock()
            activity = module_at(root, "npc_activity")
            activity.decide = forbidden
            modules = {
                "selected_companions": module_at(root, "selected_companions"), "npc_activity": activity,
                "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None),
                    parse_choices=lambda t: (t, None), bind_selection=Mock(), acknowledge_direct=Mock(),
                    response_metadata=lambda *a, **kw: dict(end_conversation=True, switch_primary="dv",
                        goto="dv_room", suppress_main_reply=True)),
                "conversation": types.SimpleNamespace(build_history_block=lambda *a, **kw: [dict(role="system", content="identity")],
                    get_history=forbidden, add_exchange=saved, maybe_compress=Mock()),
                "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t,
                    strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid),
                    map_emotion=lambda *a: "normal")}
            env.update(detect_location_in_text=lambda t: None, normalize_location=lambda t: t,
                scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                resolve_direct_address=forbidden, resolve_cameo_intent=forbidden, resolve_primary_intent=forbidden,
                scene_prompt=lambda *a: "", clock_prompt=lambda *a: "",
                _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile(r"NEVER"),
                _ACTION_CAMEO_RE=re.compile(r"\[cameo:[^]]+\]"),
                parse_action_tags=lambda t: (t, None, None, None),
                parse_cameo_tags=lambda t, *a, **kw: (re.sub(r"\[cameo:[^]]+\]", "", t), ["dv"]),
                threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            for recent in ([], [dict(who="Игрок", what="Я пойду до Алисы, пока!")],
                           [dict(who="Игрок", what="хочу поболтать с Мику")]):
                for enabled in (True, False):
                    env["cfg"]["scene_auto_primary"] = enabled
                    with patch.dict(sys.modules, modules):
                        response = env["chat"](dict(character="sl", text="Я же попрощался с тобой",
                            location="square", scene=dict(enabled=True, present=["sl", "mi"], context=recent)))
                    self.assertEqual(response["id"], "sl")
                    self.assertEqual(saved.call_args.args[0], "sl")
                    self.assertTrue(response["scene_debug"]["retrospective_farewell"])
                    self.assertTrue(response["movement_blocked"])
                    self.assertTrue(response["cameo_requested"])
                    self.assertFalse(response["npc_calls"])
                    for key in ("end_conversation", "switch_primary", "visit_primary", "goto", "departure", "cameo", "suppress_main_reply"):
                        self.assertFalse(response.get(key), (root, key, response))
                    self.assertIn("PAST goodbye", llm.call_args.args[0][0]["content"])
                    client = PrimarySwitchTests().environment(root)
                    client["es_ai_pick_id"]("sl")
                    client["ES_AI_LOC_CUR"][0] = "square"
                    client["es_ai_apply_actions"](json.loads(json.dumps(response)), "Я же попрощался с тобой")
                    self.assertEqual(client["es_ai_char_id"], "sl")
                    self.assertEqual(client["ES_AI_LOC_CUR"][0], "square")
            self.assertEqual(llm.call_count, 6)
            forbidden.assert_not_called()

    def test_retrospective_with_new_current_command_is_not_blocked(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["sl"])
            for command in ("а теперь пойду к Алисе", "а теперь я пойду к Алисе"):
                text = "Я же попрощался с тобой, " + command
                self.assertFalse(resolver.retrospective_farewell(text))
                result = resolver.resolve(text, scene, "sl", lambda t: None, True)
                self.assertEqual(result["visit_primary"]["id"], "dv")
            result = resolver.resolve("Я же попрощался с тобой, а теперь я пойду к Алисе",
                scene, "sl", lambda t: None, True, ["хочу поболтать с Мику"])
            self.assertEqual(result["visit_primary"]["id"], "dv")
            self.assertEqual(result["context_source"], "current")
            for command in ("пока", "я пойду один", "иди спать"):
                result = resolver.resolve("Я же попрощался с тобой, " + command, scene, "sl", lambda t: None, True)
                self.assertFalse(result.get("retrospective_farewell"))
                self.assertTrue(result["farewell_primary"])

    def test_context_positive_intentions_and_exclusions(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["sl", "sh", "mi", "un"])
            for text, target in (("Славя спасибо, иди наверное спать, я Шурику помогу.", "sh"),
                                 ("я помогу Шурику", "sh"), ("я хочу помочь Лене", "un"),
                                 ("хочу поболтать с Мику", "mi"), ("я пообщаюсь с Леной", "un")):
                result = resolver.resolve(text, scene, "sl", lambda t: None, True)
                self.assertEqual(result["switch_primary"], target, (root, text, result))
                self.assertEqual(result["context_source"], "current")
                self.assertEqual(result["cameo_aside"], ["sl"])
                self.assertIsNone(resolver.resolve(text, scene, "sl", lambda t: None, False)["switch_primary"])
                nearby = resolver.resolve(text, dict(enabled=True, present=["sl"], nearby=[target]), "sl", lambda t: None, True)
                self.assertEqual(nearby["switch_primary"], target)
            for text in ("Шурику нужна помощь", "Славя Шурику поможет", "я не помогу Шурику",
                         'Он сказал: «я Шурику помогу»', "я Шурику помогу?", "если я помогу Шурику",
                         "хочу поболтать с Мику и Леной", "я поговорю с Мику и Леной", "Пока", "Надо заняться делами"):
                result = resolver.resolve(text, scene, "sl", lambda t: None, True)
                self.assertIsNone(result["switch_primary"], (text, result))
                self.assertIsNone(result["visit_primary"], (text, result))

    def test_context_prior_player_intention_is_bounded_and_consumed(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["sl", "mi", "sh"])
            resolve = lambda active, recent: resolver.resolve("Пока", scene, active, lambda t: None, True, recent)
            self.assertEqual(resolve("sl", ["хочу поболтать с Мику"])["switch_primary"], "mi")
            self.assertEqual(resolve("sl", ["я хочу помочь Шурику", "Ладно"])["context_source"], "prior")
            for active, recent in (("mi", ["хочу поболтать с Мику"]),
                                   ("sh", ["Славя спасибо, иди наверное спать, я Шурику помогу."]),
                                   ("sl", ["Славя спасибо, иди наверное спать, я Шурику помогу."]),
                                   ("sl", ["хочу поболтать с Мику", "Один", "Два"]),
                                   ("mi", ["я помогу Шурику", "хочу поболтать с Мику"])):
                self.assertIsNone(resolve(active, recent)["switch_primary"], (active, recent))
            self.assertIsNone(resolver.resolve("Привет", scene, "sl", lambda t: None, True,
                                              ["хочу поболтать с Мику"])["switch_primary"])

    def test_context_json_actual_label_keeps_new_binding(self):
        for root in ROOTS:
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            history = Mock(side_effect=lambda *a, **kw: [dict(role="system", content="own identity")])
            saved, llm = Mock(), Mock(return_value="help response")
            modules = {"selected_companions": module_at(root, "selected_companions"),
                       "npc_activity": module_at(root, "npc_activity"),
                       "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                       "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None), parse_choices=lambda t: (t, None), bind_selection=Mock(), response_metadata=lambda *a, **kw: dict(end_conversation=True, suppress_main_reply=True), acknowledge_direct=Mock()),
                       "conversation": types.SimpleNamespace(build_history_block=history, get_history=lambda cid: ([dict(role="user", content="хочу поболтать с Мику")], ""), add_exchange=saved, maybe_compress=Mock()),
                       "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t, strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                       "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid), map_emotion=lambda *a: "normal")}
            env.update(detect_location_in_text=lambda t: None, normalize_location=lambda t: t,
                       scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                       resolve_direct_address=lambda *a: None, scene_prompt=lambda *a: "", clock_prompt=lambda *a: "",
                       _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile(r"NEVER"),
                       _ACTION_CAMEO_RE=re.compile(r"NEVER"), parse_action_tags=lambda t: (t, None, None, None),
                       parse_cameo_tags=lambda t, *a, **kw: (t, []),
                       resolve_cameo_intent=Mock(side_effect=AssertionError("No classifier for handoff")),
                       resolve_primary_intent=Mock(return_value=None),
                       threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            text = "Славя спасибо, иди наверное спать, я Шурику помогу."
            payload = dict(character="sl", text=text, location="library", scene=dict(enabled=True, location_id="library", present=["sl", "sh"]))
            with patch.dict(sys.modules, modules):
                response = env["chat"](payload)
                self.assertEqual(history.call_args.args[0], "sh")
                self.assertEqual(saved.call_args.args[0], "sh")
                self.assertIn("FORMER partner only", llm.call_args.args[0][0]["content"])
                self.assertEqual(response["scene_debug"]["context_source"], "current")
                self.assertFalse(response.get("end_conversation"))
                self.assertFalse(response.get("suppress_main_reply"))
                # Replay the latest public encounter, then the actual input-label below.
                modules["story_events"].response_metadata = lambda *a, **kw: dict(end_conversation=True, suppress_main_reply=True)
                text = "Славя, пока! Я с Ольгой Дмитриевной пообщаюсь."
                context = [dict(who="Игрок", what="Пошли до Ольги - она у себя"),
                           dict(who="Славя", what="Пойдём, я тебя провожу к Ольге Дмитриевне."),
                           dict(who="Ольга Дмитриевна", what="Заходите, Славя, Колян, только тихо — я уже собиралась спать. Что у вас случилось?")]
                load(os.path.join(server, "main.py"), env, {"resolve_primary_intent"}, rpy=False)
                modules["characters_store"].characters = lambda: [dict(id=cid, name=cid) for cid in ("sl", "mt", "sh", "mi")]
                llm.side_effect = ['{"handoff":"mt","direction":"local"}', "Хорошо, до завтра!", "Добрый вечер. Что ты хотел обсудить?"]
                response = env["chat"](dict(character="sl", text=text, location="mt_room",
                    scene=dict(enabled=True, location_id="mt_room", present=["sl", "mt"], context=context)))
                self.assertEqual(response["id"], "mt", (response, llm.call_args_list, env["scene_event"].call_args_list))
                self.assertEqual(response["switch_primary"], "mt")
                self.assertFalse(response.get("end_conversation"))
                self.assertFalse(response.get("suppress_main_reply"))
                self.assertEqual(saved.call_args.args[0], "mt")
                self.assertEqual(history.call_args.args[0], "mt")
                self.assertEqual(response["scene_debug"]["context_source"], "semantic")
                self.assertEqual(llm.call_args_list[-3].kwargs["override_timeout"] <= 8, True)
                self.assertEqual(response["departure"]["id"], "sl")
                self.assertEqual(response["departure"]["reply"], "Хорошо, до завтра!")
                self.assertEqual(saved.call_args_list[-2].args, ("sl", text, "Хорошо, до завтра!"))
                self.assertIn("newly selected", llm.call_args.args[0][0]["content"])
                llm.side_effect = ['{"handoff":"mt","direction":"visit"}']
                semantic_visit = env["resolve_primary_intent"](text, dict(present=["mt"]), "sl", time.monotonic())
                self.assertEqual(semantic_visit, dict(target="mt", direction="visit"))
                llm.side_effect = ['{"handoff":"mt","direction":"local"}']
                self.assertIsNone(env["resolve_primary_intent"](text, dict(present=[]), "sl", time.monotonic()))
                for raw in ('{"handoff":"intruder"}', '{"handoff":[]}', '{"cameo":["mt"]}',
                            '{"handoff":"sl"}', '{"handoff":"mt","direction":"invite"}',
                            '{"handoff":"mt"}', 'not json'):
                    llm.side_effect = [raw]
                    self.assertIsNone(env["resolve_primary_intent"](text, dict(present=["mt"]), "sl", time.monotonic()))
                llm.side_effect = TimeoutError("private provider failure")
                self.assertIsNone(env["resolve_primary_intent"](text, dict(present=["mt"]), "sl", time.monotonic()))
                env["resolve_primary_intent"] = Mock(return_value=None)
                llm.side_effect = None
                for context, target in (([dict(who="Игрок", what="хочу поболтать с Мику")], "mi"),
                                        ([dict(who="Игрок", what="я хочу помочь Шурику")], "sh")):
                    prior = env["chat"](dict(character="sl", text="Пока", scene=dict(enabled=True, present=["sl", "mi", "sh"], context=context)))
                    self.assertEqual(prior["switch_primary"], target)
                    self.assertEqual(prior["scene_debug"]["context_source"], "prior")
                personal = env["chat"](dict(character="sl", text="Пока", scene=dict(enabled=True, present=["sl", "mi"])))
                self.assertEqual(personal["switch_primary"], "mi")
                cleared = env["chat"](dict(character="sl", text="Пока", scene=dict(enabled=True, present=["sl", "mi"], context=[])))
                self.assertTrue(cleared["end_conversation"])
                # Generated NPC context must not become the player's intent.
                modules["conversation"].get_history = lambda cid: ([], "")
                modules["story_events"].response_metadata = lambda *a, **kw: {}
                no_intent = env["chat"](dict(character="sl", text="Пока", scene=dict(enabled=True, present=["sl", "sh"], context=[dict(who="Славя", what="я хочу помочь Шурику")])))
                self.assertTrue(no_intent["end_conversation"])
                remote = copy.deepcopy(payload)
                remote["scene"].update(present=["sl"], destination_capacity={"club_room": 2})
                visit = env["chat"](remote)
                self.assertEqual(visit["visit_primary"], dict(id="sh", location_id="club_room"))
                self.assertEqual(visit["goto"], "club_room")
                self.assertFalse(visit.get("end_conversation"))
                visitor = PrimarySwitchTests().environment(root)
                visitor["ES_AI_CHARS"].append(("sh", "sh", ""))
                visitor["es_ai_pick_id"]("sl")
                visitor["renpy"].scene = lambda: None
                visitor["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                visitor["es_ai_apply_actions"](json.loads(json.dumps(visit)), text)
                self.assertEqual(visitor["es_ai_char_id"], "sh")
                self.assertEqual(visitor["ES_AI_LOC_CUR"][0], "club_room")
                self.assertIn("sl", [g["id"] for g in visitor["ES_AI_CAMEO_NEARBY"]["library"]])
                self.assertNotIn("sl", [g["id"] for g in visitor["ES_AI_SHOWN"]])
                blocked_payload = copy.deepcopy(remote)
                blocked_payload["scene"]["destination_nearby"] = dict(square=["sh"])
                blocked = env["chat"](blocked_payload)
                self.assertTrue(blocked["visit_blocked"])
                self.assertFalse(blocked["end_conversation"])
                self.assertNotIn("goto", blocked)
                self.assertEqual(blocked["scene_debug"]["context_blocked"], "visit-unavailable")
                env["cfg"]["npc_activity_enabled"] = True
                remote["scene"]["activity"] = {"sh": {}}
                remote["clock"] = dict(enabled=True, time="12:00")
                at_work = env["chat"](remote)
                self.assertEqual(at_work["id"], "sh")
                remote["clock"]["time"] = "23:00"
                away = env["chat"](remote)
                self.assertTrue(away["visit_blocked"])
                self.assertFalse(away["end_conversation"])
                env["cfg"]["npc_activity_enabled"] = False
                env["cfg"]["scene_auto_primary"] = False
                disabled = env["chat"](payload)
                self.assertTrue(disabled["end_conversation"])
                self.assertNotIn("switch_primary", disabled)
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read().split("label es_ai_chat_input:\n", 1)[1].split("\n################################################################################", 1)[0]
            lines = []
            for line in source.splitlines():
                stripped = line.lstrip()
                indent = line[:len(line) - len(stripped)]
                if stripped.startswith("$ "):
                    lines.append(indent + stripped[2:])
                elif stripped.startswith(("if ", "else:")) or stripped.startswith("default=es_ai_voice_text"):
                    lines.append(line)
                elif stripped.startswith("jump "):
                    lines.append(indent + "jump(%r)" % stripped[5:])
            client = PrimarySwitchTests().environment(root)
            client["ES_AI_CHARS"].extend([("sh", "sh", ""), ("mt", "mt", "")])
            client["es_ai_pick_id"]("sl")
            client["ES_AI_SHOWN"].append(dict(id="mt", emo="normal", cameo=True))
            client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            response = json.loads(json.dumps(response))
            events = []
            spoken_at = []
            def say(cid, *args, **kwargs):
                events.append(cid)
                spoken_at.append((cid, client["ES_AI_LOC_CUR"][0], client["ES_AI_LOC_LAST_CHAR"][0], kwargs))
            class Jump(Exception): pass
            def jump(label):
                events.append(label)
                raise Jump(label)
            client.update(jump=jump, es_ai_clock_sync=lambda: None, es_ai_char_name=lambda cid: cid,
                          es_ai_voice_text="", es_ai_story_input_take=lambda: text,
                          es_ai_ask_girl=lambda *a: response,
                          es_ai_say_girl=say,
                          es_ai_try_cameo=lambda *a: None, es_ai_clock_complete=lambda *a: None,
                          es_ai_delivery_flush=lambda: None, es_ai_story_choices_menu=lambda: None)
            with self.assertRaises(Jump):
                exec(compile(__import__("textwrap").dedent("\n".join(lines)), "<context chat label>", "exec"), client)
            self.assertEqual(events, ["sl", "mt", "es_ai_chat_input"])
            self.assertEqual(spoken_at[0][:3], ("sl", "library", "sl"))
            self.assertTrue(spoken_at[0][3]["wait_voice"])
            self.assertEqual(spoken_at[1][0], "mt")
            self.assertEqual(client["es_ai_char_id"], "mt")
            self.assertEqual(client["es_ai_who_name"], "mt")
            self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "mt")

    def test_departure_without_replacement(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            for text in ("Пока", "Ладно пока Спокойной ночи Я до Электроника пошёл",
                         "Славя спасибо, иди наверное спать, я Шурику помогу.",
                         "я от тебя ухожу", "я пойду один", "мне пора", "до встречи", "иди домой Славя"):
                for enabled in (False, True):
                    result = resolver.resolve(text, dict(present=["sl"]), "sl", lambda t: None, enabled)
                    self.assertTrue(result.get("farewell_primary"), (root, text, result))
            for text in ("Мику, пока", "Пока, Мику", "я сказал пока", "Он сказал: «Пока»",
                         "пока мы здесь посидим", "Славя сказала до встречи", "я не пойду один"):
                self.assertFalse(resolver.resolve(text, dict(present=["sl", "mi"]), "sl", lambda t: None, True).get("farewell_primary"), text)

    def test_actual_chat_label_detaches_after_delivery(self):
        # Execute the actual input-label Python statements and branch structure.
        for root in ROOTS:
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read().split("label es_ai_chat_input:\n", 1)[1].split("\n################################################################################", 1)[0]
            lines = []
            for line in source.splitlines():
                stripped = line.lstrip()
                indent = line[:len(line) - len(stripped)]
                if stripped.startswith("$ "):
                    lines.append(indent + stripped[2:])
                elif stripped.startswith(("if ", "else:")):
                    lines.append(line)
                elif stripped.startswith("jump "):
                    lines.append(indent + "jump(%r)" % stripped[5:])
                elif stripped.startswith("default=es_ai_voice_text"):
                    lines.append(line)
            client = PrimarySwitchTests().environment(root)
            client["es_ai_pick_id"]("sl")
            client["ES_AI_CLOCK"]["lines"] = 0
            events = []
            class Jump(Exception): pass
            def jump(label):
                events.append(label)
                raise Jump(label)
            client.update(jump=jump, es_ai_clock_sync=lambda: None,
                          es_ai_char_name=lambda cid: cid, es_ai_voice_text="",
                          es_ai_story_input_take=lambda: "Пока",
                          es_ai_ask_girl=lambda *a: json.loads('{"ok":true,"id":"sl","reply":"Bye","end_conversation":true}'),
                          es_ai_say_girl=lambda *a, **kw: events.append("farewell"),
                          es_ai_try_cameo=lambda *a: self.fail("No extra requests after farewell"),
                          es_ai_clock_complete=lambda *a: events.append("clock"),
                          es_ai_delivery_flush=lambda: events.append("flush"),
                          es_ai_story_choices_menu=lambda: self.fail("No stale choices"))
            with self.assertRaises(Jump):
                exec(compile(__import__("textwrap").dedent("\n".join(lines)), "<actual chat label>", "exec"), client)
            self.assertEqual(events, ["farewell", "clock", "flush", "es_ai_pick"])
            self.assertIsNone(client["ES_AI_LOC_LAST_CHAR"][0])
            self.assertIsNone(client["es_ai_char_id"])
            self.assertFalse(client["ES_AI_SHOWN"])
            client["es_ai_pick_id"]("el")
            self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "el")

    def test_failed_client_handoff_keeps_farewell(self):
        for root in ROOTS:
            for action in (dict(switch_primary="el"),
                           dict(visit_primary=dict(id="el", location_id="club_room"), goto="club_room")):
                client = PrimarySwitchTests().environment(root)
                client["es_ai_pick_id"]("sl")
                client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=False)
                result = json.loads(json.dumps(dict(action, farewell_primary="sl", reply="host response")))
                client["es_ai_apply_actions"](result, "Пока, я пошёл")
                self.assertTrue(result["end_conversation"])
                self.assertTrue(result["suppress_main_reply"])
                client["es_ai_detach_primary"]()
                self.assertIsNone(client["ES_AI_LOC_LAST_CHAR"][0])
                self.assertNotIn("sl", [g["id"] for g in client["ES_AI_CAMEO_NEARBY"].get("library", [])])

    def test_privacy_departure_is_local_and_cancels_pending(self):
        for root in ROOTS:
            client = PrimarySwitchTests().environment(root)
            client["ES_AI_LOC_CUR"][0] = "un_room"
            client["ES_AI_LOC_LAST_CHAR"][0] = "mi"
            client["ES_AI_SHOWN"][:] = [dict(id="mi", emo="normal"), dict(id="sl", cameo=True, emo="normal")]
            client["ES_AI_CAMEO_NEARBY"].update(un_room=[dict(id="un")], square=[dict(id="el"), dict(id="un")])
            client["ES_AI_ACTIVITY_PENDING"] = {cid: {} for cid in ("sl", "un", "el")}
            client["es_ai_apply_actions"](json.loads(json.dumps(dict(
                privacy=True, scene_depart=["sl", "un", "el", "mi", "bogus", {}]))), "Мику, хочу побыть наедине с тобой")
            self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["mi"])
            self.assertEqual(client["ES_AI_CAMEO_NEARBY"]["un_room"], [])
            self.assertEqual([g["id"] for g in client["ES_AI_CAMEO_NEARBY"]["square"]], ["el", "un"])
            self.assertEqual(client["ES_AI_ACTIVITY_PENDING"], {"el": {}})
            self.assertEqual(set(client["ES_AI_SCENE_ABSENT"]["un_room"]), {"sl", "un"})
            snapshot = client["es_ai_scene_snapshot"]("mi", dict(cameo_max_extra=6, npc_activity_enabled=False))
            self.assertFalse(set(snapshot["available"] + snapshot["invitable"]) & {"sl", "un"})
            client["es_ai_activity_exchange"] = Mock(side_effect=AssertionError("privacy must not advance invitations"))
            client["es_ai_try_cameo"]("mi", "hello", dict(privacy=True, cameo_requested=True))
            client["es_ai_activity_exchange"].assert_not_called()

    def test_privacy_intent_locality_and_toggle(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            text = "Славя, я хочу побыть наедине с Мику"
            for scene in (dict(present=["sl", "mi", "un"]),
                          dict(present=["sl", "un"], nearby=["mi"])):
                result = resolver.resolve(text, scene, "sl", lambda t: "beach", True)
                self.assertEqual(result["switch_primary"], "mi")
                self.assertEqual(result["scene_depart"], ["sl", "un"])
                self.assertIsNone(result["goto"])
                self.assertIsNone(result["visit_primary"])
                disabled = resolver.resolve(text, scene, "sl", lambda t: "beach", False)
                self.assertIsNone(disabled["switch_primary"])
                self.assertEqual(disabled["scene_depart"], [])
                self.assertTrue(disabled["movement_blocked"])
                self.assertEqual(disabled["primary_reason"], "privacy-disabled")
            result = resolver.resolve("Мику, хочу побыть наедине с тобой",
                                      dict(present=["mi", "sl", "un"]), "mi", lambda t: "beach", False)
            self.assertIsNone(result["switch_primary"])
            self.assertEqual(result["scene_depart"], ["sl", "un"])
            self.assertFalse(result["movement_blocked"])
            remote = resolver.resolve(text, dict(present=["sl", "un"], available=["mi"],
                                                 invitable=["mi"], pending_calls={"mi": {}}), "sl", lambda t: "beach", True)
            self.assertIsNone(remote["switch_primary"])
            self.assertIsNone(remote["visit_primary"])
            self.assertEqual(remote["primary_reason"], "privacy-target-not-local")
            for text in ("не хочу быть наедине с Мику", "Славя хотела бы побыть наедине с Мику?",
                         'Он сказал: «я хочу побыть наедине с Мику»',
                         "если я хочу побыть наедине с Мику", "я хочу побыть наедине с Мику?",
                         "Славя хочет побыть наедине с Мику"):
                result = resolver.resolve(text, dict(present=["sl", "mi", "un"]), "sl", lambda t: None, True)
                self.assertIsNone(result["switch_primary"], text)
                self.assertFalse(result.get("privacy"), text)

    def test_visit_requires_intent_not_mentions(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            for text in ("где Электроник?", "я не пойду к Электронику", "я пойду к Электронику?",
                         "хочу к Электронику", "Электроник в клубе", 'Он сказал: «я пойду к Электронику»'):
                result = resolver.resolve(text, dict(present=["mz"]), "mz", lambda t: None, True)
                self.assertIsNone(result["visit_primary"], text)

    def test_latest_zhenya_local_directed_handoff(self):
        phrases = ("Электроник, оставим Женю.", "Электроник, пошли к тебе.", "пошли, Электроник!")
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            for text in phrases:
                for nearby in (False, True):
                    scene = dict(present=["mz"] if nearby else ["mz", "el"], nearby=["el"] if nearby else [])
                    result = resolver.resolve(text, scene, "mz", lambda t: None, True)
                    self.assertEqual(result["switch_primary"], "el", (root, text, scene))
                    self.assertEqual(result["goto"], "club_room" if "к тебе" in text else None)
                    client = PrimarySwitchTests().environment(root)
                    client["ES_AI_CHARS"].append(("el", "el", ""))
                    record = dict(id="el", emo="normal", cameo=True)
                    if nearby:
                        client["ES_AI_CAMEO_NEARBY"]["library"] = [record]
                    else:
                        client["ES_AI_SHOWN"].append(record)
                    client["renpy"].scene = lambda: None
                    client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                    client["es_ai_apply_actions"](json.loads(json.dumps(result)), text)
                    self.assertEqual(client["es_ai_char_id"], "el")
                    self.assertEqual(client["es_ai_who_name"], "el")
                    client["es_ai_apply_actions"]({}, "Привет")
                    self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "el")
                    self.assertIsNone(resolver.resolve(text, scene, "mz", lambda t: None, False)["switch_primary"])
                    remote = dict(present=["mz"], available=["el"], pending_calls={"el": {}}, activity={"el": dict(status="busy")})
                    self.assertIsNone(resolver.resolve(text, remote, "mz", lambda t: None, True)["switch_primary"])
            for text in ("Электроник, не пошли к тебе", "Электроник, пошли к тебе?",
                         "Женя сказала что Электроник, пошли к тебе", 'Он сказал: «пошли, Электроник!»',
                         "Электроник, оставим Женю?", "пошли, Электроник и Шурик!"):
                self.assertIsNone(resolver.resolve(text, dict(present=["mz", "el", "sh"]), "mz", lambda t: None, True)["switch_primary"], text)

    def test_live_release_and_explicit_context_handoff(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            for text in ("Славя, оставь нас", "я дальше пойду с Электроником",
                         "Славя останься тут, я поговорю с Электроником"):
                for local in (dict(present=["sl", "el"]), dict(present=["sl"], nearby=["el"])):
                    result = resolver.resolve(text, local, "sl", lambda t: None, True)
                    self.assertEqual(result["switch_primary"], "el", (root, text, local))
                    self.assertEqual(result["cameo_aside"], ["sl"])
                    self.assertIsNone(result["goto"])
                    self.assertFalse(result["movement_blocked"])
                    self.assertIsNone(resolver.resolve(text, local, "sl", lambda t: None, False)["switch_primary"])
            negatives = ("где Электроник", "я не пойду с Электроником", "я дальше пойду с Электроником?",
                         'Он сказал: «я дальше пойду с Электроником»', "Славя, оставь нас?",
                         "Славя, не оставь нас", "Славя, оставайся тут",
                         "Славя, оставь нас. Я поговорю с Шуриком")
            for text in negatives:
                self.assertIsNone(resolver.resolve(text, dict(present=["sl", "el"]), "sl", lambda t: None, True)["switch_primary"], text)
            for scene in (dict(present=["sl", "el", "sh"]),
                          dict(present=["sl"], available=["el"], invitable=["el"],
                               pending_calls={"el": dict(wait_turns=0)}, activity={"el": dict(status="pending")})):
                self.assertIsNone(resolver.resolve("Славя, оставь нас", scene, "sl", lambda t: None, True)["switch_primary"])
            remote = resolver.resolve("ладно я оставлю тебя, пойду назад на площаль к Электронику",
                                      dict(present=["sl"]), "sl", lambda t: None, True)
            self.assertIsNone(remote["switch_primary"])

    def test_live_stay_inflections_and_disabled_toggle(self):
        text = "Славя останься тут, я схожу с Леной к площади"
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            for enabled in (True, False):
                result = resolver.resolve(text, dict(present=["sl", "un"], nearby=[]),
                                          "sl", lambda t: "square" if "площади" in t else None, enabled)
                self.assertEqual(result["switch_primary"], "un" if enabled else None)
                self.assertEqual(result["movement_blocked"], not enabled)
                self.assertEqual(result["cameo_aside"], ["sl"] if enabled else [])
            env = PrimarySwitchTests().environment(root)
            env["ES_AI_LOC_CUR"][0] = "stage_big"
            env["ES_AI_LOC_LAST_CHAR"][0] = "sl"
            env["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True)]
            env["renpy"].scene = lambda: None
            env["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            env["es_ai_apply_actions"](dict(switch_primary="un", goto="square", cameo_aside=["sl"], travel_with=[]), text)
            self.assertEqual(env["es_ai_char_id"], "un")
            self.assertEqual(env["es_ai_who_name"], "un")
            self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["un"])
            self.assertEqual([g["id"] for g in env["ES_AI_CAMEO_NEARBY"]["stage_big"]], ["sl"])
            self.assertNotIn("sl", [g["id"] for g in env["ES_AI_CAMEO_NEARBY"].get("square", [])])

    def test_label_rebinds_before_reply_and_next_input(self):
        for root in ROOTS:
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
                source = stream.read()
            for label, apply in (("es_ai_chat_input", "es_ai_apply_actions(_res, _inp)"),
                                 ("es_ai_chat_initiative", "es_ai_apply_actions(_ini)")):
                block = source.split("label " + label + ":", 1)[1].split("\nlabel ", 1)[0]
                after = block.split(apply, 1)[1]
                self.assertLess(after.index("es_ai_char_id = ES_AI_LOC_LAST_CHAR[0]"), after.index("es_ai_say_girl("))
                self.assertIn("es_ai_who_name = es_ai_char_name(es_ai_char_id)", after)
            block = source.split("label es_ai_chat_input:", 1)[1]
            self.assertLess(block.index("es_ai_char_id = ES_AI_LOC_LAST_CHAR[0]"), block.index("renpy.input("))

    def test_resolver_matrix(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(present=["mz", "sl", "dv"], nearby=["mi"])
            detect = lambda text: "beach" if "пляж" in text else None
            text = "Женя оставайся читать а мы со Славей пойдём на пляж"
            for enabled in (False, None, 1, "true"):
                self.assertTrue(resolver.resolve(text, scene, "mz", detect, enabled)["movement_blocked"])
            examples = [(text, "sl", []),
                        ("Женя оставайся читать а мы со Славей пойдём к Лене", "sl", []),
                        ("Женя оставайся читать а мы с Мику и Славей пойдём на пляж", "mi", ["sl"]),
                        ("Женя оставайся читать а мы все пойдём на пляж", "sl", ["dv"]),
                        ("Женя оставайся читать. Алиса оставайся. Пойдём все на пляж", "sl", []),
                        ("Женя оставайся читать а мы с Шуриком пойдём на пляж", None, []),
                        ("Женя оставайся читать а мы пойдём на пляж", None, []),
                        ("Женя оставайся читать а мы со Славей пойдём неизвестно куда", None, []),
                        ("Женя оставайся читать. Славя пока. Пойдём со Славей на пляж", None, [])]
            for message, switch, extras in examples:
                with self.subTest(root=root, message=message):
                    result = resolver.resolve(message, scene, "mz", detect, True)
                    self.assertEqual(result["switch_primary"], switch)
                    self.assertEqual(result["travel_with"], extras)
                    self.assertEqual(result["movement_blocked"], switch is None)
                    if switch:
                        self.assertIn("mz", result["cameo_aside"])
            result = resolver.resolve("Пойдём со Славей на пляж", scene, "mz", detect, True)
            self.assertIsNone(result["switch_primary"])
            self.assertEqual(result["travel_with"], ["sl"])

    def test_client_transition_and_rejection(self):
        for root in ROOTS:
            for nearby in (False, True):
                env = PrimarySwitchTests().environment(root)
                env["renpy"].scene = lambda: None
                env["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                record = dict(id="sl", emo="normal", cameo=True, dress="swim",
                              dress_reason="player", dress_location="library", tag="sl normal swim")
                if nearby:
                    env["ES_AI_CAMEO_NEARBY"]["library"] = [record]
                else:
                    env["ES_AI_SHOWN"].append(record)
                env["es_ai_cameo_enter"]("mi", "normal", stay=True)
                captured = []
                enter = env["es_ai_girl_enter"]
                def observe(cid, emotion):
                    enter(cid, emotion)
                    captured.append(env["ES_AI_DRESS"][0])
                env["es_ai_girl_enter"] = observe
                env["es_ai_apply_actions"](dict(switch_primary="sl", goto="beach", travel_all=True,
                    travel_with=["mi"], cameo_aside=["mz"]), "Женя оставайся а мы со Славей пойдём на пляж")
                self.assertEqual(captured[0], "swim")
                self.assertEqual(env["es_ai_char_id"], "sl")
                self.assertEqual(env["ES_AI_LOC_LAST_CHAR"][0], "sl")
                self.assertEqual(env["ES_AI_LOC_CUR"][0], "beach")
                self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"sl", "mi"})
                self.assertIn("mz", [g["id"] for g in env["ES_AI_CAMEO_NEARBY"]["library"]])
                self.assertNotIn("sl", [g["id"] for g in env["ES_AI_CAMEO_NEARBY"].get("library", [])])
            for cid, enabled, goto in (("sl", False, "beach"), ("un", True, "beach"), ("sl", True, "invalid")):
                env = PrimarySwitchTests().environment(root)
                env["ES_AI_SHOWN"].append(dict(id="sl", emo="normal", cameo=True))
                env["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=enabled)
                response = dict(switch_primary=cid, goto=goto, travel_all=True)
                env["es_ai_apply_actions"](response, "Пойдём на пляж")
                self.assertEqual(env["ES_AI_LOC_CUR"][0], "library")
                self.assertEqual(env["ES_AI_LOC_LAST_CHAR"][0], "mz")
                self.assertTrue(response["suppress_main_reply"])

    def test_server_identity_history_and_capacity(self):
        for root in ROOTS:
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg={"scene_auto_primary": True})
            load(os.path.join(server, "main.py"), env, {"chat", "scene_encounter"}, rpy=False)
            history = Mock(side_effect=lambda *a, **kw: [dict(role="system", content="own identity")])
            saved = Mock()
            llm = Mock(return_value="new partner response")
            modules = {"selected_companions": module_at(root, "selected_companions"),
                       "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                       "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None), parse_choices=lambda t: (t, None), bind_selection=Mock(), response_metadata=lambda *a, **kw: {}, commit=Mock(), acknowledge_direct=Mock(), direct_request=lambda *a: None),
                       "conversation": types.SimpleNamespace(build_history_block=history, add_exchange=saved, maybe_compress=Mock()),
                       "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t,
                           strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                       "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid), map_emotion=lambda *a: "normal")}
            env.update(detect_location_in_text=lambda t: "square" if "площадь" in t else ("beach" if "пляж" in t else None),
                       normalize_location=lambda t: t, scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                       resolve_direct_address=lambda *a: ["mz"], scene_prompt=lambda *a: "",
                       clock_prompt=lambda *a: "", _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"),
                       _ACTION_ASIDE_RE=re.compile(r"NEVER"), _ACTION_CAMEO_RE=re.compile(r"NEVER"),
                       parse_action_tags=lambda t: (t, None, None, None),
                       parse_cameo_tags=lambda t, *a, **kw: (t, ["mz", "sl"]),
                       resolve_cameo_intent=Mock(return_value=[]),
                       resolve_primary_intent=Mock(return_value=None),
                       threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            payload = dict(character="mz", text="Женя останься тут, я схожу со Славей на пляж",
                           location="library", scene=dict(active="mz", present=["mz", "sl"], nearby=[],
                           destinations={"beach": ["mz", "sl", "un"]}, destination_capacity={"beach": 2}))
            original = copy.deepcopy(payload)
            with patch.dict(sys.modules, modules):
                result = env["chat"](payload)
            self.assertEqual(result["id"], "sl")
            self.assertEqual(result["switch_primary"], "sl")
            self.assertEqual(result["goto"], "beach")
            self.assertEqual(result["travel_with"], [])
            self.assertFalse(result.get("suppress_main_reply"))
            self.assertFalse(result.get("cameo"))
            self.assertEqual(history.call_args.args[0], "sl")
            self.assertEqual(saved.call_args.args[0], "sl")
            self.assertEqual(llm.call_count, 2)
            self.assertEqual(result["departure"]["id"], "mz")
            self.assertEqual(history.call_args_list[0].args[0], "mz")
            self.assertEqual(history.call_args_list[0].kwargs["location"], "library")
            self.assertIn("ORIGINAL location", llm.call_args_list[0].args[0][0]["content"])
            self.assertNotIn("newly selected", llm.call_args_list[0].args[0][0]["content"])
            self.assertEqual(payload, original)
            # Before Elektronik's first appearance: visit him, do not summon him here.
            env["resolve_direct_address"] = lambda *a: None
            env["cfg"]["npc_activity_enabled"] = False
            for text in ("Ладно, я пошёл до Электроника!", "оставайся а я к Электронику пойду",
                         "Ладно, пока! Спокойной ночи! Я до Электроника пошёл!",
                         "Женя, оставайся, а я пойду к Электронику"):
                payload = dict(character="mz", text=text, location="library",
                               scene=dict(enabled=True, location_id="library", present=["mz"],
                                          destination_capacity={"club_room": 2}, destination_nearby={},
                                          npc_activity_enabled=False))
                with patch.dict(sys.modules, modules):
                    result = env["chat"](payload)
                self.assertEqual(result["id"], "el", (root, text, result))
                self.assertEqual(result["visit_primary"], dict(id="el", location_id="club_room"))
                self.assertNotIn("switch_primary", result)
                self.assertEqual(history.call_args.kwargs["location"], "club_room")
                self.assertEqual(saved.call_args.args[0], "el")
                client = PrimarySwitchTests().environment(root)
                client["renpy"].scene = lambda: None
                client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                promoted_at = []
                enter = client["es_ai_girl_enter"]
                def promote(cid, emotion):
                    promoted_at.append((cid, client["ES_AI_LOC_CUR"][0]))
                    enter(cid, emotion)
                client["es_ai_girl_enter"] = promote
                client["es_ai_apply_actions"](json.loads(json.dumps(result)), text)
                self.assertEqual(promoted_at, [("el", "club_room")])
                self.assertEqual(client["es_ai_char_id"], "el")
                self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "el")
                self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["el"])
                self.assertEqual([g["id"] for g in client["ES_AI_CAMEO_NEARBY"]["library"]], ["mz"])
                with patch.dict(sys.modules, modules):
                    following = env["chat"](dict(character=client["es_ai_char_id"], text="Привет",
                                                   scene=dict(present=["el"])))
                self.assertEqual(following["id"], "el")
                for change in (dict(destination_nearby={"aidpost_inside": ["el"]}),
                               dict(destination_capacity={}), dict(enabled=False)):
                    blocked_payload = copy.deepcopy(payload)
                    blocked_payload["scene"].update(change)
                    with patch.dict(sys.modules, modules):
                        blocked = env["chat"](blocked_payload)
                    self.assertTrue(blocked["movement_blocked"])
                    self.assertTrue(blocked["visit_blocked"])
                    self.assertNotIn("goto", blocked)
                env["cfg"]["scene_auto_primary"] = False
                with patch.dict(sys.modules, modules):
                    blocked = env["chat"](payload)
                self.assertTrue(blocked["movement_blocked"])
                self.assertNotIn("visit_primary", blocked)
                env["cfg"]["scene_auto_primary"] = True
                env["cfg"]["npc_activity_enabled"] = True
                scheduled = copy.deepcopy(payload)
                scheduled["scene"]["activity"] = {"el": {}}
                scheduled["clock"] = dict(enabled=True, time="12:00")
                with patch.dict(sys.modules, modules):
                    ready = env["chat"](scheduled)
                self.assertEqual(ready["id"], "el")
                scheduled["clock"]["time"] = "23:00"
                with patch.dict(sys.modules, modules):
                    blocked = env["chat"](scheduled)
                self.assertTrue(blocked["movement_blocked"])
                self.assertNotIn("goto", blocked)
                env["cfg"]["npc_activity_enabled"] = False
            env["cfg"].pop("npc_activity_enabled")
            env["cfg"]["npc_activity_enabled"] = False
            for enabled in (True, False):
                env["cfg"]["scene_auto_primary"] = enabled
                for text in ("Пока", "Славя спасибо, иди наверное спать, я Шурику помогу.",
                             "Ладно пока Спокойной ночи Я до Электроника пошёл"):
                    payload = dict(character="sl", text=text, location="club_room",
                                   scene=dict(enabled=True, location_id="club_room", present=["sl", "sh"],
                                              destination_capacity={}, npc_activity_enabled=False))
                    with patch.dict(sys.modules, modules):
                        farewell = env["chat"](payload)
                    if enabled and "Шурику" in text:
                        self.assertEqual(farewell["switch_primary"], "sh")
                        self.assertEqual(farewell["id"], "sh")
                        self.assertFalse(farewell.get("end_conversation"))
                        continue
                    self.assertTrue(farewell["end_conversation"], farewell)
                    self.assertEqual(farewell["id"], "sl")
                    self.assertFalse(farewell.get("cameo"))
                    self.assertNotIn("goto", farewell)
                    client = PrimarySwitchTests().environment(root)
                    client["es_ai_pick_id"]("sl")
                    client["ES_AI_ACTIVITY_PENDING"] = {"sl": {}, "el": {}}
                    client["es_ai_apply_actions"](json.loads(json.dumps(farewell)), text)
                    client["es_ai_detach_primary"]()
                    self.assertIsNone(client["es_ai_char_id"])
                    self.assertFalse(client["ES_AI_ACTIVITY_PENDING"])
            env["cfg"]["scene_auto_primary"] = True
            env["cfg"].pop("npc_activity_enabled")
            env["resolve_direct_address"] = lambda *a: ["mz"]
            payload = dict(character="sl", text="Славя оставь нас, Лена пошли на площадь",
                           location="stage_big", scene=dict(active="sl", present=["sl", "un"], nearby=[]))
            with patch.dict(sys.modules, modules):
                result = env["chat"](payload)
            self.assertEqual(result["id"], "un")
            self.assertEqual(result["switch_primary"], "un")
            self.assertEqual(result["goto"], "square")
            self.assertEqual(result["scene_debug"]["cameo_aside"], ["sl"])
            self.assertIs(result["scene_debug"]["auto_primary"], True)
            self.assertEqual(history.call_args.args[0], "un")
            client = PrimarySwitchTests().environment(root)
            client["ES_AI_FREE_SCENE"][0] = True
            client["ES_AI_LOC_CUR"][0] = "stage_big"
            client["ES_AI_LOC_LAST_CHAR"][0] = "sl"
            client["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True)]
            client["renpy"].scene = lambda: None
            client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            client["es_ai_apply_actions"](json.loads(json.dumps(result)), payload["text"])
            self.assertEqual(client["es_ai_char_id"], "un")
            self.assertEqual(client["ES_AI_LOC_CUR"][0], "square")
            self.assertEqual([g["id"] for g in client["ES_AI_CAMEO_NEARBY"]["stage_big"]], ["sl"])
            payload = dict(character="sl", text="Славя оставь нас. Мику, пойдём прогуляемся",
                           location="stage_big", scene=dict(active="sl", present=["sl", "mi"]))
            with patch.dict(sys.modules, modules):
                result = env["chat"](payload)
            self.assertEqual(result["id"], "mi")
            self.assertEqual(result["switch_primary"], "mi")
            self.assertNotIn("goto", result)
            self.assertFalse(result.get("suppress_main_reply"))
            self.assertEqual(history.call_args.args[0], "mi")
            self.assertEqual(saved.call_args.args[0], "mi")
            env["parse_action_tags"] = lambda t: (t, "beach", None, None)
            for text in ("Славя, оставь нас", "я дальше пойду с Электроником",
                         "Электроник, оставим Женю.", "Электроник, пошли к тебе.", "пошли, Электроник!"):
                active = "mz" if text.startswith("Электроник") or text.startswith("пошли,") else "sl"
                payload = dict(character=active, text=text, location="club_room",
                               scene=dict(enabled=True, location_id="club_room", active=active,
                                          present=[active, "el"], nearby=[], activity={"el": {}},
                                          pending_calls={"el": dict(location_id="club_room", wait_turns=2)}))
                with patch.dict(sys.modules, modules):
                    result = env["chat"](payload)
                self.assertEqual(result["id"], "el")
                self.assertEqual(result["switch_primary"], "el")
                self.assertEqual(result["scene_debug"]["primary_stage"], "response-ready")
                self.assertTrue(result["scene_debug"]["parsed_reply"])
                self.assertEqual(result["scene_debug"]["parsed_goto"], "beach")
                self.assertEqual(result.get("goto"), "club_room" if "к тебе" in text else None)
                self.assertEqual(history.call_args.args[0], "el")
                self.assertEqual(saved.call_args.args[0], "el")
                client = PrimarySwitchTests().environment(root)
                client["ES_AI_FREE_SCENE"][0] = True
                client["ES_AI_LOC_CUR"][0] = "club_room"
                client["ES_AI_LOC_LAST_CHAR"][0] = active
                client["ES_AI_CHARS"].append(("el", "el", ""))
                client["ES_AI_SHOWN"][:] = [dict(id=active, emo="normal"), dict(id="el", emo="normal", cameo=True)]
                client["renpy"].scene = lambda: None
                client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                client["es_ai_apply_actions"](json.loads(json.dumps(result)), text)
                self.assertEqual(client["es_ai_char_id"], "el")
                self.assertEqual(client["es_ai_who_name"], "el")
                self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "el")
                self.assertEqual(client["ES_AI_LOC_CUR"][0], "club_room")
                self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["el"])
                following = dict(character=client["es_ai_char_id"], text="Привет", location="club_room",
                                 scene=dict(active="el", present=["el"]))
                address = env["resolve_direct_address"]
                env["resolve_direct_address"] = lambda *a: None
                with patch.dict(sys.modules, modules):
                    env["chat"](following)
                env["resolve_direct_address"] = address
                self.assertEqual(history.call_args.args[0], "el")
                self.assertEqual(saved.call_args.args[0], "el")
            # Exact live privacy request: first reply and persisted history belong to Miku.
            env["resolve_direct_address"] = lambda *a: ["sl"]
            env["parse_action_tags"] = lambda t: (t, "beach", None, "swim")
            modules["story_events"].response_metadata = lambda *a, **kw: dict(id="sl", switch_primary="sl", goto="beach", cameo=["sl"], cameo_aside=[], travel_all=True, dress="swim")
            for nearby in (False, True):
                env["resolve_direct_address"] = lambda *a: ["sl"]
                env["parse_action_tags"] = lambda t: (t, "beach", None, "swim")
                env["parse_cameo_tags"] = lambda *a, **kw: (a[0], ["sl", "un", "el"])
                modules["story_events"].response_metadata = lambda *a, **kw: dict(id="sl", switch_primary="sl", goto="beach", cameo=["sl"], cameo_aside=[], travel_all=True, dress="swim")
                payload = dict(character="sl", text="Славя, я хочу побыть наедине с Мику", location="un_room",
                               story_choice=dict(id="old-sl-choice", roles={"primary": "sl"}),
                               scene=dict(active="sl", present=["sl", "un"] if nearby else ["sl", "mi", "un"],
                                          nearby=["mi"] if nearby else []))
                with patch.dict(sys.modules, modules):
                    result = env["chat"](payload)
                self.assertEqual(result["id"], "mi")
                self.assertEqual(result["switch_primary"], "mi")
                self.assertEqual(result["scene_depart"], ["sl", "un"])
                self.assertNotIn("goto", result)
                self.assertNotIn("dress", result)
                self.assertFalse(result.get("cameo"))
                self.assertEqual(history.call_args.args[0], "mi")
                self.assertEqual(history.call_args.kwargs["location"], "un_room")
                self.assertEqual(saved.call_args.args[0], "mi")
                client = PrimarySwitchTests().environment(root)
                client["ES_AI_LOC_CUR"][0] = "un_room"
                client["ES_AI_LOC_LAST_CHAR"][0] = "sl"
                client["ES_AI_DRESS"][0] = None
                client["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True)]
                record = dict(id="mi", emo="normal", cameo=True)
                if nearby:
                    client["ES_AI_CAMEO_NEARBY"]["un_room"] = [record]
                else:
                    client["ES_AI_SHOWN"].append(record)
                client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                client["es_ai_apply_actions"](json.loads(json.dumps(result)), payload["text"])
                self.assertEqual(client["es_ai_char_id"], "mi")
                self.assertEqual(client["es_ai_who_name"], "mi")
                self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "mi")
                self.assertEqual(client["ES_AI_LOC_CUR"][0], "un_room")
                self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], ["mi"])
                self.assertEqual(client["ES_AI_CAMEO_NEARBY"]["un_room"], [])
                self.assertEqual(set(client["ES_AI_SCENE_ABSENT"]["un_room"]), {"sl", "un"})
                self.assertIsNone(client["ES_AI_DRESS"][0])
                env["resolve_direct_address"] = lambda *a: None
                modules["story_events"].response_metadata = lambda *a, **kw: {}
                env["parse_action_tags"] = lambda t: (t, None, None, None)
                env["parse_cameo_tags"] = lambda *a, **kw: (a[0], [])
                with patch.dict(sys.modules, modules):
                    following = env["chat"](dict(character=client["es_ai_char_id"], text="Пока", location="un_room",
                                                  scene=dict(active="mi", present=["mi"], nearby=["sl", "un"])))
                self.assertEqual(following["id"], "mi")
                self.assertEqual(history.call_args.args[0], "mi")
                self.assertEqual(saved.call_args.args[0], "mi")
                client["es_ai_apply_actions"](json.loads(json.dumps(following)), "Пока")
                self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], "mi")
            encounter = env["scene_encounter"](dict(active="sl", travel_with=["sl", "mi"], destination_capacity={"beach": 2}), "beach")
            self.assertEqual(encounter["present"], ["mi"])
            self.assertEqual(encounter["capacity"], 1)

    def test_config_strict_and_ui_save(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env = dict(re=re, cfg={}, config_loader=types.SimpleNamespace(save_config=Mock()))
            load(str(root / "main.py"), env, {"config_set"}, rpy=False)
            with patch.dict(sys.modules, {"story_events": types.SimpleNamespace()}):
                for invalid in (1, "true", None, [], {}):
                    self.assertFalse(env["config_set"](dict(key="scene_auto_primary", value=invalid))["ok"])
                    self.assertEqual(env["cfg"], {})
                env["config_loader"].save_config.assert_not_called()
                self.assertTrue(env["config_set"](dict(key="scene_auto_primary", value=True))["ok"])
                self.assertIs(env["cfg"]["scene_auto_primary"], True)
            ui, data, owner = SettingsSaveStateTests().environment(root)
            ui["auto_primary_on"][0] = True
            ui["refresh_save_state"]()
            self.assertEqual(ui["b_save"].kind, "primary")
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                self.assertTrue(ui["save_all"]())
            self.assertIs(ui["cfg"]["scene_auto_primary"], True)
            self.assertEqual(ui["b_save"].kind, "chip")
            source = (root / "settings_window.py").read_text(encoding="utf-8-sig")
            self.assertIn('auto_primary_on = [cfg.get("scene_auto_primary") is True]', source)
            self.assertIn('auto_primary_on[0] = False', source)


if __name__ == "__main__":
    unittest.main()
