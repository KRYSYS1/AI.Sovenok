"""Deferred consent regressions in both roots, with isolated state and scripted replies."""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_story_events as stories


YES = "\u0414\u0430, \u0437\u0430\u0432\u0442\u0440\u0430 \u043f\u043e\u043c\u043e\u0433\u0443 \u043f\u043e\u0438\u0441\u043a\u0430\u0442\u044c."
TOMORROW = "\u0437\u0430\u0432\u0442\u0440\u0430"
TITLE = "\u041e\u0442\u0432\u0451\u0440\u0442\u043a\u0430 \u0443 \u043a\u0440\u044b\u043b\u044c\u0446\u0430"
OFFER = dict(status="offered", title=TITLE, summary="Shurik lost a screwdriver; help search tomorrow", participants=["sh"])
CHOICES = [dict(id="help", text=YES), dict(id="refuse", text="No thanks")]
CONFIG = dict(enabled=True, choices_enabled=True, intensity="high")
IDS = ["uv", "sh"]


class AcceptanceTests(unittest.TestCase):
    def test_scoped_negation_selected_reply_ack_restart(self):
        cases = (
            ("\u041e\u0442\u0432\u0451\u0440\u0442\u043a\u0443 \u0428\u0443\u0440\u0438\u043a\u0430 \u043f\u043e\u043c\u043e\u0433\u0443 \u043f\u043e\u0438\u0441\u043a\u0430\u0442\u044c \u0437\u0430\u0432\u0442\u0440\u0430 \u043f\u0440\u0438 \u0434\u043d\u0435\u0432\u043d\u043e\u043c \u0441\u0432\u0435\u0442\u0435, \u0430 \u043d\u0435 \u0441\u0435\u0439\u0447\u0430\u0441.", "active"),
            ("\u043d\u0435 \u0441\u0435\u0439\u0447\u0430\u0441 \u0430 \u0437\u0430\u0432\u0442\u0440\u0430 \u043f\u043e\u043c\u043e\u0433\u0443 \u043d\u0430\u0439\u0442\u0438 \u043e\u0442\u0432\u0451\u0440\u0442\u043a\u0443", "active"),
            ("\u0437\u0430\u0432\u0442\u0440\u0430 \u043d\u0435 \u0431\u0443\u0434\u0443 \u0438\u0441\u043a\u0430\u0442\u044c \u043e\u0442\u0432\u0451\u0440\u0442\u043a\u0443", "offered"),
            ("\u043d\u0435 \u043e\u0431\u0435\u0449\u0430\u044e \u043f\u043e\u043c\u043e\u0433\u0443", "offered"),
            ("\u043c\u043e\u0436\u0435\u0442 \u0437\u0430\u0432\u0442\u0440\u0430", "offered"),
            ("\u043f\u043e\u043c\u043e\u0433\u0443 \u0437\u0430\u0432\u0442\u0440\u0430, \u043d\u043e \u043d\u0435 \u0445\u043e\u0447\u0443 \u0443\u0447\u0430\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c", "declined"),
            ("\u043d\u0435 \u0441\u0435\u0439\u0447\u0430\u0441", "offered"),
            ("\u0437\u0430\u0432\u0442\u0440\u0430 \u043f\u043e\u043c\u043e\u0433\u0443 \u043d\u0430\u0439\u0442\u0438 \u043e\u0442\u0432\u0451\u0440\u0442\u043a\u0443 \u0438 \u043a\u0443\u043f\u0438\u0442\u044c \u0445\u043b\u0435\u0431", "offered"),
        )
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for text, expected in cases:
                for tagged in (False, True):
                    with self.subTest(root=root, text=text, tagged=tagged), tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                        mod = stories.module(root)
                        mod.manager = mod.StoryManager(os.path.join(directory, "story.json"))
                        mod.manager._load()
                        mod.manager.state.update(turns=8)
                        opening = mod.manager.prepare(CONFIG, IDS, "sh")
                        options = [dict(id="search_tomorrow", text=text), CHOICES[1]]
                        menu = mod.manager.stage_choices(opening, options, OFFER, "Will you help?")
                        mod.manager.commit(opening, OFFER, "Will you help?")
                        before = copy.deepcopy(mod.manager.state)
                        env, llm, _, modules = stories.StoryTests().endpoint_env(root, mod, True)
                        env["cfg"]["story_events"] = CONFIG.copy()
                        modules["characters_store"].characters = lambda: [dict(id=cid) for cid in IDS]
                        env["resolve_cameo_intent"] = lambda *a: []
                        llm.chat.return_value = "We can wait." + (
                            " [story:%s]" % json.dumps(dict(status="offered")) if tagged else "")
                        payload = dict(character="uv", text=text, location="square",
                                       clock=dict(enabled=True, time="23:55", phase="night"),
                                       story_choice=dict(token=menu["token"], version=menu["version"], id="search_tomorrow"))
                        with patch.dict(sys.modules, modules):
                            result = env["chat"](payload)
                            self.assertTrue(result["ok"], result)
                            self.assertEqual(mod.manager.state, before)
                            self.assertIn("story_ack", result)
                            for key in ("goto", "switch_primary", "travel_with", "travel_all"):
                                self.assertFalse(result.get(key), key)
                            llm.chat.assert_called_once()
                            mod.manager = mod.StoryManager(mod.manager.path)
                            env["scene_flush"](dict(story_acks=[result["story_ack"]]))
                            committed = copy.deepcopy(mod.manager.state)
                            env["scene_flush"](dict(story_acks=[result["story_ack"]]))
                        self.assertEqual(mod.manager.state, committed)
                        self.assertEqual(committed["status"], expected)
                        self.assertEqual(committed["planned_time"], TOMORROW if expected == "active" else "")
                        self.assertEqual(committed["version"], before["version"] + 1)
                        self.assertEqual(committed["turns"], before["turns"] + 1)
                        self.assertEqual(committed["decisions"], [options[0]])
                        for key in ("title", "summary", "participants"):
                            self.assertEqual(committed[key], before[key])
                        self.assertEqual(payload["clock"]["time"], "23:55")
                        reloaded = mod.StoryManager(mod.manager.path)
                        reloaded._load()
                        self.assertEqual(reloaded.state, committed)

    def test_deferred_decision_boundaries(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod = stories.module(root)
            for text in (YES, "yes I will help tomorrow", "Shurik, yes I'll help tomorrow"):
                self.assertEqual(mod.player_decision(text, OFFER), "accepted", (root, text))
            for text in ("maybe tomorrow", "yes I will buy bread tomorrow", "yes if I can help tomorrow",
                         "\u043c\u043e\u0436\u0435\u0442 \u0437\u0430\u0432\u0442\u0440\u0430",
                         "\u043d\u0435 \u043e\u0431\u0435\u0449\u0430\u044e", YES + "?",
                         "\u043d\u0435 \u0437\u0430\u0432\u0442\u0440\u0430, \u0441\u0435\u0439\u0447\u0430\u0441"):
                self.assertEqual(mod.player_decision(text, OFFER), "unknown", (root, text))
            self.assertEqual(mod.player_decision("\u0434\u0430 \u043d\u043e \u043d\u0435 \u0445\u043e\u0447\u0443 \u0443\u0447\u0430\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c", OFFER), "declined")
            self.assertEqual(mod.player_decision(YES, dict(OFFER, status="active")), "unknown")

    def test_semantic_transition_preserves_task_without_model_consent(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for update in (None, dict(status="offered", title="Wrong UV task", summary="Wrong", participants=["uv"]),
                           dict(status="active", title="Wrong UV task", summary="Already searching tonight", participants=["uv"])):
                with self.subTest(root=root, update=update), tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                    mod = stories.module(root)
                    manager = mod.StoryManager(os.path.join(directory, "story.json"))
                    manager._load()
                    manager.state.update(turns=8)
                    token = manager.prepare(CONFIG, IDS, "sh")
                    manager.commit(token, OFFER, "Will you help?", player_text="yes")
                    self.assertEqual(manager.state["status"], "offered")  # No retroactive consent to a new offer.
                    manager.commit(manager.prepare(CONFIG, IDS, "uv"), update, "Tomorrow then", player_text=YES)
                    self.assertEqual(manager.state["status"], "active")
                    self.assertEqual(manager.state["planned_time"], TOMORROW)
                    self.assertEqual(manager.state["participants"], ["sh"])
                    self.assertEqual(manager.state["title"], TITLE)
                    self.assertEqual(manager.state["summary"], OFFER["summary"])
                    reloaded = mod.StoryManager(manager.path)
                    prompt = reloaded.prepare(CONFIG, IDS, "uv")["context"]
                    self.assertEqual(reloaded.state, manager.state)
                    self.assertIn("do not demand action tonight", prompt)
                    self.assertIn("Never advance the clock", prompt)

    def test_36_turn_shurik_offer_then_uv_selected_acceptance(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for tagged in (False, True):
                with self.subTest(root=root, tagged=tagged), tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                    mod = stories.module(root)
                    mod.manager = mod.StoryManager(os.path.join(directory, "story.json"))
                    env, llm, conversation, modules = stories.StoryTests().endpoint_env(root, mod, True)
                    env["cfg"]["story_events"] = CONFIG.copy()
                    env["scene_diagnostics"] = lambda *a: dict(origin="chat", status="ok", address_id="sh", address_reason="name")
                    modules["characters_store"].characters = lambda: [dict(id=cid) for cid in IDS]
                    with patch.dict(sys.modules, modules):
                        for turn in range(1, 37):
                            llm.chat.return_value = "(normal) We can wait."
                            payload = dict(character="uv", text="Ordinary conversation", location="square",
                                           clock=dict(enabled=True, time="23:55", phase="night"))
                            if turn == 9:
                                env["resolve_direct_address"] = lambda *a: ["sh"]
                                payload["text"] = "Shurik, what happened?"
                                out = env["chat"](payload)
                                self.assertEqual(out["reply"], "")
                                llm.chat.return_value += " [story:%s] [choices:%s]" % (json.dumps(OFFER), json.dumps(dict(options=CHOICES)))
                                before = copy.deepcopy(mod.manager.state)
                                direct = env["cameo"](dict(character="sh", active_id="uv", player_text=payload["text"],
                                                          story_token=out["story_token"], location_id="square"))
                                self.assertEqual(mod.manager.state, before)
                                choice = direct["choices"]
                                env["scene_flush"](dict(story_acks=[direct["story_ack"]]))
                                self.assertEqual(mod.manager.state["status"], "offered")
                                env["resolve_direct_address"] = lambda *a: None
                                continue
                            if turn == 10:
                                payload.update(text=YES, story_choice=dict(token=choice["token"], version=choice["version"], id="help"))
                                if tagged:
                                    llm.chat.return_value += " [story:%s]" % json.dumps(dict(OFFER, title="Wrong replacement", participants=["uv"]))
                            out = env["chat"](payload)
                            self.assertTrue(out["ok"], out)
                            self.assertFalse(out.get("goto"))
                            self.assertFalse(out.get("switch_primary"))
                            self.assertFalse(out.get("travel_with"))
                            self.assertFalse(out.get("travel_all"))
                            self.assertEqual(payload["clock"]["time"], "23:55")
                            if turn == 10:
                                self.assertEqual(mod.manager.state["status"], "offered")
                                mod.manager = mod.StoryManager(mod.manager.path)  # Pending validated choice survives restart.
                                env["scene_flush"](dict(story_acks=[out["story_ack"]]))
                                committed = copy.deepcopy(mod.manager.state)
                                env["scene_flush"](dict(story_acks=[out["story_ack"]]))
                                self.assertEqual(mod.manager.state, committed)
                            if turn >= 10:
                                self.assertEqual(mod.manager.state["status"], "active")
                                self.assertEqual(mod.manager.state["planned_time"], TOMORROW)
                                self.assertEqual(mod.manager.state["participants"], ["sh"])
                                self.assertEqual(mod.manager.state["title"], TITLE)
                            if turn != 10:
                                env['scene_flush'](dict(story_acks=[out['story_ack']]))
                        self.assertEqual(mod.manager.state["turns"], 36)
                        self.assertEqual(mod.manager.state["decisions"], [CHOICES[0]])
                        primary_calls = [call for call in llm.chat.call_args_list
                                         if call.kwargs.get('override_max_tokens') != 384]
                        recovery_calls = [call for call in llm.chat.call_args_list
                                          if call.kwargs.get('override_max_tokens') == 384]
                        self.assertEqual(len(primary_calls), 36)
                        self.assertEqual(len(recovery_calls), 26)  # Due stays due after invalid repair output.

    def test_direct_acceptance_waits_for_ack_and_stale_cannot_accept(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            with self.subTest(root=root), tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                mod = stories.module(root)
                manager = mod.StoryManager(os.path.join(directory, "story.json"))
                manager._load()
                manager.state.update(turns=8)
                manager.commit(manager.prepare(CONFIG, IDS, "sh"), OFFER, "Help tomorrow?")
                token = manager.prepare(CONFIG, IDS, "uv")
                key = manager.direct_request(token, YES, ["sh"], "uv")
                ack = manager.direct_delivery(key, "sh", "uv", YES, None, "Agreed for tomorrow")
                self.assertEqual(manager.state["status"], "offered")
                restarted = mod.StoryManager(manager.path)
                self.assertEqual(restarted.acknowledge_direct([ack]), [ack])
                self.assertEqual(restarted.state["status"], "active")
                self.assertEqual(restarted.state["planned_time"], TOMORROW)
                # A fresh active-state yes cannot cancel, reschedule or duplicate the story.
                restarted.commit(restarted.prepare(CONFIG, IDS, "uv"), None, "Fine", player_text="No")
                self.assertEqual(restarted.state["status"], "active")
                restarted.commit(token, dict(status="offered", title="Stale"), "Stale", player_text=YES)
                self.assertEqual(restarted.state["title"], TITLE)

    def test_load_does_not_migrate_historical_choice_to_acceptance(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            with tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                mod = stories.module(root)
                manager = mod.StoryManager(os.path.join(directory, "story.json"))
                manager._load()
                manager.state.update(turns=8)
                manager.commit(manager.prepare(CONFIG, IDS, "sh"), OFFER, "Help?")
                manager.state["decisions"] = [CHOICES[0]]
                manager.commit(manager.prepare(CONFIG, IDS, "uv"), None, "Waiting", player_text="Other topic")
                reloaded = mod.StoryManager(manager.path)
                with patch.object(mod.os, "replace", side_effect=AssertionError("Read-only prepare wrote state")):
                    reloaded.prepare(CONFIG, IDS, "uv")
                self.assertEqual(reloaded.state["status"], "offered")
                self.assertEqual(reloaded.state["planned_time"], "")


if __name__ == "__main__":
    unittest.main()
