"""Offline selected travel regressions for both installed roots."""
import os
import re
import unittest
import json
import sys
import time
import types
from unittest.mock import Mock, patch
from test_cameo_clothing import ROOTS, load
import test_primary_scene_switch as primary
from test_scene_memory import module_at


class SelectedCompanionTests(unittest.TestCase):
    def test_current_partner_privacy_overrides_cohort_and_explicit_travel(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["el", "mz"], nearby=["mi"], travel_party=["el", "mz"])
            detect = lambda t: "beach" if "пляж" in t else None
            for partner in ("тобой", "Электроником"):
                for prefix in ("", "Электроник, "):
                    text = "Пошли на пляж. " + prefix + "Я хочу побыть наедине с " + partner + "."
                    result = resolver.resolve(text, scene, "el", detect, True)
                    self.assertTrue(result["privacy"], text)
                    self.assertEqual(result["goto"], "beach")
                    self.assertEqual(result["scene_depart"], ["mz", "mi"])
                    self.assertEqual(result["travel_party"], [])
                    self.assertEqual(result["travel_with"], [])
                    self.assertIsNone(result["switch_primary"])
            stationary = resolver.resolve("Я хочу побыть наедине с тобой.", scene, "el", detect, True)
            self.assertTrue(stationary["privacy"])
            self.assertIsNone(stationary["goto"])
            for phrase in ("Я не хочу побыть наедине с тобой.", '"Я хочу побыть наедине с тобой."',
                           "Он хочет побыть наедине с тобой.", "Он сказал: я хочу побыть наедине с тобой.",
                           "Он: я хочу побыть наедине с тобой.", "Женя, я хочу побыть наедине с тобой."):
                result = resolver.resolve("Пошли на пляж. " + phrase, scene, "el", detect, True)
                self.assertFalse(result.get("privacy"), phrase)
                self.assertIn("mz", result["travel_with"], phrase)
                self.assertEqual(set(result["travel_party"]), {"el", "mz"}, phrase)

    def test_server_group_handoff_roles_prompts_and_json(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            llm, saved = Mock(return_value="reply"), Mock()
            histories = Mock(side_effect=lambda cid, *a, **kw: [dict(role="system", content="identity=" + cid)])
            scenes = []
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
            env.update(detect_location_in_text=lambda t: "old_building_inside" if "внутрь" in t else None,
                normalize_location=lambda t: t,
                scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                resolve_direct_address=lambda *a: None, resolve_cameo_intent=lambda *a: [],
                resolve_primary_intent=Mock(side_effect=AssertionError("No semantic classifier needed")),
                scene_prompt=lambda s, cid: scenes.append((cid, s)) or "", clock_prompt=lambda *a: "",
                _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile("NEVER"),
                _ACTION_CAMEO_RE=re.compile(r"\[cameo:[^]]+\]"),
                parse_action_tags=lambda t: (t, None, None, None), parse_cameo_tags=lambda t, *a, **kw: (t, []),
                threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            client = primary.PrimarySwitchTests().environment(root)
            client["renpy"].scene = lambda: None
            client["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            client["es_ai_cameo_on"] = lambda: True
            client["ES_AI_LOC_CUR"][0] = "old_building"
            client["es_ai_cameo_enter"]("el", "normal", stay=True)
            with patch.dict(sys.modules, modules):
                for text in ("Электроник, пошли с нами изучим заброшку", "Пошли во внутрь", "Идёмте", "Да"):
                    active = client["ES_AI_LOC_LAST_CHAR"][0]
                    result = json.loads(json.dumps(env["chat"](dict(character=active, text=text,
                        location=client["ES_AI_LOC_CUR"][0], scene=client["es_ai_scene_snapshot"](active)))))
                    self.assertEqual(result["id"], "el")
                    if active == "mz":
                        self.assertEqual(result["travel_with"], ["mz"])
                        self.assertEqual(result["departure"]["id"], "mz")
                        self.assertEqual(result["cameo_aside"], [])
                        self.assertIn("NOT a farewell", llm.call_args_list[0].args[0][0]["content"])
                        self.assertIn("companion travelling WITH", llm.call_args_list[1].args[0][0]["content"])
                        self.assertIn("mz", scenes[-1][1]["present"])
                        self.assertFalse(scenes[-1][1]["context"])
                    client["es_ai_apply_actions"](result, text)
                    self.assertEqual({g["id"] for g in client["ES_AI_SHOWN"]}, {"mz", "el"})
            self.assertEqual([call.args[0] for call in histories.call_args_list], ["mz", "el", "el", "el", "el"])
            self.assertEqual([call.args[0] for call in saved.call_args_list], ["mz", "el", "el", "el", "el"])
            env["detect_location_in_text"] = lambda t: "beach" if "пляж" in t else None
            arrived = Mock(side_effect=AssertionError("Privacy must not trigger destination cameos"))
            client["es_ai_cameo_on_arrive"] = arrived
            for suffix in ("Я хочу побыть наедине с тобой.", "Электроник, я хочу побыть наедине с тобой.",
                           "Я хочу побыть наедине с Электроником.", "Я хочу побыть наедине с Женей."):
                client["ES_AI_LOC_CUR"][0] = "old_building"
                client["ES_AI_CAMEO_NEARBY"].clear()
                client["ES_AI_SHOWN"][:] = [dict(id="el", emo="normal"), dict(id="mz", emo="normal", cameo=True, travel_party=True)]
                client["ES_AI_LOC_LAST_CHAR"][0] = "el"
                client["es_ai_cameo_enter"]("mi", "normal", stay=True)
                client["es_ai_cameo_park"]("mi", announce=False)
                text = "Пошли на пляж. " + suffix
                with patch.dict(sys.modules, modules):
                    result = json.loads(json.dumps(env["chat"](dict(character="el", text=text,
                        location="old_building", scene=client["es_ai_scene_snapshot"]("el")))))
                target = "mz" if suffix.endswith("Женей.") else "el"
                departed = "el" if target == "mz" else "mz"
                self.assertTrue(result["privacy"])
                self.assertEqual(result["id"], target)
                self.assertEqual(result["goto"], "beach")
                self.assertEqual(result["travel_party"], [])
                self.assertEqual(result["travel_with"], [])
                self.assertFalse(result.get("cameo"))
                self.assertFalse(result.get("dress"))
                self.assertIn("Travel only with the player", llm.call_args.args[0][0]["content"])
                self.assertFalse(scenes[-1][1]["context"])
                self.assertEqual(scenes[-1][1]["travel_party"], [])
                self.assertNotIn(departed, scenes[-1][1]["present"])
                client["es_ai_apply_actions"](result, text)
                self.assertEqual(client["ES_AI_LOC_LAST_CHAR"][0], target)
                self.assertEqual(client["ES_AI_LOC_CUR"][0], "beach")
                self.assertEqual([g["id"] for g in client["ES_AI_SHOWN"]], [target])
                self.assertEqual(set(client["ES_AI_SCENE_ABSENT"]["old_building"]), {departed, "mi"})
                self.assertFalse(client["ES_AI_CAMEO_NEARBY"].get("old_building"))
                self.assertFalse(client["ES_AI_CAMEO_NEARBY"].get("beach"))
                self.assertFalse(client["es_ai_scene_snapshot"](target)["travel_party"])
                client["ES_AI_SCENE_ABSENT"].clear()
            arrived.assert_not_called()

    def test_group_invitation_json_client_and_continuation(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            env = primary.PrimarySwitchTests().environment(root)
            env["renpy"].scene = lambda: None
            env["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
            env["es_ai_cameo_on"] = lambda: True
            env["es_ai_cameo_enter"]("el", "normal", stay=True)
            env["ES_AI_LOC_CUR"][0] = "old_building"
            detect = lambda t: "old_building_inside" if "внутрь" in t else "mine" if "шахт" in t else None
            text = "Электроник, пошли с нами изучим заброшку"
            travel = resolver.resolve(text, env["es_ai_scene_snapshot"]("mz"), "mz", detect, True)
            self.assertEqual(travel["switch_primary"], "el")
            self.assertEqual(travel["travel_with"], ["mz"])
            self.assertEqual(travel["cameo_aside"], [])
            self.assertFalse(travel["travel_all"])
            env["es_ai_apply_actions"](json.loads(json.dumps(travel)), text)
            self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"el", "mz"})
            self.assertEqual(set(env["es_ai_scene_snapshot"]("el")["travel_party"]), {"el", "mz"})
            # Unrelated later arrivals do not silently join the selected expedition.
            env["es_ai_cameo_enter"]("mi", "normal", stay=True)
            for text in ("Пошли во внутрь", "Идёмте в шахту", "Идём дальше"):
                scene = env["es_ai_scene_snapshot"]("el")
                travel = resolver.resolve(text, scene, "el", detect, True)
                self.assertIn("mz", travel["travel_with"], text)
                if text.startswith("Пошли"):
                    self.assertNotIn("mi", travel["travel_with"])
                env["es_ai_apply_actions"](json.loads(json.dumps(travel)), text)
                self.assertIn("mz", {g["id"] for g in env["ES_AI_SHOWN"]})
            env["es_ai_cameo_park"]("mz", announce=False)
            self.assertEqual(env["es_ai_scene_snapshot"]("el")["travel_party"], [])
            travel = resolver.resolve("Пошли во внутрь", env["es_ai_scene_snapshot"]("el"), "el", detect, True)
            self.assertNotIn("mz", travel["travel_with"])

    def test_group_scope_split_privacy_and_plain_walk(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            scene = dict(enabled=True, present=["mz", "el", "mi"], nearby=["sl"], travel_party=["mz", "el"])
            detect = lambda t: "beach" if "пляж" in t else None
            for text in ("Идёмте на пляж", "Пойдёмте на пляж", "Идём дальше на пляж", "Пошли с нами на пляж", "Пошли вместе с нами на пляж"):
                travel = resolver.resolve(text, dict(scene, travel_party=[]), "el", detect, True)
                self.assertEqual(set(travel["travel_with"]), {"mz", "mi"}, text)
                self.assertNotIn("sl", travel["travel_with"])
            for text in ("Пошли на пляж", "Пошли во внутрь"):
                self.assertEqual(resolver.resolve(text, dict(scene, travel_party=[]), "el", detect, True)["travel_with"], [])
            for text in ("Я пойду один на пляж", "Я пойду на пляж", "Женя оставайся читать. Пошли на пляж", "Пока, Женя. Пошли на пляж"):
                travel = resolver.resolve(text, scene, "el", detect, True)
                self.assertEqual(travel["travel_party"], [], text)
                self.assertNotIn("mz", travel["travel_with"], text)
            for text in ("Не пойду с нами на пляж", "Не идёмте на пляж", 'Он сказал: "пошли с нами на пляж"'):
                travel = resolver.resolve(text, dict(scene, travel_party=[]), "el", detect, True)
                self.assertFalse(travel["travel_with"], text)
                self.assertFalse(travel.get("travel_party"), text)
            privacy = resolver.resolve("Пойдём все на пляж. Я хочу побыть наедине с Женей.", scene, "el", detect, True)
            self.assertTrue(privacy["privacy"])
            self.assertEqual(privacy["travel_party"], [])
            self.assertEqual(privacy["travel_with"], [])
            self.assertEqual(privacy["goto"], "beach")
            for action in ("clear", "switch", "privacy", "leave"):
                env = primary.PrimarySwitchTests().environment(root)
                env["es_ai_cameo_enter"]("el", "normal", stay=True)
                env["es_ai_read_cameo_settings"] = lambda: dict(scene_auto_primary=True, cameo_max_extra=6)
                env["es_ai_cameo_on"] = lambda: True
                env["es_ai_apply_actions"](dict(travel_party=["mz", "el"]), "Привет")
                if action == "clear":
                    env["es_ai_cameo_clear"]()
                elif action == "switch":
                    env["es_ai_pick_id"]("el")
                elif action == "leave":
                    env["es_ai_cameo_leave"]("el")
                else:
                    travel = resolver.resolve("Я хочу побыть наедине с Женей", env["es_ai_scene_snapshot"]("mz"), "mz", detect, True)
                    env["es_ai_apply_actions"](json.loads(json.dumps(travel)), "Я хочу побыть наедине с Женей")
                self.assertFalse(env["es_ai_scene_snapshot"](env["ES_AI_LOC_LAST_CHAR"][0])["travel_party"], action)
                self.assertFalse(any(g.get("travel_party") for g in env["ES_AI_SHOWN"]), action)

    def test_current_clause_selection(self):
        for root in ROOTS:
            selection = module_at(root, "selected_companions")
            env = {"re": re}
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            load(os.path.join(server, "main.py"), env, {"detect_location_in_text", "scene_encounter"}, rpy=False)
            # The loader intentionally excludes ordinary constants.
            import ast
            env["re"] = re
            with open(os.path.join(server, "main.py"), encoding="utf-8-sig") as stream:
                tree = ast.parse(stream.read())
            alias = next(n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_LOCATION_ALIASES" for t in n.targets))
            exec(compile(ast.Module(body=[alias], type_ignores=[]), "aliases", "exec"), env)
            scene = dict(present=["un", "sl", "dv", "mz"], nearby=["mi", "el"])
            examples = [("Пойдём на пляж со Славей", "beach", ["sl"]),
                        ("Пойдём на пляж с Алисой и Мику", "beach", ["dv", "mi"]),
                        ("Пойдём на пляж вместе с Электроником", "beach", ["el"]),
                        ("Женя оставайся читать а мы со Славей пойдём к Лене", "un_room", ["sl"]),
                        ("Пойдём все на пляж. Женя оставайся читать", "beach", ["sl", "dv"]),
                        ("Пойдём все на пляж", "beach", ["sl", "dv", "mz"]),
                        ("Пойдём на пляж с Шуриком", "beach", []),
                        ("Я говорил с Алисой про пляж", None, []),
                        ("Не пойдём все на пляж", None, [])]
            for text, destination, companions in examples:
                with self.subTest(root=root, text=text):
                    result = selection.resolve(text, scene, "un", env["detect_location_in_text"])
                    self.assertEqual(result["goto"], destination)
                    self.assertEqual(result["travel_with"], companions)
            blocked = selection.resolve("Лена оставайся читать а мы со Славей пойдём на пляж", scene, "un", env["detect_location_in_text"])
            self.assertTrue(blocked["movement_blocked"])
            self.assertFalse(selection.resolve("Женя оставайся читать", scene, "un", env["detect_location_in_text"])["cameo_aside"])
            encounter = env["scene_encounter"](dict(scene, travel_with=["sl"], travel_all=True,
                destination_capacity={"beach": 6}), "beach")
            self.assertEqual(encounter["present"], ["sl"])
            self.assertEqual(encounter["capacity"], 5)

    def test_client_selected_local_travel_and_block(self):
        for root in ROOTS:
            env = primary.PrimarySwitchTests().environment(root)
            env["renpy"].scene = lambda: None
            env["es_ai_pick_id"]("sl")
            env["es_ai_cameo_enter"]("dv", "normal", stay=True)
            env["es_ai_cameo_enter"]("mi", "normal", stay=True)
            env["es_ai_cameo_park"]("mi", announce=False)
            env["es_ai_set_location"]("beach", cameo_arrive=False, travel_all=True, travel_with=["mi", "absent"])
            self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"sl", "mi"})
            self.assertEqual({g["id"] for g in env["ES_AI_CAMEO_NEARBY"]["library"]}, {"mz", "dv"})
            env["es_ai_apply_actions"]({"goto": "square", "movement_blocked": True}, "Пошли на площадь")
            self.assertEqual(env["ES_AI_LOC_CUR"][0], "beach")

    def test_active_stay_blocks_unknown_destination_and_client_fallback(self):
        for root in ROOTS:
            selection = module_at(root, "selected_companions")
            scene = dict(present=["un", "sl"], nearby=[])
            for text in ("Лена оставайся читать а мы со Славей пойдём погулять",
                         "Лена оставайся читать а мы со Славей сходим куда-нибудь",
                         "Лена оставайся читать а мы со Славей сходим на пляж",
                         "Лена оставайся читать"):
                with self.subTest(root=root, text=text):
                    travel = selection.resolve(text, scene, "un", lambda text: None)
                    self.assertTrue(travel["movement_blocked"])
                    self.assertIsNone(travel["goto"])
                    self.assertEqual(travel["travel_with"], [])
                    env = primary.PrimarySwitchTests().environment(root)
                    env["es_ai_char_id"] = "mz"
                    env["es_ai_location_from_dialog"] = lambda *a: "beach"
                    env["es_ai_apply_actions"](dict(travel, reply="Пойдём на пляж"), text)
                    self.assertEqual(env["ES_AI_LOC_CUR"][0], "library")


if __name__ == "__main__":
    unittest.main()
