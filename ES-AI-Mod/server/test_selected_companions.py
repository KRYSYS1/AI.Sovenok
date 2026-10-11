"""Offline selected travel regressions for both installed roots."""
import os
import re
import unittest
from test_cameo_clothing import ROOTS, load
import test_primary_scene_switch as primary
from test_scene_memory import module_at


class SelectedCompanionTests(unittest.TestCase):
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
