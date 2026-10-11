"""Offline client contract tests, including both installs' shadowed stores."""
import os
import unittest

import test_cameo_clothing as clothing

ROOTS, load = clothing.ROOTS, clothing.load


class NearbyTests(unittest.TestCase):
    def environment(self, root):
        env = clothing.ClothingTests().environment(root)
        load(os.path.join(root, "es_ai_locations.rpy"), env)
        env["ES_AI_FREE_SCENE"][0] = True
        env["renpy"].scene = lambda: None
        env["renpy"].show = lambda *a: None
        env["renpy"].say = lambda *a: None
        env["es_ai_refresh_girls"] = lambda: None
        env["es_ai_loc_bg"] = lambda loc: "bg"
        env["es_ai_cameo_on_arrive"] = lambda: None
        env["ES_AI_SHOWN"][:] = [{"id": "sl", "emo": "normal"}]
        env["es_ai_cameo_line"] = lambda *a, **k: {"reply": "Reading now", "aside": True}
        env["es_ai_is_romantic_moment"] = lambda *a: False
        return env

    def test_aside_delivery_and_tick_reengage(self):
        for root in ROOTS:
            for path in ("direct", "tick"):
                with self.subTest(root=root, path=path):
                    e = self.environment(root)
                    e["es_ai_cameo_enter"]("dv", "normal", True, dress="cover")
                    if path == "direct":
                        e["es_ai_try_cameo"]("sl", "Hi", {"cameo": ["dv"]})
                    else:
                        e["es_ai_cameo_tick"]("sl")
                        e["es_ai_cameo_tick"]("sl")
                    self.assertEqual([g["id"] for g in e["ES_AI_SHOWN"]], ["sl"])
                    record = e["ES_AI_CAMEO_NEARBY"]["square"][0]
                    self.assertEqual(record["activity"], "Reading now")
                    self.assertEqual(record["dress"], "pioneer")
                    self.assertEqual(e["ES_AI_CAMEO_ACTIVE"], [])
                    snapshot = e["es_ai_scene_snapshot"]("sl")
                    self.assertEqual(snapshot["nearby"], ["dv"])
                    self.assertFalse(snapshot["replacement_available"])
                    modes = []
                    def line(*a, **k):
                        modes.append(k["mode"])
                        return {"reply": "Back"}
                    e["es_ai_cameo_line"] = line
                    e["es_ai_try_cameo"]("sl", "Hi", {"cameo": ["dv"]})
                    self.assertEqual(modes, ["here"])
                    self.assertEqual(e["ES_AI_CAMEO_NEARBY"], {})
                    self.assertEqual(e["ES_AI_SHOWN"][1]["dress"], "pioneer")
                    e["es_ai_cameo_park"]("dv")
                    e["ES_AI_CAMEO_CD"][0] = 0
                    e["ES_AI_CAMEO_BY_LOC"]["square"] = ["dv"]
                    self.assertEqual(e["es_ai_maybe_cameo"]("sl", False), [])
                    e["es_ai_try_cameo"]("sl", "Bye", {"cameo_leave": ["dv"]})
                    self.assertEqual(e["ES_AI_CAMEO_NEARBY"], {})

    def test_movement_and_unique_location(self):
        for root in ROOTS:
            with self.subTest(root=root):
                e = self.environment(root)
                e["es_ai_cameo_enter"]("dv", "normal", True, dress="cover")
                e["es_ai_set_location"]("beach")
                self.assertEqual([g["id"] for g in e["ES_AI_SHOWN"]], ["sl"])
                self.assertEqual(e["ES_AI_CAMEO_NEARBY"]["square"][0]["dress"], "pioneer")
                self.assertNotIn("dv", e["ES_AI_RECENT_LINES"][0]["what"])
                e["es_ai_cameo_enter"]("us", "normal", True)
                e["es_ai_set_location"]("library", travel_all=True)
                self.assertEqual([g["id"] for g in e["ES_AI_SHOWN"]], ["sl", "us"])
                self.assertIsNone(e["ES_AI_SHOWN"][1]["dress"])
                self.assertEqual(e["ES_AI_CAMEO_NEARBY"]["square"][0]["id"], "dv")
                e["es_ai_cameo_enter"]("dv", "normal", True)
                self.assertNotIn("square", e["ES_AI_CAMEO_NEARBY"])
                e["ES_AI_CAMEO_NEARBY"]["beach"] = [{"id": "dv"}]
                e["es_ai_cameo_park"]("dv")
                self.assertNotIn("beach", e["ES_AI_CAMEO_NEARBY"])
                e["es_ai_set_location"]("square")
                e["es_ai_set_location"]("library")
                self.assertEqual([g["id"] for g in e["ES_AI_SHOWN"]], ["sl"])
                self.assertIn("dv", e["es_ai_scene_snapshot"]("sl")["nearby"])
                e["es_ai_girls_reset"]()
                self.assertEqual(e["ES_AI_CAMEO_NEARBY"], {})

    def test_replacement_no_victim_request_and_clear(self):
        for root in ROOTS:
            with self.subTest(root=root):
                e = self.environment(root)
                e["es_ai_read_cameo_settings"]()["cameo_max_extra"] = 2
                for cid in ("dv", "us"):
                    e["es_ai_cameo_enter"](cid, "normal", True)
                e["ES_AI_CAMEO_ACTIVE"][0]["turns"] = 10
                calls = []
                def line(cid, *a, **k):
                    calls.append(cid)
                    return {"reply": "Hi"}
                e["es_ai_cameo_line"] = line
                e["es_ai_try_cameo"]("sl", "Hi", {"cameo": ["el"]})
                self.assertEqual(calls, [])
                e["es_ai_try_cameo"]("sl", "Hi", {"cameo": ["el"], "cameo_replace": True})
                self.assertEqual(calls, ["el"])
                self.assertEqual({g["id"] for g in e["ES_AI_SHOWN"]}, {"sl", "us", "el"})
                self.assertEqual(e["ES_AI_CAMEO_NEARBY"]["square"][0]["id"], "dv")
                e["es_ai_girl_enter"]("us", "normal")
                self.assertEqual(e["ES_AI_CAMEO_NEARBY"]["square"][0]["id"], "dv")
                self.assertEqual({g["id"] for g in e["ES_AI_SHOWN"]}, {"sl", "us", "el"})
                self.assertEqual({g["id"] for g in e["ES_AI_CAMEO_ACTIVE"]}, {"sl", "el"})

    def test_apply_actions_only_explicit_boolean_moves_company(self):
        for root in ROOTS:
            for flag in (False, True, "true"):
                with self.subTest(root=root, flag=flag):
                    e = self.environment(root)
                    e["es_ai_cameo_enter"]("dv", "normal", True)
                    e["es_ai_dress_from_context"] = lambda *a: None
                    e["es_ai_apply_actions"]({"goto": "beach", "travel_all": flag})
                    self.assertEqual(len(e["ES_AI_SHOWN"]), 2 if flag is True else 1)


if __name__ == "__main__":
    unittest.main()
