"""Confirmed live travel failures, mocked server -> JSON -> real client helpers."""
import json
import os
import re
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

from test_cameo_clothing import ROOTS, load
from test_scene_memory import module_at
from test_primary_scene_switch import PrimarySwitchTests


class TravelIntentTests(unittest.TestCase):
    def test_server_json_client(self):
        for root in ROOTS:
            server = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = dict(re=re, json=json, time=time, cfg=dict(scene_auto_primary=True, npc_activity_enabled=False))
            load(os.path.join(server, "main.py"), env, {"chat"}, rpy=False)
            resolver = module_at(root, "selected_companions")
            llm = Mock(return_value="Не пойдём. Старый корпус. [action:goto:old_building]")
            modules = {
                "selected_companions": resolver,
                "npc_activity": module_at(root, "npc_activity"),
                "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None),
                    parse_choices=lambda t: (t, None), bind_selection=Mock(), acknowledge_direct=Mock(),
                    response_metadata=lambda *a, **kw: {}, direct_request=lambda *a: None),
                "conversation": types.SimpleNamespace(build_history_block=lambda *a, **kw: [dict(role="system", content="identity")],
                    add_exchange=Mock(), maybe_compress=Mock()),
                "llm_client": types.SimpleNamespace(chat=llm, sanitize_in_character=lambda t: t,
                    strip_prompt_leak=lambda t, p: t, quick_summarize=Mock()),
                "characters_store": types.SimpleNamespace(get_character=lambda cid: dict(id=cid, name=cid), map_emotion=lambda *a: "normal")}
            client = PrimarySwitchTests().environment(root)
            detect = client["es_ai_location_id"]
            env.update(detect_location_in_text=detect, normalize_location=detect,
                scene_diagnostics=lambda *a: dict(origin="chat", status="received"), scene_event=Mock(),
                resolve_direct_address=lambda *a: None, resolve_cameo_intent=lambda *a: [],
                resolve_primary_intent=lambda *a: None, scene_prompt=lambda *a: "", clock_prompt=lambda *a: "",
                _EMOTION_RE=re.compile(r"^\(([^)]+)\)(.*)$"), _ACTION_ASIDE_RE=re.compile("NEVER"),
                _ACTION_CAMEO_RE=re.compile(r"\[cameo:[^]]+\]"),
                parse_action_tags=lambda t: (t, "old_building", None, None),
                parse_cameo_tags=lambda t, *a, **kw: (t, []),
                threading=types.SimpleNamespace(Thread=lambda **kw: types.SimpleNamespace(start=Mock())))
            scene = dict(enabled=True, location_id="old_building", present=["uv"], nearby=[],
                         destination_capacity={"club_room": 2}, npc_activity_enabled=False)
            cases = [("нет", None), ("слыхал", None), ("Ладно, Юля иди в лагерь", None),
                     ("нет, пойдём лучше на пляж", "beach"), ("пошли в лагерь", None),
                     ("я пошёлк к Шурику.", "club_room")]
            for text, destination in cases:
                with self.subTest(root=root, text=text), patch.dict(sys.modules, modules):
                    result = json.loads(json.dumps(env["chat"](dict(character="uv", text=text, location="old_building", scene=scene))))
                if text == "пошли в лагерь":
                    self.assertFalse(result.get("npc_depart"))
                    self.assertFalse(result.get("end_conversation"))
                    continue
                self.assertEqual(result.get("goto"), destination)
                if text == "я пошёлк к Шурику.":
                    self.assertEqual(result["visit_primary"], dict(id="sh", location_id="club_room"))
                    self.assertEqual(result["departure"]["id"], "uv")
                    self.assertTrue(result["cameo_requested"])
                elif text == "Ладно, Юля иди в лагерь":
                    self.assertTrue(result["end_conversation"])
                    self.assertEqual(result["npc_depart"], ["uv"])
                else:
                    client["ES_AI_LOC_CUR"][0] = "bunker"
                    client["es_ai_set_location"] = lambda loc, *a, **kw: client["ES_AI_LOC_CUR"].__setitem__(0, loc)
                    client["es_ai_apply_actions"](result, text)
                    self.assertEqual(client["ES_AI_LOC_CUR"][0], destination or "bunker")

    def test_scoped_controls_and_roles(self):
        for root in ROOTS:
            resolver = module_at(root, "selected_companions")
            client = PrimarySwitchTests().environment(root)
            scene = dict(enabled=True, present=["uv", "sh"], nearby=[])
            for text in ("нет", "не пойдём на пляж", "он сказал: пошли на пляж", '"пошли на пляж"', "пойдём на пляж?", "я думал пойти к Шурику"):
                self.assertIsNone(resolver.movement_clause(text), text)
                self.assertIsNone(client["es_ai_location_from_dialog"](text, "Пойдём через старый корпус"), text)
            for text in ("пошли на пляж", "нет, пойдём лучше на пляж"):
                self.assertEqual(client["es_ai_location_from_dialog"](text, "Старый корпус"), "beach")
                self.assertEqual(resolver.resolve(text, scene, "uv", client["es_ai_location_id"], True)["goto"], "beach")
            result = resolver.resolve("Ладно, Юля иди в лагерь", scene, "uv", lambda t: None, True)
            self.assertEqual(result["switch_primary"], "sh")
            result = resolver.resolve("Шурик иди в лагерь", scene, "uv", lambda t: None, True)
            self.assertEqual(result["npc_depart"], ["sh"])
            self.assertFalse(result["farewell_primary"])
            self.assertIsNone(result["switch_primary"])
            for enabled in (True, False):
                result = resolver.resolve("я пошёлк к Шурику.", scene, "uv", lambda t: None, enabled)
                self.assertEqual(result["visit_primary"]["id"], "sh")
                result = resolver.resolve("я направляюсь к Шурику", scene, "uv", lambda t: None, enabled)
                self.assertTrue(result["movement_blocked"])
                self.assertEqual(result["directional_visit"], "sh")


if __name__ == "__main__":
    unittest.main()
