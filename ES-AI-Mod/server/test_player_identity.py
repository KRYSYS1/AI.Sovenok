"""Offline identity regressions for dev and workshop, with all writes stubbed."""
import ast
import copy
import json
import os
from pathlib import Path
import re
import sys
import threading
import types
import unittest
from unittest.mock import Mock, mock_open, patch

from test_cameo_clothing import load


DEV = Path(__file__).resolve().parent
WORKSHOP = Path(r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310\server")


class PlayerIdentityTests(unittest.TestCase):
    def store(self, root):
        store = types.ModuleType("characters_store")
        store.__file__ = str(root / "characters_store.py")
        exec(compile(Path(store.__file__).read_text(encoding="utf-8-sig"), store.__file__, "exec"), store.__dict__)
        store._data = {"player": {"name": "KRYSYS", "persona": "custom persona"},
                       "characters": [{"id": "us", "name": "NPC", "age": 14,
                                       "persona": "persona", "speech": "speech"}]}
        store._by_id = {"us": store._data["characters"][0]}
        return store

    def test_store_identity_safety_and_paths(self):
        for root in (DEV, WORKSHOP):
            store = self.store(root)
            block = store.player_block()
            self.assertIn("игрок по имени KRYSYS", block)
            self.assertIn("приоритет", block)
            self.assertIn("не отменяет правила безопасности", block)
            self.assertIn("custom persona", block)
            rules = store.reply_rules(store.get_character("us"))
            self.assertNotRegex(rules, "Сем[её]|Semyon")
            self.assertIn("несовершеннолетний", rules)
            self.assertIn("semen_room", rules)
            store._data = None
            opener = mock_open(read_data=json.dumps({"player": {"name": "KRYSYS"}, "characters": []}))
            loader = types.SimpleNamespace(user_data_dir=lambda: "stub-user-data")
            with patch.dict(sys.modules, {"config_loader": loader}), patch("builtins.open", opener):
                store.reload()
            expected = root if root == DEV else Path("stub-user-data")
            self.assertEqual(opener.call_args.args[0], os.path.join(str(expected), "es_characters.json"))
            self.assertEqual(store.get_player()["name"], "KRYSYS")

    def test_cameo_all_modes_and_initiative(self):
        for root in (DEV, WORKSHOP):
            store = self.store(root)
            llm = types.ModuleType("llm_client")
            llm.chat = Mock(return_value="(smile) Hello")
            llm.sanitize_in_character = lambda text: text
            llm.strip_prompt_leak = lambda text, prompt: text
            conv = types.SimpleNamespace(get_history=lambda cid: ([], ""))
            env = {"re": re, "cfg": {}, "scene_prompt": lambda *args: ""}
            load(str(root / "main.py"), env, {"cameo", "initiative", "parse_action_tags",
                 "normalize_dress", "parse_cameo_tags", "normalize_location",
                 "clock_prompt", "game_clock_valid"}, False)
            with patch.dict(sys.modules, {"characters_store": store, "llm_client": llm,
                                          "conversation": conv}):
                for mode in ("leave", "stay", "here", "enter"):
                    result = env["cameo"]({"character": "us", "mode": mode})
                    self.assertTrue(result["ok"])
                    prompt = llm.chat.call_args.args[0][0]["content"]
                    self.assertIn("игрок по имени KRYSYS", prompt)
                    self.assertNotRegex(prompt, "Сем[её]|Semyon")
                    self.assertIn("несовершеннолетний", prompt)
                self.assertTrue(env["initiative"]({"character": "us"})["ok"])
                self.assertIn("KRYSYS", llm.chat.call_args.args[0][0]["content"])
                self.assertNotRegex(str(llm.chat.call_args.args), "Сем[её]|Semyon")
            tree = ast.parse((root / "main.py").read_text(encoding="utf-8-sig"))
            chat = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "chat")
            self.assertNotRegex(ast.unparse(chat), "Сем[её]|Semyon")

    def test_summary_keeps_history_and_current_identity(self):
        for root in (DEV, WORKSHOP):
            store = self.store(root)
            env = {"threading": threading, "lock": threading.Lock(), "_persist": Mock()}
            load(str(root / "conversation.py"), env,
                 {"_format_for_summary", "maybe_compress", "build_system_prompt"}, False)
            messages = [{"role": "user", "content": "old message"},
                        {"role": "assistant", "content": "old reply"}]
            env["conversations"] = {"us": {"messages": copy.deepcopy(messages), "summary": "Семён у моря"}}
            summarize = Mock(return_value="KRYSYS у моря")
            with patch.dict(sys.modules, {"characters_store": store}):
                self.assertTrue(env["maybe_compress"]("us", {"history": {"keep_recent": 0}}, summarize, force=True))
                text = summarize.call_args.args[0]
                self.assertIn("KRYSYS: old message", text)
                self.assertIn("приоритет", text)
                self.assertIn("Семён у моря", text)
                prompt = env["build_system_prompt"]("us", summary="Семён у моря")
                self.assertIn("игрок по имени KRYSYS", prompt)
                self.assertIn("старой истории и памяти", prompt)
            self.assertEqual(env["conversations"]["us"]["messages"], messages)

    def test_client_public_player_label(self):
        for path in (DEV.parent / "mod/es_ai_cameo.rpy", WORKSHOP.parent / "es_ai_cameo.rpy"):
            env = {"ES_AI_RECENT_LINES": [], "unicode": str}
            load(str(path), env, {"es_ai_recent_push"})
            env["es_ai_recent_push"]("", "Hello")
            self.assertEqual(env["ES_AI_RECENT_LINES"][0], {"who": "Игрок", "what": "Hello"})
            self.assertNotRegex(path.read_text(encoding="utf-8-sig"), "Сем[её]|Semyon")

    def test_settings_load_and_save_authoritative_file(self):
        for root in (DEV, WORKSHOP):
            path = root / "settings_window.py"
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            owner = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and
                         any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and
                             t.id == "chars_path" for t in s.targets) for s in n.body))
            start = next(i for i, n in enumerate(owner.body) if isinstance(n, ast.Assign) and
                         any(isinstance(t, ast.Name) and t.id == "chars_path" for t in n.targets))
            data = {"characters": [{"id": "us", "name": "NPC", "persona": "unchanged"}],
                    "player": {"id": "player", "name": "KRYSYS", "persona": "custom"}, "other": 42}
            variable = Mock()
            variable.get.return_value = "NEW-NAME"
            env = {"os": os, "json": json, "BASE_DIR": str(root),
                   "config_loader": types.SimpleNamespace(user_data_dir=lambda: "stub-user-data"),
                   "player_name_var": variable, "persona_text": Mock(), "_post": Mock(),
                    "show_result": Mock(), "pr_chips": [Mock()], "persona_who": Mock()}
            opener = mock_open(read_data=json.dumps(data))
            with patch("builtins.open", opener):
                exec(compile(ast.Module(body=owner.body[start:start + 3], type_ignores=[]), str(path), "exec"), env)
                variable.set.assert_called_once_with("KRYSYS")
                env.update(prompt_targets=[("player", "KRYSYS", True)], prompt_idx=[0])
                env["persona_text"].get.return_value = "custom"
                save = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "prompt_save")
                exec(compile(ast.Module(body=[save], type_ignores=[]), str(path), "exec"), env)
                env["prompt_save"]()
            expected = os.path.join(str(root) if root == DEV else "stub-user-data", "es_characters.json")
            self.assertEqual(opener.call_args_list[0].args[0], expected)
            self.assertEqual(opener.call_args_list[1].args[0], expected)
            saved = json.loads("".join(call.args[0] for call in opener().write.call_args_list))
            data["player"]["name"] = "NEW-NAME"
            self.assertEqual(saved, data)
            env["_post"].assert_called_once_with("/reload")
            self.assertEqual(env["prompt_targets"], [("player", "NEW-NAME", True)])
            env["pr_chips"][0].retranslate.assert_called_once_with()
            env["persona_who"].retranslate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
