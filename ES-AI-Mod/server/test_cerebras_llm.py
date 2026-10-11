"""Both-root Cerebras regressions, with mocked transport and no live secrets."""
import ast
import copy
import io
import json
import types
import unittest
import urllib.parse
import urllib.request
from unittest.mock import Mock, patch

import test_custom_llm as custom_tests
from test_i18n_new_settings import SERVERS, extract, tree


def constants(server, filename):
    parsed = tree(server / filename)
    env = {}
    extract([n for n in parsed.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in {
                 "LLM_PROVIDERS", "LLM_PRESETS", "MODELS_URLS", "MODEL_FALLBACKS",
                 "PROVIDER_KEYNAME", "KEY_URLS", "ALL_KEYS", "_KEY_NAMES", "_LLM_PRESETS",
             } for t in n.targets)], env)
    return parsed, env


def normalizer(server):
    env = {"urllib": __import__("urllib")}
    extract([n for n in tree(server / "config_loader.py").body
             if isinstance(n, ast.FunctionDef) and n.name == "normalize_llm_urls"], env)
    return env["normalize_llm_urls"]


class CerebrasLlmTests(unittest.TestCase):
    def test_ui_order_defaults_keys_and_translation(self):
        for server in SERVERS:
            parsed, env = constants(server, "settings_window.py")
            providers = env["LLM_PROVIDERS"]
            self.assertEqual(providers[providers.index("Cohere") + 1], "Cerebras")
            self.assertEqual(env["LLM_PRESETS"]["Cerebras"],
                             ("https://api.cerebras.ai/v1", "qwen-3.8-27b", "cerebras_api_key"))
            self.assertEqual(env["KEY_URLS"]["cerebras_api_key"], "https://cloud.cerebras.ai")
            self.assertIn("cerebras_api_key", env["ALL_KEYS"])
            self.assertEqual(env["PROVIDER_KEYNAME"]["cerebras"], "cerebras_api_key")
            for url, _, _ in env["LLM_PRESETS"].values():
                self.assertNotIn("/chat/completions", url)
            _, backend = constants(server, "main.py")
            self.assertIn("cerebras_api_key", backend["_KEY_NAMES"])
            self.assertEqual(backend["_LLM_PRESETS"]["cerebras"],
                             env["LLM_PRESETS"]["Cerebras"][:2])
            for url, _ in backend["_LLM_PRESETS"].values():
                self.assertNotIn("/chat/completions", url)
            i18n = {}
            extract([n for n in tree(server / "ui_i18n.py").body if isinstance(n, ast.FunctionDef)
                     or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EN"
                                                         for t in n.targets)], i18n)
            self.assertEqual(i18n["tr"]("Cerebras", "en"), "Cerebras")

    def test_chat_dispatch_and_missing_key_never_uses_other_provider(self):
        for server in SERVERS:
            client, config = custom_tests.CustomLlmTests().client(str(server))
            config.cfg["llm"].update(provider="cerebras", api_url="https://api.cerebras.ai/v1",
                                      model="qwen-3.8-27b")
            config.keys.update(llm_api_key="wrong-provider", custom_llm_api_key="wrong-custom")
            with patch.object(urllib.request, "urlopen") as opened:
                with self.assertRaisesRegex(client.LlmError, "No API key for Cerebras"):
                    client.chat([])
                opened.assert_not_called()
            config.keys["cerebras_api_key"] = "offline-key"
            self.assertTrue(client.available_providers()["cerebras"])
            for url in ("https://api.cerebras.ai/v1", "https://api.cerebras.ai/v1/chat/completions/"):
                config.cfg["llm"]["api_url"] = url
                with patch.object(urllib.request, "urlopen", return_value=custom_tests.CustomLlmTests().response()) as opened:
                    self.assertEqual(client.chat([]), "Hello")
                req = opened.call_args.args[0]
                self.assertEqual(req.full_url, "https://api.cerebras.ai/v1/chat/completions")
                self.assertEqual(req.get_header("Authorization"), "Bearer offline-key")

    def test_discovery_authenticated_get_and_static_fallback(self):
        for server in SERVERS:
            parsed, env = constants(server, "settings_window.py")
            field = lambda value: types.SimpleNamespace(get=lambda: value)
            env.update(llm_provider_var=field("Cerebras"), url_var=field("https://api.cerebras.ai/v1"),
                       provider_keyname=lambda: "cerebras_api_key",
                       key_vars={"cerebras_api_key": field("offline-key")},
                       urllib=__import__("urllib"), json=json, bg=lambda kind, job: job())
            extract([n for n in ast.walk(parsed) if isinstance(n, ast.FunctionDef)
                     and n.name in ("models_source", "_parse_models", "fetch_models", "models_arrived")], env)
            url, key = env["models_source"]()
            self.assertEqual(url, "https://api.cerebras.ai/v1/models")
            data = {"data": [{"id": "gpt-oss-120b"}, {"id": "qwen-3.8-27b"}]}
            with patch.object(urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(data).encode())) as opened:
                env["fetch_models"](url, key)
            request = opened.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer offline-key")
            env.update(models={"want": url, "loading": True}, refill_models=Mock(),
                       close_models=Mock(), show_result=Mock())
            env["models_arrived"]((url, "offline error"))
            self.assertEqual(env["models"]["ids"], env["MODEL_FALLBACKS"]["Cerebras"])
            env["refill_models"].assert_called_once_with(show_all=True)
            env["close_models"].assert_not_called()

    def test_url_migration_only_terminal_llm_fields(self):
        for server in SERVERS:
            normalize = normalizer(server)
            config = {"llm": {"api_url": "https://example.org/v1/chat/completions/?route=a#f",
                              "custom_api_url": "https://example.org/chat/completions/proxy",
                              "model": "offline-model", "provider": "custom"},
                      "tts": {"api_url": "https://example.org/v1/chat/completions"}}
            before = copy.deepcopy(config)
            normalize(config)
            self.assertEqual(config["llm"]["api_url"], "https://example.org/v1?route=a#f")
            self.assertEqual(config["llm"]["custom_api_url"], before["llm"]["custom_api_url"])
            self.assertEqual(config["tts"], before["tts"])
            again = copy.deepcopy(config)
            normalize(config)
            self.assertEqual(config, again)

    def test_loader_paths_exports_and_config_set(self):
        for server in SERVERS:
            parsed = tree(server / "config_loader.py")
            names = {n.name for n in parsed.body if isinstance(n, ast.FunctionDef)}
            self.assertTrue({"reload_all", "save_config", "save_keys", "normalize_llm_urls"} <= names)
            save_keys = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == "save_keys")
            source = ast.unparse(save_keys)
            self.assertIn("keys.json", source)
            self.assertIn("_DIR" if server == SERVERS[0] else "user_data_dir()", source)
            main, env = constants(server, "main.py")
            env.update(cfg={}, config_loader=types.SimpleNamespace(
                normalize_llm_urls=normalizer(server), save_config=Mock()))
            extract([n for n in main.body if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_CFG_SECTIONS" for t in n.targets)
                or isinstance(n, ast.FunctionDef) and n.name == "config_set"], env)
            with patch.dict("sys.modules", story_events=types.ModuleType("story_events")):
                self.assertTrue(env["config_set"]({"section": "llm", "key": "api_url",
                                                  "value": "https://example.org/v1/chat/completions"})["ok"])
            self.assertEqual(env["cfg"]["llm"]["api_url"], "https://example.org/v1")

    def test_dynamic_flow_wrap_preserves_provider_order(self):
        for server in SERVERS:
            parsed, env = constants(server, "settings_window.py")
            extract([n for n in ast.walk(parsed) if isinstance(n, ast.FunctionDef) and n.name == "flow"], env)
            for width in (350, 764, 904, 1224):
                chips = []
                for name in env["LLM_PROVIDERS"]:
                    chip = types.SimpleNamespace(nat_w=len(name) * 9 + 30, h=34, place=Mock())
                    chips.append(chip)
                bottom = env["flow"](chips, 28, 170, width)
                last = (170, 0)
                for chip in chips:
                    x, y = chip.place.call_args.args
                    self.assertLessEqual(x + chip.nat_w, 28 + width)
                    self.assertGreaterEqual((y, x), last)
                    last = (y, x)
                self.assertEqual(bottom, last[0] + 34)

    def test_keys_set_accepts_cerebras_and_clears_without_disk_io(self):
        for server in SERVERS:
            parsed, env = constants(server, "main.py")
            fake = types.ModuleType("config_loader")
            fake.keys = {}
            fake.save_keys = Mock()
            extract([n for n in parsed.body if isinstance(n, ast.FunctionDef)
                     and n.name in ("keys_set", "_mask_key")], env)
            with patch.dict("sys.modules", config_loader=fake):
                self.assertTrue(env["keys_set"]({"name": "cerebras_api_key", "value": "offline-key"})["ok"])
                self.assertEqual(fake.keys["cerebras_api_key"], "offline-key")
                self.assertTrue(env["keys_set"]({"name": "cerebras_api_key", "value": None})["ok"])
                self.assertEqual(fake.keys["cerebras_api_key"], "")
            self.assertEqual(fake.save_keys.call_count, 2)

    def test_preview_uses_cerebras_key_and_runtime_endpoint(self):
        import sys
        for server in SERVERS:
            client, _ = custom_tests.CustomLlmTests().client(str(server))
            parsed = tree(server / "settings_window.py")
            field = lambda value: types.SimpleNamespace(get=lambda: value)
            env = dict(save_all=lambda **kwargs: True, url_var=field("https://api.cerebras.ai/v1"),
                       model_var=field("qwen-3.8-27b"), provider_keyname=lambda: "cerebras_api_key",
                       key_vars={"cerebras_api_key": field("offline-key")},
                       llm_provider_var=field("Cerebras"), show_result=Mock(),
                       bg=lambda kind, job: job(), json=json, urllib=__import__("urllib"),
                       time=__import__("time"))
            extract([n for n in ast.walk(parsed) if isinstance(n, ast.FunctionDef) and n.name == "test_llm"], env)
            with patch.dict(sys.modules, llm_client=client), patch.object(
                    urllib.request, "urlopen", return_value=custom_tests.CustomLlmTests().response()) as opened:
                env["test_llm"]()
            request = opened.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.cerebras.ai/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer offline-key")


if __name__ == "__main__":
    unittest.main()
