"""Offline custom endpoint and post-clear regressions; no live config imports."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import copy
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

import test_story_events as story_fixture
from test_cameo_clothing import load, ROOTS

DEV, WORKSHOP, TEMP = story_fixture.DEV, story_fixture.WORKSHOP, story_fixture.TEMP
BASE = "https://codex-relay.codes/v1"
ENDPOINT = BASE + "/chat/completions"


def read_module(root, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CustomLlmTests(unittest.TestCase):
    def client(self, root):
        config = types.SimpleNamespace(cfg={"llm": dict(provider="custom", api_url=BASE,
                                                       model="offline-model", max_tokens=400,
                                                       temperature=0.9)}, keys={})
        with patch.dict(sys.modules, config_loader=config):
            return read_module(root, "llm_client"), config

    def response(self):
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "Hello"}}]}).encode())

    def test_normalization_idempotent_query_and_invalid_urls(self):
        for root in existing_paths((DEV, WORKSHOP)):
            client, _ = self.client(root)
            for url in (BASE, BASE + "/", ENDPOINT, ENDPOINT + "/"):
                self.assertEqual(client.normalize_chat_url(url), ENDPOINT)
                self.assertEqual(client.normalize_chat_url(client.normalize_chat_url(url)), ENDPOINT)
                self.assertEqual(client.normalize_chat_url(url + "?route=offline#fragment"),
                                 ENDPOINT + "?route=offline")
            for url in ("", "relative/v1", "ftp://example.org/v1", "https://user:pass@example.org/v1"):
                with self.assertRaises(client.LlmError):
                    client.normalize_chat_url(url)

    def test_settings_preview_server_test_and_chat_same_endpoint(self):
        for root in existing_paths((DEV, WORKSHOP)):
            client, config = self.client(root)
            env = dict(re=re)
            load(os.path.join(root, "main.py"), env, rpy=False)
            with open(os.path.join(root, "settings_window.py"), encoding="utf-8-sig") as stream:
                tree = ast.parse(stream.read())
            preview = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_llm")
            for url in (BASE, ENDPOINT + "/?route=offline"):
                config.cfg["llm"]["api_url"] = url
                fields = lambda value: types.SimpleNamespace(get=lambda: value)
                ui = dict(save_all=lambda **k: True, url_var=fields(url), model_var=fields("offline-model"),
                          provider_keyname=lambda: "", key_vars={}, llm_provider_var=fields("Custom"),
                          show_result=Mock(), bg=lambda kind, job: job(), json=json,
                          urllib=__import__("urllib"), time=__import__("time"))
                exec(compile(ast.Module(body=[preview], type_ignores=[]), "preview", "exec"), ui)
                requests = []
                def opened(request, **kwargs):
                    requests.append(request)
                    return self.response()
                with patch.dict(sys.modules, llm_client=client), patch.object(urllib.request, "urlopen", side_effect=opened):
                    ui["test_llm"]()
                    self.assertTrue(env["test_llm"]()["ok"])
                    self.assertEqual(client.chat([{"role": "user", "content": "offline"}]), "Hello")
                self.assertEqual(len(requests), 3)
                self.assertEqual({r.full_url for r in requests}, {client.normalize_chat_url(url)})
                for request in requests:
                    self.assertEqual(json.loads(request.data)["model"], "offline-model")

    def test_missing_model_never_calls_network(self):
        for root in existing_paths((DEV, WORKSHOP)):
            client, config = self.client(root)
            for model in ("", "model-name", None):
                config.cfg["llm"]["model"] = model
                with patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")) as opened:
                    with self.assertRaises(client.LlmError):
                        client.chat([{"role": "user", "content": "offline"}])
                    opened.assert_not_called()

    def test_http_status_preserved(self):
        for root in existing_paths((DEV, WORKSHOP)):
            client, _ = self.client(root)
            error = urllib.error.HTTPError(ENDPOINT, 404, "Not Found", {}, io.BytesIO(b'{}'))
            with patch.object(urllib.request, "urlopen", side_effect=error):
                with self.assertRaisesRegex(client.LlmError, "HTTP 404"):
                    client.chat([{"role": "user", "content": "offline"}])

    def test_clear_then_actual_chat_preserves_config_and_world(self):
        for root in existing_paths((DEV, WORKSHOP)):
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                fixture = story_fixture.StoryTests()
                story = story_fixture.module(root)
                env, _, _, modules = fixture.endpoint_env(root, story, False)
                client, config = self.client(root)
                env["cfg"].update(config.cfg)
                client.cfg = env["cfg"]
                config.cfg = env["cfg"]
                config.user_data_dir = lambda: directory
                config.save_config = Mock(side_effect=AssertionError("config write"))
                with patch.dict(sys.modules, config_loader=config):
                    conversation = read_module(root, "conversation")
                conversation._dir = lambda: directory
                modules.update(llm_client=client, conversation=conversation, config_loader=config,
                               scene_memory=types.SimpleNamespace(clear=Mock(), prompt=lambda *a: "", ingest=Mock()))
                modules["characters_store"].get_character = lambda cid: dict(id=cid, name=cid, persona="Persona", speech="Speech")
                modules["characters_store"].get_player = lambda: dict(name="Offline player")
                conversation.conversations["un"] = dict(messages=[dict(role="user", content="old")], summary="old")
                before = copy.deepcopy(env["cfg"])
                story.manager = story.StoryManager(os.path.join(directory, "world.json"))
                with patch.dict(sys.modules, modules), patch.object(urllib.request, "urlopen", side_effect=lambda *a, **k: self.response()) as opened:
                    self.assertTrue(env["history_clear"]({})["ok"])
                    self.assertEqual(conversation.get_history("un"), ([], ""))
                    result = env["chat"](dict(character="un", text="Hello"))
                    self.assertTrue(result["ok"], result)
                    body = json.loads(opened.call_args.args[0].data)
                    self.assertEqual(body["messages"][0]["role"], "system")
                    self.assertTrue(body["messages"][0]["content"])
                    self.assertEqual(body["messages"][-1], dict(role="user", content="Hello"))
                self.assertEqual(env["cfg"], before)
                config.save_config.assert_not_called()
                self.assertFalse(os.path.exists(story.manager.path))

    def test_rejected_character_argument_cannot_poison_context(self):
        for root in ROOTS:
            env = dict(basestring=str, es_ai_novel_context=[])
            load(os.path.join(root, "es_ai_api.rpy"), env)
            generator = (x for x in [True])
            env["es_ai_push_context"]("Everyone", generator)
            self.assertEqual(env["es_ai_novel_context"], [])
            env["es_ai_push_context"]("NPC", "Valid text")
            env["es_ai_novel_context"].append(dict(who="Everyone", what=generator))
            self.assertEqual(json.loads(json.dumps(env["es_ai_context_snapshot"]())),
                             [dict(who="NPC", what="Valid text")])


if __name__ == "__main__":
    unittest.main()
