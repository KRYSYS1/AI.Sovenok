# -*- coding: utf-8 -*-
"""Non-explicit costume requests, actor consent and private adult choices."""
import importlib.util
import os
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_cameo_clothing import ROOTS, REQUEST_CASES, load
import test_clothing_long_session as sessions
import test_story_events as stories


class ClothingRequestTests(unittest.TestCase):
    def server(self, root):
        return os.path.join(os.path.dirname(root) if os.path.basename(root) == "mod" else root, "server")

    def policy(self, root):
        spec = importlib.util.spec_from_file_location("costume_test_policy", os.path.join(self.server(root), "clothing_policy.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def environment(self, root, cid="sl"):
        env = sessions.ClothingLongSessionTests().environment(root)
        env["ES_AI_LOC_LAST_CHAR"][0] = cid
        env["ES_AI_SHOWN"][:] = [dict(id=cid, emo="normal")]
        env["ES_AI_LOC_CUR"][0] = "bus_inside"
        env["ES_AI_TIME"][0] = "day"
        env["ES_AI_CAMEO_NEARBY"].clear()
        env["ES_AI_ROMANCEABLE"] = ["sl", "mi", "un", "dv", "mt"]
        env["es_ai_cameo_adult_home_ids"] = lambda: {"sl", "mi", "un", "dv", "mt"}
        env["_images"].update({"sl shy swim close", "mi normal swim"})
        return env

    def test_server_client_request_matrix(self):
        extra = (("в бикини переоденься", "swim"), ("Славя, в купальник переоденься", "swim"),
                 ("Славя, в купальник НЕ переодевайся", None), ("Славя, в бикини не переоденься", None),
                 ("Славя, переоденься", None), ("Славя, в форму переоденься", "cover"),
                 ("Славя, в платье переоденься", "dress"), ("Славя, надень спортивную одежду", "sport"),
                 ("Славя и Лена, в бикини переоденься", "swim"),
                 ("Славя надень форму, Лена надень купальник", "cover"))
        for root in ROOTS:
            env, policy = self.environment(root), self.policy(root)
            for text, expected in REQUEST_CASES + extra:
                with self.subTest(root=root, text=text):
                    unnamed = (text, expected) in extra
                    self.assertEqual(env["es_ai_cameo_clothing_request"]("sl", text, unnamed=unnamed), expected)
                    self.assertEqual(policy.cameo_requested_dress("sl", text, unnamed=unnamed), expected)
                    self.assertEqual(policy.cameo_requested_dress("sl", text), env["es_ai_cameo_clothing_request"]("sl", text))

    def test_explicit_reverse_order_stock_sprite_and_aliases(self):
        for root in ROOTS:
            env = self.environment(root)
            env["ES_AI_SHOWN"][0]["emo"] = "shy"
            env["ES_AI_LOC_LAST_EMO"][0] = "shy"
            env["es_ai_apply_actions"]({"dress": "swim", "reply": "Да, надену купальник."}, "в бикини переоденься")
            self.assertEqual(env["ES_AI_DRESS"][0], "swim")
            env["es_ai_refresh_girls"]()
            self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl shy swim close")
            normalizer = {"re": re}
            load(os.path.join(self.server(root), "main.py"), normalizer, {"normalize_dress"}, False)
            for word in ("бикини", "купальник", "bikini", "swimsuit", "swim"):
                self.assertEqual(normalizer["normalize_dress"](word), "swim")
                env["es_ai_set_dress"](word)
                self.assertEqual(env["ES_AI_DRESS"][0], "swim")
            self.assertIsNone(normalizer["normalize_dress"]("переоденься"))
            self.assertIsNone(env["es_ai_dress_from_context"]("переоденься", "", env["es_ai_location"]()))

    def test_reversed_negation_never_authorizes(self):
        for root in ROOTS:
            for text in ("в купальник НЕ переодевайся", "в бикини не переоденься"):
                env = self.environment(root)
                env["es_ai_apply_actions"]({"dress": "swim"}, text)
                self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_private_daytime_miku_optional_not_automatic(self):
        for root in ROOTS:
            for location in ("bus_inside", "un_room", "polyana", "library", "beach"):
                for answer, tag, expected in (("Да, хочу, переоденусь в бикини.", "swim", "swim"),
                                               ("Да, обнимемся.", "swim", None),
                                               ("Да, хочу, переоденусь в бикини.", None, None)):
                    env = self.environment(root, "mi")
                    env["ES_AI_LOC_CUR"][0] = location
                    if location == "beach":
                        env["ES_AI_TIME"][0] = "night"
                    env["es_ai_apply_actions"]({"reply": answer, "dress": tag}, "обнимемся")
                    self.assertEqual(env["ES_AI_DRESS"][0], expected, (root, location, answer))
                    if expected:
                        self.assertEqual(env["ES_AI_SHOWN"][0]["dress_reason"], "romantic_choice")
                        env["es_ai_apply_actions"]({"privacy": True}, "поговорим наедине")
                        self.assertEqual(env["ES_AI_DRESS"][0], "swim")

    def test_crowd_nearby_and_wrong_actor_block_choice(self):
        for root in ROOTS:
            for crowded, nearby, text in ((True, False, "обнимемся"), (False, True, "обнимемся"),
                                         (False, False, "хочу обнять Мику"),
                                         (False, False, "хочу побыть наедине с Мику"),
                                         (False, False, "романтика"), (False, False, "наедине")):
                env = self.environment(root)
                if crowded:
                    env["ES_AI_SHOWN"].append(dict(id="un", emo="normal", cameo=True))
                if nearby:
                    env["ES_AI_CAMEO_NEARBY"]["bus_inside"] = [dict(id="mi")]
                env["es_ai_apply_actions"]({"dress": "swim", "reply": "Да, хочу, надену купальник."}, text)
                self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_refusal_preserves_primary_and_cameo(self):
        for root in ROOTS:
            for answer in ("Не хочу переодеваться.", "Останусь в форме.", "Не надену купальник.", "Не буду надевать купальник."):
                env, policy = self.environment(root), self.policy(root)
                self.assertTrue(policy.clothing_refused(answer))
                self.assertTrue(env["es_ai_clothing_refused"](answer))
                env["es_ai_apply_actions"]({"dress": "swim", "reply": answer}, "в бикини переоденься")
                self.assertEqual(env["ES_AI_DRESS"][0], "cover" if answer == "Останусь в форме." else None)
                env["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"), dict(id="un", emo="normal", cameo=True)]
                env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "Лена, в бикини переоденься"
                env["es_ai_speakers"]["un"] = lambda text: None
                env["es_ai_cameo_speak"]("un", answer, "normal", "swim")
                self.assertEqual(env["ES_AI_SHOWN"][1].get("dress"), "pioneer" if answer == "Останусь в форме." else None)

    def test_structured_adult_fail_closed(self):
        for root in ROOTS:
            policy = self.policy(root)
            for cid in ("mi", "sl", "us", "uv"):
                for age in (18, 27, 17, 14, None, "18", True, float("nan")):
                    expected = cid not in ("us", "uv") and type(age) in (int, float) and age >= 18
                    self.assertEqual(bool(policy.romantic_choice(cid, age, "обнимемся", "Да, хочу, надену купальник", True)), expected)
                    env = self.environment(root, cid)
                    env["es_ai_cameo_adult_home_ids"] = lambda: {cid} if expected else set()
                    env["es_ai_apply_actions"]({"dress": "swim", "reply": "Да, хочу, надену купальник"}, "обнимемся")
                    self.assertEqual(env["ES_AI_DRESS"][0], "swim" if expected else None)

    def test_actual_chat_authorization_and_refusal(self):
        fixture = stories.StoryTests()
        fixture.setUp()
        try:
            for root in ROOTS:
                server = self.server(root)
                mod = stories.module(server)
                mod.manager = fixture.manager(mod)
                env, llm, _, modules = fixture.endpoint_env(server, mod, False)
                modules["characters_store"].get_character = lambda cid: dict(id=cid, name=cid, persona="", age=18)
                with patch.dict(sys.modules, modules):
                    for text, answer, present, expected in (
                            ("в бикини переоденься", "Да, надену купальник", ["mi"], "swim"),
                            ("в бикини переоденься", "Останусь в форме", ["mi"], "cover"),
                            ("обнимемся", "Да, хочу, переоденусь в бикини", ["mi"], "swim"),
                            ("обнимемся", "Да, хочу, переоденусь в бикини", ["mi", "sl"], None),
                            ("обнимемся", "Да, обнимемся", ["mi"], None),
                            ("хочу обнять Славю", "Да, хочу, надену купальник", ["mi"], None)):
                        llm.chat.return_value = "(normal) " + answer + " [action:dress:swim]"
                        out = env["chat"](dict(text=text, character="mi", location="bus_inside", scene=dict(present=present)))
                        self.assertTrue(out["ok"], out)
                        self.assertEqual(out.get("dress"), expected, (root, text, answer))
        finally:
            fixture.tearDown()

    def test_actual_cameo_explicit_and_refused(self):
        fixture = stories.StoryTests()
        fixture.setUp()
        try:
            for root in ROOTS:
                server = self.server(root)
                mod = stories.module(server)
                mod.manager = fixture.manager(mod)
                env, llm, _, modules = fixture.endpoint_env(server, mod, False)
                with patch.dict(sys.modules, modules):
                    for text, answer, expected in (("Славя, в бикини переоденься", "Да, надену купальник", "swim"),
                                                   ("Славя, в купальник не переодевайся", "Останусь в форме", "cover"),
                                                   ("Славя, в бикини переоденься", "Не хочу переодеваться", None)):
                        llm.chat.return_value = "(normal) " + answer + " [action:dress:swim]"
                        out = env["cameo"](dict(character="sl", player_text=text, location_id="bus_inside"))
                        self.assertTrue(out["ok"], out)
                        self.assertEqual(out.get("dress"), expected)
        finally:
            fixture.tearDown()

    def test_actual_chat_structured_age_and_canonical_exclusions(self):
        fixture = stories.StoryTests()
        fixture.setUp()
        try:
            for root in ROOTS:
                server = self.server(root)
                mod = stories.module(server)
                mod.manager = fixture.manager(mod)
                env, llm, _, modules = fixture.endpoint_env(server, mod, False)
                with patch.dict(sys.modules, modules):
                    for cid, age in (("mi", 18), ("mi", 17), ("mi", None), ("mi", "18"), ("mi", True), ("us", 27), ("uv", 27)):
                        modules["characters_store"].get_character = lambda actor: dict(id=actor, name=actor, persona="Adult custom persona", age=age)
                        llm.chat.return_value = "(normal) Да, хочу, надену купальник. [action:dress:swim]"
                        out = env["chat"](dict(text="обнимемся", character=cid, location="bus_inside", scene=dict(present=[cid])))
                        self.assertEqual(out.get("dress"), "swim" if cid == "mi" and age == 18 else None)
                        self.assertNotEqual(out.get("dress_reason"), "romantic_choice" if cid in ("us", "uv") else "invalid")
        finally:
            fixture.tearDown()

    def test_old_context_and_existing_costume_are_not_new_consent(self):
        for root in ROOTS:
            env = self.environment(root, "mi")
            env["ES_AI_RECENT_LINES"][:] = [dict(who="Player", what="обнимемся")]
            env["es_ai_apply_actions"]({"dress": "swim", "reply": "Да, хочу, надену купальник"}, "привет")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            env["ES_AI_DRESS"][0] = "swim"
            self.assertFalse(env["es_ai_beach_romantic_clothing"]("привет", "Да, хочу, надену купальник"))
            record = dict(id="mi", dress_reason="romantic_choice", dress_location="bus_inside")
            self.assertEqual(env["es_ai_cameo_dress"](None, "swim", record), "swim")
            record.update(id="us", dress_reason="romantic_choice")
            self.assertIsNone(env["es_ai_cameo_dress"](None, "swim", record))

    def test_episode_preference_boundaries_stability_and_reset(self):
        for root in ROOTS:
            for draw, expected in ((.749, "swim"), (.750, "keep")):
                policy = self.policy(root)
                scene = dict(location_id="bus_inside", present=["mi"])
                with patch.object(policy.random, "random", return_value=draw) as rng:
                    for text in ("обнимемся", "поцелую", "люблю тебя"):
                        self.assertIn("romantic_outfit_preference=" + expected,
                                      policy.romantic_preference("mi", 18, text, scene))
                    self.assertEqual(rng.call_count, 1)
                    policy.record_clothing_reply("mi", "Не хочу переодеваться.")
                    self.assertIn("preference=keep", policy.romantic_preference("mi", 18, "обнимемся", scene))
                    self.assertEqual(rng.call_count, 1)
                    policy.romantic_preference("mi", 18, "привет", scene)
                    policy.romantic_preference("mi", 18, "поговорим", scene)
                    policy.romantic_preference("mi", 18, "обнимемся", scene)
                    self.assertEqual(rng.call_count, 2)
                    public = dict(scene, present=["mi", "sl"])
                    self.assertEqual(policy.romantic_preference("mi", 18, "обнимемся", public), "")
                    policy.romantic_preference("mi", 18, "обнимемся", scene)
                    self.assertEqual(rng.call_count, 3)
                    policy.romantic_preference("mi", 18, "обнимемся", dict(scene, location_id="un_room"))
                    self.assertEqual(rng.call_count, 4)

    def test_episode_age_privacy_and_neutral_fail_closed(self):
        for root in ROOTS:
            policy = self.policy(root)
            with patch.object(policy.random, "random") as rng:
                for cid, age in (("us", 28), ("uv", 28), ("mi", None), ("mi", "18"), ("mi", True), ("mi", 17)):
                    self.assertEqual(policy.romantic_preference(cid, age, "обнимемся", dict(location_id="bus_inside", present=[cid])), "")
                for scene in ({}, dict(location_id="bus_inside", present=["mi"], nearby=["sl"])):
                    self.assertEqual(policy.romantic_preference("mi", 18, "обнимемся", scene), "")
                for text in ("наедине", "привет", "не обнимай", "хочу обнять Славю"):
                    self.assertEqual(policy.romantic_preference("mi", 18, text, dict(location_id="bus_inside", present=["mi"])), "")
                rng.assert_not_called()
            for cid in ("sl", "un", "mi"):
                self.assertTrue(policy.adult_romance_allowed(cid, 18))

    def test_rendered_outfit_snapshot_overrides_requested_fallback(self):
        for root in ROOTS:
            env = self.environment(root)
            load(os.path.join(root, "es_ai_cameo.rpy"), env, {"es_ai_actual_outfits"})
            env["ES_AI_LOC_CUR"][0] = "beach"
            env["es_ai_refresh_girls"]()
            self.assertEqual(env["es_ai_actual_outfits"]()["sl"], "swim")
            env["ES_AI_SHOWN"][0].update(dress="swim", tag="sl normal pioneer")
            self.assertEqual(env["es_ai_actual_outfits"]()["sl"], "pioneer")
            env["ES_AI_SHOWN"][0].update(tag=None)
            env["es_ai_resolve_sprite"] = lambda *a, **kw: "sl normal pioneer"
            self.assertEqual(env["es_ai_actual_outfits"]()["sl"], "pioneer")
            env["es_ai_resolve_sprite"] = lambda *a, **kw: None
            self.assertEqual(env["es_ai_actual_outfits"]()["sl"], "unknown")

    def test_actual_prompt_snapshot_and_pre_generation_preference(self):
        fixture = stories.StoryTests()
        fixture.setUp()
        try:
            for root in ROOTS:
                server = self.server(root)
                mod = stories.module(server)
                mod.manager = fixture.manager(mod)
                env, llm, _, modules = fixture.endpoint_env(server, mod, False)
                modules["characters_store"].get_character = lambda cid: dict(id=cid, name=cid, persona="Old uniform", age=18)
                modules["characters_store"].characters = lambda: [dict(id="mi", name="Miku")]
                load(os.path.join(server, "main.py"), env, {"scene_prompt"}, False)
                scene = dict(location_id="bus_inside", present=["mi"], outfits=dict(mi="swim"))
                import clothing_policy
                clothing_policy._episodes.clear()
                with patch.dict(sys.modules, modules), patch.object(clothing_policy.random, "random", return_value=.750):
                    llm.chat.return_value = "(normal) Да, обнимемся. [action:dress:swim]"
                    out = env["chat"](dict(text="обнимемся", character="mi", location="bus_inside", scene=scene))
                    prompt = llm.chat.call_args[0][0][0]["content"]
                    self.assertIn('"mi": "swim"', prompt)
                    self.assertIn("romantic_outfit_preference=keep", prompt)
                    self.assertIsNone(out.get("dress"))
                    llm.chat.return_value = "(normal) Да, хочу, переоденусь в купальник. [action:dress:swim]"
                    out = env["chat"](dict(text="обнимемся", character="mi", location="bus_inside", scene=scene))
                    self.assertEqual(out.get("dress"), "swim")
                    # A hint must never randomly discard an explicit voluntary choice.
                    env["initiative"](dict(character="mi", location="bus_inside", scene=scene))
                    self.assertIn('"mi": "swim"', llm.chat.call_args[0][0][0]["content"])
                    env["cameo"](dict(character="mi", location_id="bus_inside", scene=scene, dress="pioneer"))
                    prompt = llm.chat.call_args[0][0][0]["content"]
                    self.assertIn("AUTHORITATIVE CURRENT CLOTHING: swim", prompt)
                    self.assertIn('"mi": "swim"', prompt)
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
