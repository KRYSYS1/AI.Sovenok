"""Cross-location outfit sequences with actual client functions, no live data."""
import copy
import unittest
from unittest.mock import patch

from test_cameo_clothing import ROOTS
import test_primary_scene_switch as primary


class ClothingLongSessionTests(unittest.TestCase):
    def environment(self, root):
        env = primary.PrimarySwitchTests().environment(root)
        env["renpy"].scene = lambda: None
        env["es_ai_loc_bg"] = lambda loc: "bg"
        env["es_ai_cameo_on_arrive"] = lambda: None
        env["es_ai_location_from_dialog"] = lambda *a: None
        env["es_ai_read_cameo_settings"] = lambda: dict(cameo_max_extra=6, scene_auto_primary=True)
        env["_images"].update({"un normal swim", "mt normal swim", "mt normal dress"})
        env["ES_AI_LOC_CUR"][0] = "square"
        env["ES_AI_DRESS"][0] = None
        env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
        env["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True),
                                    dict(id="mi", emo="normal", cameo=True)]
        env["ES_AI_LOC_LAST_CHAR"][0] = "sl"
        env["es_ai_char_id"] = "sl"
        return env

    def assert_safe(self, env):
        env["es_ai_refresh_girls"]()
        for record in env["ES_AI_SHOWN"]:
            self.assertIn(record["tag"], env["_images"])
            self.assertNotIn("body", record["tag"])
            self.assertNotIn("nude", record["tag"])
            self.assertEqual(record["tag"].split()[0], record["id"])

    def test_beach_home_party_library_beach_with_promotions(self):
        for root in ROOTS:
            with self.subTest(root=root):
                env = self.environment(root)
                for location, expected in (("beach", "swim"), ("sl_room", "pioneer"),
                                           ("stage_big", "dress"), ("library", "pioneer"), ("beach", "swim")):
                    env["es_ai_set_location"](location, cameo_arrive=False, travel_all=True)
                    if location == "stage_big":
                        env["es_ai_apply_actions"]({}, "Let's go to the concert")
                    self.assert_safe(env)
                    self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal " + expected)
                    self.assertEqual(next(g for g in env["ES_AI_SHOWN"] if g["id"] == "un")["tag"], "un normal " + expected)
                    env["ES_AI_RECENT_LINES"][:] = [dict(who="sl", text="Old romantic exchange")]
                    env["es_ai_pick_id"]("un")
                    self.assertFalse(env["ES_AI_RECENT_LINES"])
                    self.assert_safe(env)
                    self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "un normal " + expected)
                    env["es_ai_pick_id"]("sl")
                env["es_ai_apply_actions"]({}, "Put on a uniform")
                self.assertEqual(env["ES_AI_DRESS"][0], "cover")
                env["es_ai_apply_actions"]({"dress": "body"}, "Hello")
                self.assertEqual(env["ES_AI_DRESS"][0], "cover")
                self.assert_safe(env)
                self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal pioneer")
                env["es_ai_set_location"]("library", cameo_arrive=False, travel_all=True)
                env["es_ai_set_location"]("beach", cameo_arrive=False, travel_all=True)
                self.assert_safe(env)
                self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal swim")

    def test_selected_traveler_and_parked_outfit_provenance(self):
        for root in ROOTS:
            env = self.environment(root)
            env["es_ai_set_location"]("beach", cameo_arrive=False, travel_all=True)
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "un, put on a uniform"
            env["es_ai_cameo_enter"]("un", "normal", dress="cover")
            env["ES_AI_CAMEO_PLAYER_TEXT"][0] = ""
            covered = copy.deepcopy(next(g for g in env["ES_AI_SHOWN"] if g["id"] == "un"))
            env["es_ai_set_location"]("library", cameo_arrive=False, travel_with=["mi"])
            self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"sl", "mi"})
            parked = next(g for g in env["ES_AI_CAMEO_NEARBY"]["beach"] if g["id"] == "un")
            for field in ("dress", "dress_reason", "dress_location"):
                self.assertEqual(parked[field], covered[field])
            traveler = next(g for g in env["ES_AI_SHOWN"] if g["id"] == "mi")
            self.assertIsNone(traveler["dress"])
            self.assertEqual(traveler["dress_location"], "library")
            self.assertEqual(traveler["dress_reason"], "location")
            self.assert_safe(env)
            env["es_ai_set_location"]("beach", cameo_arrive=False, travel_all=True)
            env["es_ai_cameo_enter"]("un", "normal")
            rejoined = next(g for g in env["ES_AI_SHOWN"] if g["id"] == "un")
            self.assertEqual(rejoined["dress"], "pioneer")
            self.assertEqual(rejoined["dress_reason"], covered["dress_reason"])
            self.assert_safe(env)

    def test_night_day_home_zero_draw_and_local_cover(self):
        for root in ROOTS:
            for phase, reason in (("night", "night_home"), ("day", "home_changing")):
                with self.subTest(root=root, phase=phase):
                    env = self.environment(root)
                    env["ES_AI_SHOWN"][:] = [dict(id="mt", emo="normal")]
                    env["ES_AI_LOC_LAST_CHAR"][0] = "mt"
                    env["ES_AI_LOC_CUR"][0] = "sl_room"
                    env["ES_AI_TIME"][0] = phase
                    env["ES_AI_CLOCK"].update(enabled=True, minutes=23 * 60 if phase == "night" else 12 * 60)
                    refresh = env["es_ai_refresh_girls"]
                    env["es_ai_refresh_girls"] = lambda: None
                    with patch.object(env["_es_random"], "random", return_value=0) as draw:
                        env["es_ai_cameo_enter"]("sl", "normal")
                        record = next(g for g in env["ES_AI_SHOWN"] if g["id"] == "sl")
                        self.assertEqual(record["dress"], "swim")
                        self.assertEqual(record["dress_reason"], reason)
                        env["es_ai_cameo_park"]("sl", announce=False)
                        env["es_ai_cameo_enter"]("sl", "angry")
                        self.assertEqual(draw.call_count, 1)
                        env["es_ai_cameo_enter"]("sl", "angry", dress="cover")
                        env["es_ai_cameo_park"]("sl", announce=False)
                        env["es_ai_cameo_enter"]("sl", "angry", dress="swim")
                        self.assertEqual(next(g for g in env["ES_AI_SHOWN"] if g["id"] == "sl")["dress"], "pioneer")
                        self.assertEqual(draw.call_count, 1)
                    env["es_ai_pick_id"]("sl")
                    self.assertEqual(env["ES_AI_DRESS"][0], "cover")
                    # Restore rendering after counting only the outfit RNG draws.
                    env["es_ai_refresh_girls"] = refresh
                    self.assert_safe(env)
                    self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal pioneer")
                    env["es_ai_set_location"]("beach", cameo_arrive=False, travel_all=True)
                    self.assert_safe(env)
                    self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal " + ("pioneer" if phase == "night" else "swim"))


if __name__ == "__main__":
    unittest.main()
