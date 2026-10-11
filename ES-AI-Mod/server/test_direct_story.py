"""Delivery-bound direct stories, isolated from live configuration and paid APIs."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import copy
import os
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

import test_story_events as stories
import test_cameo_clothing as clothing
from test_story_events import module, DEV, WORKSHOP
from test_cameo_clothing import ROOTS, load


class DirectStoryTests(unittest.TestCase):
    def setup_story(self, root):
        fixture = stories.StoryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        mod = module(root)
        mod.manager = fixture.manager(mod)
        fixture.offer(mod.manager)
        return fixture, mod

    def request(self, fixture, mod, text="Slavya, yes"):
        return mod.manager.direct_request(fixture.token(mod.manager), text, ["sl", "mt"], "un")

    def test_ack_lifecycle_first_actual_speaker_and_replay(self):
        for root in existing_paths((DEV, WORKSHOP)):
            fixture, mod = self.setup_story(root)
            manager = mod.manager
            before = copy.deepcopy(manager.state)
            key = self.request(fixture, mod)
            a = manager.direct_delivery(key, "sl", "un", "Slavya, yes",
                                        dict(status="active", summary="Notebook search accepted"), "Let's search")
            b = manager.direct_delivery(key, "mt", "un", "Slavya, yes",
                                        dict(status="active", summary="Other candidate"), "Agreed")
            self.assertEqual(manager.state, before)
            manager.acknowledge_direct([a, b, a])
            self.assertEqual(manager.state["status"], "active")
            self.assertEqual(manager.state["summary"], "Notebook search accepted")
            self.assertEqual(manager.state["turns"], before["turns"] + 1)
            committed = copy.deepcopy(manager.state)
            manager.acknowledge_direct([b, a])
            self.assertEqual(manager.state, committed)
            key = self.request(fixture, mod, "I found and returned the notebook")
            ack = manager.direct_delivery(key, "sl", "un", "I found and returned the notebook",
                                         dict(status="completed", summary="Notebook returned"), "Thank you")
            manager.acknowledge_direct([ack])
            self.assertEqual(manager.state["status"], "completed")
            self.assertEqual(manager.state["closed_turn"], manager.state["turns"])

    def test_refusal_and_goal_acceptance_use_original_player_text(self):
        for root in existing_paths((DEV, WORKSHOP)):
            for text, update, expected in (("Slavya, no thanks", dict(status="active"), "declined"),
                ("Slavya, let's find the notebook", dict(status="active"), "active"),
                ("Slavya, maybe later?", dict(status="active"), "offered")):
                fixture, mod = self.setup_story(root)
                key = self.request(fixture, mod, text)
                ack = mod.manager.direct_delivery(key, "sl", "un", text, update, "Okay")
                ack["update"] = dict(status="completed")
                ack["player_text"] = "yes"
                mod.manager.acknowledge_direct([ack])
                self.assertEqual(mod.manager.state["status"], expected)

    def test_invalid_expired_stale_empty_and_bounded(self):
        for root in existing_paths((DEV, WORKSHOP)):
            fixture, mod = self.setup_story(root)
            manager = mod.manager
            key = self.request(fixture, mod)
            before = copy.deepcopy(manager.state)
            for token, cid, active, text in ((key, "unknown", "un", "Slavya, yes"),
                (key, "un", "un", "Slavya, yes"), (key, "sl", "mt", "Slavya, yes"),
                (key, "sl", "un", "yes"), ("injected", "sl", "un", "Slavya, yes")):
                self.assertIsNone(manager.direct_delivery(token, cid, active, text, dict(status="active"), "Hi"))
            self.assertIsNone(manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, " "))
            manager.acknowledge_direct([dict(token=key, delivery_id="invented"), None, dict(token=[]), {}])
            self.assertEqual(manager.state, before)
            ack = manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, "Hi")
            manager.pending_direct[key]["created"] -= mod.DIRECT_TTL + 1
            manager.acknowledge_direct([ack])
            self.assertEqual(manager.state, before)
            key = self.request(fixture, mod)
            ack = manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, "Hi")
            manager.commit(fixture.token(manager), None, "Newer exchange")
            newer = copy.deepcopy(manager.state)
            manager.acknowledge_direct([ack])
            self.assertEqual(manager.state, newer)
            for _ in range(140):
                self.request(fixture, mod)
            self.assertEqual(len(manager.pending_direct), 128)
            key = self.request(fixture, mod)
            for _ in range(8):
                self.assertIsNotNone(manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, "Hi"))
            self.assertIsNone(manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, "Hi"))

    def test_disabled_is_lazy_and_invalidates_pending(self):
        for root in existing_paths((DEV, WORKSHOP)):
            mod = module(root)
            config = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=False)))
            with patch.dict(sys.modules, config_loader=config), patch.object(mod.manager, "_load", side_effect=AssertionError("disabled I/O")):
                self.assertIsNone(mod.direct_request("yes", ["sl"], "un"))
                self.assertIsNone(mod.direct_context(dict(story_token="fake"), "sl"))
                self.assertIsNone(mod.direct_delivery({}, "sl", None, "Hi"))
                mod.acknowledge_direct([dict(token="fake", delivery_id="fake")])
            fixture, mod = self.setup_story(root)
            key = self.request(fixture, mod)
            ack = mod.manager.direct_delivery(key, "sl", "un", "Slavya, yes", None, "Hi")
            before = copy.deepcopy(mod.manager.state)
            with patch.dict(sys.modules, config_loader=config):
                mod.acknowledge_direct([ack])
            self.assertEqual(mod.manager.state, before)
            self.assertFalse(mod.manager.pending_direct)

    def test_failed_persistence_retries_and_concurrent_ack_is_once(self):
        for root in existing_paths((DEV, WORKSHOP)):
            fixture, mod = self.setup_story(root)
            key = self.request(fixture, mod)
            ack = mod.manager.direct_delivery(key, "sl", "un", "Slavya, yes", dict(status="active"), "Agreed")
            before = copy.deepcopy(mod.manager.state)
            with patch.object(mod.os, "replace", side_effect=OSError("disk full")):
                mod.manager.acknowledge_direct([ack])
            self.assertEqual(mod.manager.state, before)
            self.assertIn(key, mod.manager.pending_direct)
            threads = [threading.Thread(target=mod.manager.acknowledge_direct, args=([ack],)) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(mod.manager.state["turns"], before["turns"] + 1)
            self.assertEqual(mod.manager.state["status"], "active")
            self.assertNotIn(key, mod.manager.pending_direct)

    def test_actual_endpoints_prepare_generate_ack_before_private_next_turn(self):
        for root in existing_paths((DEV, WORKSHOP)):
            fixture, mod = self.setup_story(root)
            env, llm, conversation, modules = fixture.endpoint_env(root, mod, True)
            env["scene_diagnostics"] = lambda *a: dict(origin="chat", status="ok", address_id="sl", address_reason="name")
            env["resolve_direct_address"] = lambda *a: ["sl"]
            scene_memory = types.SimpleNamespace(ingest=Mock(), prompt=lambda *a: "")
            modules["scene_memory"] = scene_memory
            with patch.dict(sys.modules, modules):
                before = copy.deepcopy(mod.manager.state)
                result = env["chat"](dict(character="un", text="Slavya, yes"))
                self.assertEqual(result["reply"], "")
                llm.chat.assert_not_called()
                conversation.add_exchange.assert_not_called()
                self.assertEqual(mod.manager.state, before)
                payload = dict(character="sl", active_id="un", player_text="Slavya, yes", story_token=result["story_token"])
                delivered = env["cameo"](payload)
                self.assertIn("story_ack", delivered)
                self.assertNotIn("story:", delivered["reply"])
                self.assertEqual(mod.manager.state, before)
                self.assertEqual(llm.chat.call_args.args[0][-1]["content"], "Slavya, yes")
                llm.chat.return_value = '(normal) Hi [story:{"status":"completed"}]'
                random_reply = env["cameo"](dict(character="sl", player_text="yes"))
                self.assertNotIn("story_ack", random_reply)
                self.assertNotIn("story:", random_reply["reply"])
                self.assertEqual(mod.manager.state, before)
                # A private next request processes only opaque delivery IDs, not public speech.
                env["resolve_direct_address"] = lambda *a: None
                llm.chat.return_value = "(normal) Private reply"
                env["chat"](dict(character="un", text="private next turn", story_acks=[delivered["story_ack"]]))
                self.assertEqual(mod.manager.state["status"], "active")
                self.assertEqual(mod.manager.state["turns"], before["turns"] + 2)
                self.assertEqual(llm.chat.call_count, 3)
                self.assertEqual(conversation.add_exchange.call_count, 1)
                scene_memory.ingest.assert_called_with(None)

    def test_client_records_only_success_and_retries_bounded_snapshots(self):
        for root in ROOTS:
            env = clothing.ClothingTests().environment(root)
            env["es_ai_speakers"] = {"sl": lambda text: None}
            env["es_ai_internal_speaking"] = [False]
            ack = dict(token="a" * 36, delivery_id="b" * 36)
            env["es_ai_cameo_speak"]("sl", " ", story_ack=ack)
            self.assertFalse(env["ES_AI_STORY_ACKS"])
            env["es_ai_speakers"]["sl"] = Mock(side_effect=RuntimeError("not displayed"))
            with self.assertRaises(RuntimeError):
                env["es_ai_cameo_speak"]("sl", "Hello", story_ack=ack)
            self.assertFalse(env["ES_AI_STORY_ACKS"])
            self.assertFalse(env["es_ai_internal_speaking"][0])
            env["es_ai_speakers"]["sl"] = lambda text: None
            env["es_ai_cameo_speak"]("sl", "Hello", story_ack=ack)
            env["es_ai_story_ack_record"](ack)
            self.assertEqual(env["es_ai_story_ack_snapshot"](), [ack])
            load(os.path.join(root, "es_ai_api.rpy"), env, {"es_ai_chat_async", "es_ai_initiative_async"})
            env.update(ES_AI_FREE_SCENE=[False], es_ai_clock_begin=lambda **kw: None,
                       es_ai_run_async=lambda kind, fn: fn(),
                       es_ai_http=lambda route, payload: dict(ok=True, payload=payload))
            for call in (lambda: env["es_ai_chat_async"]("un", "private next turn"),
                         lambda: env["es_ai_initiative_async"]("un")):
                payload = call()["payload"]
                self.assertEqual(payload["story_acks"], [ack])
                self.assertNotIn("scene", payload)
                self.assertNotIn("story_token", payload)
            snapshot = env["es_ai_story_ack_snapshot"]()
            snapshot[0]["token"] = "changed"
            self.assertEqual(env["es_ai_story_ack_snapshot"](), [ack])
            for n in range(40):
                env["es_ai_story_ack_record"](dict(token="a" * 36, delivery_id=str(n).zfill(36)))
            self.assertEqual(len(env["es_ai_story_ack_snapshot"]()), 30)
            env["ES_AI_STORY_ACKS"][0] = (0, ack)
            self.assertEqual(len(env["es_ai_story_ack_snapshot"]()), 29)


if __name__ == "__main__":
    unittest.main()
