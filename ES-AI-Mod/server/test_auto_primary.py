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
            history = Mock(return_value=[dict(role="system", content="own identity")])
            saved = Mock()
            llm = Mock(return_value="new partner response")
            modules = {"selected_companions": module_at(root, "selected_companions"),
                       "scene_memory": types.SimpleNamespace(ingest=Mock(), prompt=lambda cid: ""),
                       "story_events": types.SimpleNamespace(prepare=lambda *a: None, parse_tags=lambda t: (t, None), commit=Mock(), acknowledge_direct=Mock(), direct_request=lambda *a: None),
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
            llm.assert_called_once()
            self.assertEqual(payload, original)
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
