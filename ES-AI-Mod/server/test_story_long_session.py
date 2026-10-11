"""Repeatable offline sessions; scripted LLM output is not model-coherence proof."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_story_events as stories
from test_cameo_clothing import ROOTS
from test_scene_memory import module_at


class LongStorySessionTests(unittest.TestCase):
    def test_multiple_addressee_decision_boundaries(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            mod = stories.module(root)
            state = dict(status="offered", title="Notebook search", summary="Find a notebook")
            for text in ("Slavya, Olga, let's find the notebook",
                         "Slavya, Olga, yes",
                         "\u0421\u043b\u0430\u0432\u044f, \u041e\u043b\u044c\u0433\u0430, \u0434\u0430"):
                self.assertEqual(mod.player_decision(text, state, True), "accepted")
            self.assertEqual(mod.player_decision("Slavya, Olga, no thanks", state, True), "declined")
            for text in ("Slavya, Olga, let's find a note", "Slavya, Olga, yes?",
                         "She said Slavya, Olga, yes", "Unknown, Olga, yes", "Slavya, Olga, maybe"):
                self.assertEqual(mod.player_decision(text, state, True), "unknown")

    def test_36_turn_notebook_story_both_roots(self):
        for client_root, server_root in zip(ROOTS, existing_paths((stories.DEV, stories.WORKSHOP))):
            with self.subTest(root=server_root), tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                mod = stories.module(server_root)
                mod.manager = mod.StoryManager(os.path.join(directory, "story.json"))
                fixture = stories.StoryTests()
                env, llm, conversation, modules = fixture.endpoint_env(server_root, mod, True)
                env["cfg"]["story_events"]["intensity"] = "medium"
                memory = module_at(client_root, "scene_memory")
                modules["scene_memory"] = memory
                modules["config_loader"].user_data_dir = lambda: directory
                modules["characters_store"].characters = lambda: [dict(id=cid, age=30) for cid in ("un", "sl", "mt", "mi")]
                modules["characters_store"].get_character = lambda cid: dict(id=cid, name=cid, age=30, persona="Fictional adult volunteer")
                active, location = "un", "square"
                prompts, transcript = [], []
                env["scene_diagnostics"] = lambda *a: dict(origin="chat", status="ok", address_id="sl", address_reason="name")
                env["resolve_direct_address"] = lambda *a: None

                def scripted(messages, **kwargs):
                    prompts.append(copy.deepcopy(messages))
                    return scripted.reply

                llm.chat.side_effect = scripted
                with patch.dict(sys.modules, modules):
                    for turn in range(1, 37):
                        text = "Check the notebook search, step %s" % turn
                        update = None
                        if turn == 7:
                            update = dict(status="offered", title="First notebook offer", summary="Find a notebook", participants=["sl", "mt"])
                        elif turn == 8:
                            text = "No thanks"
                            update = dict(status="active", summary="Wrong acceptance")
                        elif 9 <= turn <= 18:
                            update = dict(status="offered", title="Too soon", summary="Wrong replacement")
                        elif turn == 19:
                            update = dict(status="offered", title="Second notebook offer", summary="Find a notebook", participants=["sl", "mt"])
                        elif turn == 20:
                            text = "Slavya, Olga, let's find the notebook"
                            update = dict(status="active", summary="Volunteers accepted notebook search")
                        elif turn == 21:
                            text = "No, the notebook is not there"
                            update = dict(status="declined", summary="Wrong abandonment")
                        elif turn == 23:
                            active, location = "sl", "library"
                            text = "We arrived at the library to search the shelf"
                        elif turn == 24:
                            text = "Olga, I found the notebook on the library shelf"
                            update = dict(status="active", summary="Notebook found on library shelf")
                        elif turn == 26:
                            env["cfg"]["story_events"]["enabled"] = False
                            update = dict(status="completed", summary="Wrong paused completion")
                        elif turn == 27:
                            env["cfg"]["story_events"]["enabled"] = True
                        elif turn == 32:
                            active, location = "mt", "square"
                            text = "We brought the notebook back to the square"
                        elif turn == 36:
                            text = "I handed the found notebook back to its owner"
                            update = dict(status="completed", summary="Notebook returned to its owner")
                        scripted.reply = "(normal) Volunteer reply %s" % turn
                        if update:
                            scripted.reply += " [story:%s]" % json.dumps(update)
                        if turn == 22:
                            scripted.reply += ' [story:{"status":[]}]'
                        if turn == 25:
                            scripted.reply += ' [story:{"status":"completed"}] [story:{"status":"declined"}]'
                        before = copy.deepcopy(mod.manager.state)
                        direct = turn in (20, 24)
                        env["resolve_direct_address"] = (lambda *a: ["sl", "mt"]) if turn == 20 else (lambda *a: ["mt"]) if direct else (lambda *a: None)
                        payload = dict(character=active, text=text, location=location)
                        if turn in (20, 23, 24, 32):
                            witnesses = ["un", "sl", "mt"] if turn == 20 else ["sl", "mt"] if turn in (23, 24) else ["mt", "un"]
                            payload["public_events"] = [dict(id="long_%s" % turn, location_id=location,
                                witnesses=witnesses, speaker_id="player", text=text)]
                        out = env["chat"](payload)
                        self.assertTrue(out["ok"], (turn, out))
                        if direct:
                            self.assertEqual(out["reply"], "")
                            self.assertEqual(mod.manager.state, before)
                            acknowledgements = []
                            for cid in out["cameo"]:
                                delivered = env["cameo"](dict(character=cid, active_id=active,
                                    player_text=text, story_token=out["story_token"], location_id=location))
                                self.assertNotIn("story:", delivered["reply"])
                                acknowledgements.append(delivered["story_ack"])
                            self.assertEqual(mod.manager.state, before)
                            if turn == 24:
                                # Restart after generation but before the visible-speech ACK.
                                mod.manager = mod.StoryManager(mod.manager.path)
                                mod.manager.prepare(env["cfg"]["story_events"], ["un", "sl", "mt"], active)
                                self.assertEqual(mod.manager.state, before)
                            speech = dict(id="long_speech_%s" % turn, location_id=location,
                                witnesses=["sl", "mt"], speaker_id="mt", text="The library shelf clue" if turn == 24 else "Ready to search")
                            calls = llm.chat.call_count
                            flushed = env["scene_flush"](dict(story_acks=acknowledgements, public_events=[speech]))
                            self.assertTrue(flushed["ok"])
                            self.assertEqual(llm.chat.call_count, calls)
                            self.assertEqual(mod.manager.state["turns"], before["turns"] + 1)
                            committed = copy.deepcopy(mod.manager.state)
                            env["scene_flush"](dict(story_acks=acknowledgements))
                            self.assertEqual(mod.manager.state, committed)
                        else:
                            self.assertNotIn("story:", out["reply"])
                        state = mod.manager.state
                        expected = "inactive" if turn < 7 else "offered" if turn in (7, 19) else "declined" if turn < 19 else "completed" if turn == 36 else "active"
                        self.assertEqual(state["status"], expected, turn)
                        if 8 <= turn <= 18:
                            self.assertEqual(state["title"], "First notebook offer")
                            self.assertEqual(state["summary"], "Find a notebook")
                        if turn == 26:
                            self.assertEqual(state, before)
                        with open(mod.manager.path, encoding="utf-8") as stream:
                            self.assertEqual(json.load(stream), state)
                        transcript.append((turn, active, location, state["status"]))
                    self.assertEqual(len(transcript), 36)
                    self.assertEqual(mod.manager.state["turns"], 35)
                    self.assertEqual(mod.manager.state["closed_turn"], 35)
                    self.assertEqual(mod.manager.state["summary"], "Notebook returned to its owner")
                    self.assertEqual(llm.chat.call_count, 37)  # Two purposeful speakers on turn 20.
                    self.assertEqual(conversation.add_exchange.call_count, 34)
                    memory._CACHE.clear()
                    self.assertEqual(memory.prompt("mi"), "")
                    self.assertIn("library", memory.prompt("sl"))
                    self.assertNotIn("library shelf", memory.prompt("un"))
                    self.assertIn("library shelf", memory.prompt("mt"))
                    with open(memory._path(), encoding="utf-8") as stream:
                        public = json.load(stream)["npcs"]
                    self.assertTrue(any(e["speaker_id"] == "mt" and e["location_id"] == "library" for e in public["sl"]))
                    self.assertIn("Notebook found on library shelf", prompts[-1][0]["content"])
                    reloaded = mod.StoryManager(mod.manager.path)
                    reloaded.prepare(env["cfg"]["story_events"], ["un", "sl", "mt"], "un")
                    self.assertEqual(reloaded.state, mod.manager.state)


if __name__ == "__main__":
    unittest.main()
