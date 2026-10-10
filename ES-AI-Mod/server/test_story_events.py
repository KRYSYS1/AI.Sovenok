"""Offline story state and actual endpoint tests; never import live main/config."""
import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from test_cameo_clothing import load

DEV = os.path.dirname(__file__)
WORKSHOP = r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310\server"
TEMP = r"C:\Users\kolan\AppData\Local\Temp\kilo"
OPTIONS = dict(enabled=True, intensity="low")


def module(root):
    spec = importlib.util.spec_from_file_location("story_events", os.path.join(root, "story_events.py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP)
        self.addCleanup(self.temp.cleanup)

    def manager(self, mod):
        return mod.StoryManager(os.path.join(self.temp.name, "story_events.json"))

    def token(self, manager, readonly=False):
        return manager.prepare(OPTIONS, ["un", "sl", "mt"], "un", readonly)

    def offer(self, manager):
        for _ in range(400):
            token = self.token(manager)
            if token["eligible"]:
                manager.commit(token, dict(status="offered", title="Camp task", summary="Find a notebook",
                                          participants=["sl", "unknown", "sl", "un"]), "Want to help?")
                self.assertEqual(manager.state["status"], "offered")
                return
            manager.commit(token, None, "Ordinary reply")
        self.fail("No deterministic eligible offer")

    def test_disabled_lazy_defaults_and_paths(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            manager = self.manager(mod)
            with patch.object(mod, "default_path", side_effect=AssertionError("must not load")):
                self.assertIsNone(manager.prepare(None, [], "un"))
                self.assertFalse(manager.commit(None, None, "Hi"))
                self.assertIsNone(mod.prepare({"enabled": False}))
            self.assertIsNone(manager.state)
            self.assertFalse(os.path.exists(manager.path))
            self.assertEqual(mod.settings(None), dict(enabled=False, intensity="low"))
            self.assertEqual(mod.settings(dict(enabled="true", intensity=[])), dict(enabled=False, intensity="low"))
            for key, value in (("enabled", 1), ("intensity", "max"), ("reset", True)):
                self.assertFalse(mod.valid_setting(key, value))
            config = types.SimpleNamespace(user_data_dir=lambda: self.temp.name)
            with patch.dict(sys.modules, config_loader=config):
                self.assertEqual(mod.default_path(), os.path.join(self.temp.name, "story_events.json"))
            with patch.dict(sys.modules, config_loader=types.SimpleNamespace()):
                self.assertEqual(mod.default_path(), os.path.join(root, "memory", "story_events.json"))

    def test_tags_balanced_bounded_and_independent(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            tag = '[story:' + json.dumps(dict(status="offered", title='Brackets ] and escaped " quote',
                                             summary="Nested {data}", participants=["un"])) + ']'
            reply, update = mod.parse_tags("Hello " + tag + " [action:goto:beach] [action:dress:swim]")
            self.assertEqual(update["participants"], ["un"])
            self.assertNotIn("story:", reply)
            self.assertIn("[action:goto:beach]", reply)
            for bad in ('[story:{oops}]', '[story:{"status":[]}]',
                        '[story:{"status":"offered","summary":"' + "x" * 3000 + '"}]',
                        '[action:story:offer|title|goal]', '[story:{"participants":["un"]',
                        '[story:unfinished'):
                cleaned, update = mod.parse_tags("Hi " + bad + " [action:time:night]")
                self.assertEqual(" ".join(cleaned.split()), "Hi [action:time:night]", bad)
                self.assertIsNone(update)
            self.assertIsNone(mod.parse_tags(tag + tag)[1])

    def test_lifecycle_reload_cooldown_and_sanitization(self):
        for root in (DEV, WORKSHOP):
            with self.subTest(root=root):
                mod = module(root)
                manager = self.manager(mod)
                # Each root gets an independent test state.
                manager.path += str(len(root))
                self.offer(manager)
                self.assertEqual(manager.state["participants"], ["sl", "un"])
                self.assertFalse(self.token(manager)["eligible"])
                token = self.token(manager)
                manager.commit(token, dict(status="completed"), "Premature")
                self.assertEqual(manager.state["status"], "offered")
                manager.commit(self.token(manager), dict(status="active", notes="[action:goto:beach]\n" + "x" * 1000), "Yes", player_text="Yes")
                self.assertEqual(manager.state["status"], "active")
                self.assertLessEqual(len(manager.state["notes"]), 300)
                self.assertNotIn("[", manager.state["notes"])
                manager.commit(self.token(manager), dict(status="completed", summary="Notebook returned"), "Thanks")
                reloaded = mod.StoryManager(manager.path)
                self.token(reloaded)
                self.assertEqual(reloaded.state, manager.state)
                for _ in range(10):
                    self.assertFalse(self.token(manager)["eligible"])
                    manager.commit(self.token(manager), dict(status="offered", title="Too soon", summary="No"), "Hi")
                    self.assertEqual(manager.state["summary"], "Notebook returned")
                    self.assertEqual(manager.state["status"], "completed")
                self.offer(manager)
                manager.commit(self.token(manager), dict(status="declined", notes="Player refused"), "No pressure")
                self.assertEqual(manager.state["status"], "declined")
                self.assertFalse(self.token(manager)["eligible"])

    def test_stale_failed_readonly_and_initiative(self):
        mod = module(DEV)
        manager = self.manager(mod)
        self.offer(manager)
        stale = self.token(manager)
        manager.commit(self.token(manager), dict(status="active", summary="Player accepted"), "Yes", player_text="Yes")
        turns = manager.state["turns"]
        manager.commit(stale, dict(status="declined", summary="Stale"), "Reply")
        self.assertEqual(manager.state["summary"], "Player accepted")
        self.assertEqual(manager.state["turns"], turns + 1)
        before = dict(manager.state)
        self.assertFalse(manager.commit(self.token(manager), dict(status="completed"), ""))
        self.assertFalse(manager.commit(self.token(manager, True), dict(status="completed"), "Hi"))
        self.assertFalse(manager.commit(self.token(manager), dict(status="completed"), "Hi", False))
        self.assertEqual(before, manager.state)
        with patch.object(mod.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(manager.commit(self.token(manager), dict(status="completed"), "Hi"))
        self.assertEqual(before, manager.state)
        self.assertEqual(os.listdir(self.temp.name), ["story_events.json"])

    def endpoint_env(self, root, mod, enabled):
        cfg = dict(story_events=dict(enabled=enabled, intensity="low"))
        env = dict(cfg=cfg, re=re, threading=types.SimpleNamespace(Thread=Mock()), time=time,
                   os=os, json=json, BASE_DIR=root, _LOCATION_ALIASES=[])
        load(os.path.join(root, "main.py"), env, rpy=False)
        env.update(scene_event=Mock(), scene_diagnostics=lambda *a: {"origin": "chat", "status": "ok"},
                   resolve_direct_address=lambda *a: None, resolve_cameo_intent=lambda *a: [],
                   scene_prompt=lambda *a: "\nROSTER", clock_prompt=lambda *a: "\nCLOCK")
        llm = types.SimpleNamespace(chat=Mock(return_value='(normal) Hi [story:{"status":"active"}] [action:dress:swim]'),
                                    sanitize_in_character=lambda s: s, strip_prompt_leak=lambda s, p: s,
                                    quick_summarize=Mock())
        conversation = types.SimpleNamespace(build_history_block=lambda *a, **k: [{"role": "system", "content": "Persona"}],
                                              add_exchange=Mock(), maybe_compress=Mock(), get_history=lambda *a: ([], ""))
        characters = types.SimpleNamespace(characters=lambda: [dict(id="un"), dict(id="sl")],
                                           get_character=lambda cid: dict(id=cid, name=cid, persona="Persona"),
                                           map_emotion=lambda *a: "normal", player_block=lambda: "", reply_rules=lambda ch: "")
        config = types.SimpleNamespace(cfg=cfg, save_config=Mock())
        env["config_loader"] = config
        return env, llm, conversation, dict(story_events=mod, config_loader=config,
                                           llm_client=llm, conversation=conversation, characters_store=characters)

    def test_concurrent_exchanges_do_not_overwrite_newer_plot(self):
        mod = module(DEV)
        manager = self.manager(mod)
        self.offer(manager)
        token = self.token(manager)
        initial_turns = manager.state["turns"]
        barrier = threading.Barrier(6)
        def worker():
            barrier.wait()
            manager.commit(token, dict(status="active", summary="Accepted"), "Reply", player_text="Yes")
        threads = [threading.Thread(target=worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(manager.state["turns"], initial_turns + 6)
        self.assertEqual(manager.state["status"], "active")
        self.assertEqual(manager.state["summary"], "Accepted")
        reloaded = mod.StoryManager(manager.path)
        self.token(reloaded)
        self.assertEqual(manager.state, reloaded.state)

    def test_actual_chat_acceptance_refusal_and_pending_disable(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            mod.manager = self.manager(mod)
            mod.manager.path += str(len(root))
            self.offer(mod.manager)
            env, llm, _, modules = self.endpoint_env(root, mod, True)
            with patch.dict(sys.modules, modules):
                llm.chat.return_value = 'Hi [story:{"status":"active","summary":"Player agreed"}]'
                self.assertTrue(env["chat"](dict(text="Yes, I will help"))["ok"])
                self.assertEqual(mod.manager.state["status"], "active")
                llm.chat.return_value = 'No pressure [story:{"status":"declined","notes":"Player refused"}]'
                self.assertTrue(env["chat"](dict(text="No, I do not want this"))["ok"])
                self.assertEqual(mod.manager.state["status"], "declined")
                self.assertEqual(mod.manager.state["summary"], "Player agreed")
                before = dict(mod.manager.state)
                def disabling(messages):
                    env["cfg"]["story_events"]["enabled"] = False
                    return 'Hi [story:{"status":"offered","title":"New","summary":"New"}]'
                llm.chat.side_effect = disabling
                self.assertTrue(env["chat"](dict(text="Hello"))["ok"])
                self.assertEqual(before, mod.manager.state)

    def test_actual_endpoints_success_failure_fallback_and_readonly(self):
        for root in (DEV, WORKSHOP):
            for enabled in (False, True):
                with self.subTest(root=root, enabled=enabled):
                    mod = module(root)
                    mod.manager = self.manager(mod)
                    mod.manager.path += str(len(root)) + str(enabled)
                    env, llm, conversation, modules = self.endpoint_env(root, mod, enabled)
                    with patch.dict(sys.modules, modules):
                        out = env["chat"](dict(text="Hello", character="un", location="square"))
                        self.assertTrue(out["ok"])
                        self.assertEqual(out["reply"], "Hi")
                        self.assertEqual(out["dress"], "swim")
                        llm.chat.assert_called_once()
                        conversation.add_exchange.assert_called_once_with("un", "Hello", "Hi")
                        prompt = llm.chat.call_args.args[0][0]["content"]
                        self.assertEqual("OPTIONAL CAMP STORY" in prompt, enabled)
                        if enabled:
                            self.assertEqual(mod.manager.state["turns"], 1)
                            self.assertEqual(mod.manager.state["status"], "inactive")
                        else:
                            self.assertIsNone(mod.manager.state)
                            self.assertFalse(os.path.exists(mod.manager.path))
                        for endpoint in ("initiative", "cameo"):
                            llm.chat.reset_mock()
                            result = env[endpoint](dict(character="un"))
                            self.assertEqual(result["reply"], "Hi")
                            llm.chat.assert_called_once()
                        if enabled:
                            self.assertEqual(mod.manager.state["turns"], 1)
                        llm.chat.side_effect = RuntimeError("offline failure")
                        self.assertFalse(env["chat"](dict(text="Hello"))["ok"])
                        llm.chat.side_effect = None
                        llm.chat.return_value = '[story:{"status":"offered","title":"No","summary":"Empty"}]'
                        llm.chat.reset_mock()
                        fallback = env["chat"](dict(text="Hello"))
                        self.assertTrue(fallback["reply"])
                        self.assertEqual(llm.chat.call_count, 2)  # Existing empty-response retry only.
                        if enabled:
                            self.assertEqual(mod.manager.state["turns"], 1)

    def test_copies_identical_and_config_whitelist(self):
        with open(os.path.join(DEV, "story_events.py"), "rb") as stream:
            expected = stream.read()
        with open(os.path.join(WORKSHOP, "story_events.py"), "rb") as stream:
            self.assertEqual(expected, stream.read())
        for root in (DEV, WORKSHOP):
            mod = module(root)
            env, _, _, modules = self.endpoint_env(root, mod, False)
            with open(os.path.join(root, "main.py"), encoding="utf-8-sig") as stream:
                tree = ast.parse(stream.read())
            assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and
                              any(isinstance(t, ast.Name) and t.id == "_CFG_SECTIONS" for t in n.targets))
            exec(compile(ast.Module(body=[assignment], type_ignores=[]), "config", "exec"), env)
            with patch.dict(sys.modules, modules):
                for key, value in (("enabled", "yes"), ("intensity", 4), ("unknown", True)):
                    self.assertFalse(env["config_set"](dict(section="story_events", key=key, value=value))["ok"])
                modules["config_loader"].save_config.assert_not_called()
                for key, value in (("enabled", True), ("intensity", "high")):
                    self.assertTrue(env["config_set"](dict(section="story_events", key=key, value=value))["ok"])
                self.assertEqual(env["cfg"]["story_events"], dict(enabled=True, intensity="high"))

    def test_decision_detector_clear_refusals(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            for text in ("\u043d\u0435 \u0445\u043e\u0447\u0443 \u0443\u0447\u0430\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c", "\u043d\u0435 \u0445\u043e\u0447\u0443 \u044d\u0442\u0438\u043c \u0437\u0430\u043d\u0438\u043c\u0430\u0442\u044c\u0441\u044f", "\u043d\u0435 \u0438\u043d\u0442\u0435\u0440\u0435\u0441\u043d\u043e",
                         "\u041d\u0435\u0442, \u043d\u0435 \u0445\u043e\u0447\u0443!", "\u0434\u0430\u0432\u0430\u0439 \u0431\u0435\u0437 \u044d\u0442\u043e\u0433\u043e", "not interested", "No thanks.",
                         "I don't want to participate", "I don\u2019t want to participate", "\u043d\u0435\u0442"):
                with self.subTest(root=root, text=text):
                    self.assertEqual(mod.player_decision(text), "declined")

    def test_decision_detector_explicit_acceptance_and_unknown(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            for text in ("\u0434\u0430", "\u0434\u0430\u0432\u0430\u0439", "\u0441\u043e\u0433\u043b\u0430\u0441\u0435\u043d", "\u0445\u043e\u0440\u043e\u0448\u043e, \u0434\u0430\u0432\u0430\u0439", "YES!", "let's do it",
                         "\u044f \u043f\u043e\u043c\u043e\u0433\u0443", "\u043f\u043e\u0439\u0434\u0451\u043c \u0438\u0441\u043a\u0430\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u043a\u0443", "Yes, I will help", "I'll help"):
                with self.subTest(root=root, text=text):
                    self.assertEqual(mod.player_decision(text), "accepted")
            for text in (None, "", "Maybe", "Tell me more", "yes?", "'yes'", "She said yes",
                         "\u043d\u0435 \u0445\u043e\u0447\u0443 \u0438\u0434\u0442\u0438 \u0442\u0443\u0434\u0430 \u0434\u0430\u0432\u0430\u0439 \u0437\u0434\u0435\u0441\u044c", "\u0434\u0430\u0432\u0430\u0439 \u043d\u0435 \u0431\u0443\u0434\u0435\u043c", "yes but no thanks",
                         "\u043d\u0435\u0442 \u0437\u0430\u043f\u0438\u0441\u043a\u0430 \u043d\u0435 \u0442\u0430\u043c", "I don't want to go there, let's stay here", "yes " + "x" * 1001):
                with self.subTest(root=root, text=text):
                    self.assertEqual(mod.player_decision(text), "unknown")

    def test_offered_refusal_without_tag_preserves_summary_and_starts_pause(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            manager = self.manager(mod)
            manager.path += str(len(root))
            self.offer(manager)
            before = dict(manager.state)
            self.assertTrue(manager.commit(self.token(manager), None, "No pressure", player_text="No thanks"))
            self.assertEqual(manager.state["status"], "declined")
            self.assertEqual(manager.state["summary"], before["summary"])
            self.assertEqual(manager.state["title"], before["title"])
            self.assertEqual(manager.state["participants"], before["participants"])
            self.assertEqual(manager.state["turns"], before["turns"] + 1)
            self.assertEqual(manager.state["closed_turn"], manager.state["turns"])
            self.assertFalse(self.token(manager)["eligible"])

    def test_offered_refusal_overrides_erroneous_active_tag(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            manager = self.manager(mod)
            manager.path += str(len(root))
            self.offer(manager)
            manager.commit(self.token(manager), dict(status="active", summary="Invented acceptance", title="Wrong"),
                           "Reply", player_text="\u043d\u0435\u0442, \u043d\u0435 \u0445\u043e\u0447\u0443")
            self.assertEqual(manager.state["status"], "declined")
            self.assertEqual(manager.state["summary"], "Find a notebook")
            self.assertEqual(manager.state["title"], "Camp task")

    def test_offered_unknown_cannot_activate_but_explicit_acceptance_can(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            manager = self.manager(mod)
            manager.path += str(len(root))
            self.offer(manager)
            for text in (None, "Tell me more", "\u043d\u0435 \u0445\u043e\u0447\u0443 \u0438\u0434\u0442\u0438 \u0442\u0443\u0434\u0430 \u0434\u0430\u0432\u0430\u0439 \u0437\u0434\u0435\u0441\u044c"):
                turns = manager.state["turns"]
                manager.commit(self.token(manager), dict(status="active", summary="Invented acceptance"),
                               "Reply", player_text=text)
                self.assertEqual(manager.state["status"], "offered")
                self.assertEqual(manager.state["summary"], "Find a notebook")
                self.assertEqual(manager.state["turns"], turns + 1)
            manager.commit(self.token(manager), None, "Reply", player_text="Yes")
            self.assertEqual(manager.state["status"], "offered")  # Acceptance alone cannot invent a model update.
            manager.commit(self.token(manager), dict(status="offered", summary="Explained the task"),
                           "Reply", player_text="Tell me more")
            self.assertEqual(manager.state["summary"], "Explained the task")
            manager.commit(self.token(manager), dict(status="active", summary="Agreed"), "Reply", player_text="\u044f \u043f\u043e\u043c\u043e\u0433\u0443")
            self.assertEqual(manager.state["status"], "active")
            manager.commit(self.token(manager), None, "Reply", player_text="No thanks")
            self.assertEqual(manager.state["status"], "active")  # Offered-only detector must not derail active plots.

    def test_decisions_respect_empty_reply_stale_version_and_initiative(self):
        for root in (DEV, WORKSHOP):
            mod = module(root)
            manager = self.manager(mod)
            manager.path += str(len(root))
            self.offer(manager)
            before = dict(manager.state)
            token = self.token(manager)
            self.assertFalse(manager.commit(token, None, "", player_text="No thanks"))
            self.assertFalse(manager.commit(token, dict(status="active"), "Reply", False, "Yes"))
            self.assertFalse(manager.commit(token, None, "Reply", False, "No thanks"))
            self.assertEqual(manager.state, before)
            manager.commit(token, dict(status="offered", summary="Latest summary"), "Reply")
            turns = manager.state["turns"]
            manager.commit(token, None, "Reply", player_text="No thanks")
            self.assertEqual(manager.state["status"], "offered")
            self.assertEqual(manager.state["summary"], "Latest summary")
            self.assertEqual(manager.state["turns"], turns + 1)

    def test_both_chat_integrations_enforce_offered_player_decisions(self):
        for root in (DEV, WORKSHOP):
            for text, model_reply, expected in (
                    ("No thanks", "No pressure", "declined"),
                    ("\u043d\u0435 \u0445\u043e\u0447\u0443 \u0443\u0447\u0430\u0441\u0442\u0432\u043e\u0432\u0430\u0442\u044c", 'Hi [story:{"status":"active","summary":"Wrong"}]', "declined"),
                    ("Tell me more", 'Hi [story:{"status":"active","summary":"Wrong"}]', "offered"),
                    ("\u043d\u0435 \u0445\u043e\u0447\u0443 \u0438\u0434\u0442\u0438 \u0442\u0443\u0434\u0430 \u0434\u0430\u0432\u0430\u0439 \u0437\u0434\u0435\u0441\u044c", 'Hi [story:{"status":"active"}]', "offered"),
                    ("\u0434\u0430", 'Hi [story:{"status":"active"}]', "active"),
                    ("\u043f\u043e\u0439\u0434\u0451\u043c \u0438\u0441\u043a\u0430\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u043a\u0443", 'Hi [story:{"status":"active"}]', "active")):
                with self.subTest(root=root, text=text):
                    mod = module(root)
                    with tempfile.TemporaryDirectory(dir=self.temp.name) as directory:
                        mod.manager = mod.StoryManager(os.path.join(directory, "story_events.json"))
                        self.offer(mod.manager)
                        env, llm, conversation, modules = self.endpoint_env(root, mod, True)
                        turns = mod.manager.state["turns"]
                        with patch.dict(sys.modules, modules):
                            before = dict(mod.manager.state)
                            llm.chat.side_effect = RuntimeError("offline failure")
                            self.assertFalse(env["chat"](dict(text=text))["ok"])
                            self.assertEqual(mod.manager.state, before)
                            llm.chat.side_effect = None
                            llm.chat.return_value = '[story:{"status":"active"}]'
                            self.assertTrue(env["chat"](dict(text=text))["ok"])
                            self.assertEqual(mod.manager.state, before)  # Empty fallback is not a successful exchange.
                            llm.chat.reset_mock()
                            conversation.add_exchange.reset_mock()
                            llm.chat.return_value = model_reply
                            out = env["chat"](dict(text=text))
                        self.assertTrue(out["ok"])
                        llm.chat.assert_called_once()
                        self.assertEqual(mod.manager.state["status"], expected)
                        self.assertEqual(mod.manager.state["turns"], turns + 1)
                        self.assertEqual(mod.manager.state["summary"], "Find a notebook")
                        conversation.add_exchange.assert_called_once_with("un", text, out["reply"])


if __name__ == "__main__":
    unittest.main()
