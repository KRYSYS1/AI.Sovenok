"""Offline backend checks for both builds, without user configs or TTS engines."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import copy
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SERVERS = (Path(__file__).resolve().parent,) + existing_paths((Path(WORKSHOP_ROOT) / "server",))
DISPATCH = {"edge": "_edge", "elevenlabs": "_elevenlabs", "fish": "_fish",
            "openai": "_openai", "custom": "_openai_compatible", "sapi": "_sapi"}


class CharacterVoicesTests(unittest.TestCase):
    def environment(self, server):
        cfg = {"tts": {"provider": "edge"}}
        roster = [{"id": "un", "gender": "female"}, {"id": "el"}, {"id": "sh"}]
        loader = types.ModuleType("config_loader")
        loader.cfg, loader.keys, loader.save_config = cfg, {}, Mock()
        store = types.ModuleType("characters_store")
        store.characters = lambda: roster
        store.get_character = lambda cid: next((c for c in roster if c["id"] == cid), roster[0])
        client = types.ModuleType("tts_client")
        client.__file__ = str(server / "tts_client.py")
        story = types.SimpleNamespace(settings=lambda value: value or {})
        stt = types.SimpleNamespace(available_providers=lambda: {})
        modules = {"config_loader": loader, "characters_store": store,
                   "tts_client": client, "story_events": story, "stt_client": stt}
        self.enterContext(patch.dict(sys.modules, modules))
        exec(compile((server / "tts_client.py").read_text(encoding="utf-8-sig"),
                     client.__file__, "exec"), client.__dict__)
        client.available_providers = Mock(return_value={p: True for p in DISPATCH})
        client._cache_dir = Mock(return_value="offline-cache")
        for name in DISPATCH.values():
            setattr(client, name, Mock())
        client._edge.note = client._edge.used = ""
        tree = ast.parse((server / "main.py").read_text(encoding="utf-8-sig"))
        names = {"_CFG_SECTIONS", "_KEY_NAMES", "_LLM_PRESETS"}
        functions = {"config_set", "get_config_state", "_mask_key", "tts"}
        nodes = [n for n in tree.body if
                 isinstance(n, ast.FunctionDef) and n.name in functions or
                 isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        env = dict(cfg=cfg, config_loader=loader, os=os,
                   game_clock_settings=lambda value: value or {})
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "offline-main", "exec"), env)
        return cfg, roster, client, loader, env

    def synthesize(self, client, character=None, narrator=False):
        with patch.object(client.os, "listdir", return_value=[]):
            return client.synthesize(" test ", character, narrator)

    def test_each_dispatcher_receives_override_and_correct_extension(self):
        for server in SERVERS:
            for provider, function in DISPATCH.items():
                with self.subTest(server=server, provider=provider):
                    cfg, roster, client, _, _ = self.environment(server)
                    cfg["tts"]["character_overrides"] = {
                        "un": {"provider": provider, "voice_id": "  \u0413\u043e\u043b\u043e\u0441 / ID  "}}
                    path, info = self.synthesize(client, roster[0])
                    self.assertEqual(info, provider)
                    self.assertTrue(path.endswith(".wav" if provider == "sapi" else ".mp3"))
                    args = getattr(client, function).call_args.args
                    self.assertEqual(args[0], "test")
                    self.assertEqual(args[2] if provider == "sapi" else args[1], "\u0413\u043e\u043b\u043e\u0441 / ID")
                    self.assertIn(path, args)
                    for other, name in DISPATCH.items():
                        if other != provider:
                            getattr(client, name).assert_not_called()

    def test_master_off_and_explicit_unavailable_do_not_fallback(self):
        for server in SERVERS:
            for global_provider, override in (("off", "openai"), ("edge", "off"), ("edge", "openai")):
                with self.subTest(server=server, global_provider=global_provider, override=override):
                    cfg, roster, client, loader, _ = self.environment(server)
                    cfg["tts"].update(provider=global_provider,
                                      character_overrides={"un": {"provider": override, "voice_id": "v"}})
                    client.available_providers.return_value["openai"] = False
                    self.assertEqual(self.synthesize(client, roster[0]), (None, "tts_disabled"))
                    if global_provider == "off":
                        client.available_providers.assert_not_called()
                    client._cache_dir.assert_not_called()
                    for name in DISPATCH.values():
                        getattr(client, name).assert_not_called()
                    self.assertEqual(loader.keys, {})

    def test_auto_and_missing_provider_inherit_resolved_global(self):
        for server in SERVERS:
            for global_provider, expected in (("edge", "edge"), ("auto", "elevenlabs"), ("openai", "openai")):
                for entry in ({"voice_id": "voice"}, {"provider": "auto", "voice_id": "voice"}):
                    with self.subTest(server=server, global_provider=global_provider, entry=entry):
                        cfg, roster, client, _, _ = self.environment(server)
                        cfg["tts"].update(provider=global_provider, character_overrides={"un": entry})
                        self.assertEqual(self.synthesize(client, roster[0])[1], expected)
                        self.assertEqual(getattr(client, DISPATCH[expected]).call_args.args[1], "voice")
                        other = "fish" if expected != "fish" else "edge"
                        self.assertEqual(client._voice_for(roster[0], other), client._pick_gender(roster[0], other))
            cfg, roster, client, _, _ = self.environment(server)
            cfg["tts"].update(provider="openai", character_overrides={"un": {"provider": "auto"}})
            client.available_providers.return_value["openai"] = False
            self.assertEqual(self.synthesize(client, roster[0]), (None, "tts_disabled"))

    def test_blank_voice_gender_defaults_and_bundled_voices_ignored(self):
        for server in SERVERS:
            for provider in DISPATCH:
                cfg, roster, client, _, _ = self.environment(server)
                cfg["tts"].update({provider + "_voice_female": "female",
                                   provider + "_voice_male": "male"})
                for character, expected in ((roster[0], "female"), (roster[1], "male"),
                                            ({"id": "sh", "gender": "female"}, "female")):
                    with self.subTest(server=server, provider=provider, character=character):
                        character["voices"] = {provider: "bundled-must-not-activate"}
                        cfg["tts"]["character_overrides"] = {
                            character["id"]: {"provider": provider, "voice_id": " \t "}}
                        self.synthesize(client, character)
                        args = getattr(client, DISPATCH[provider]).call_args.args
                        self.assertEqual(args[2] if provider == "sapi" else args[1], expected)

    def test_narrator_and_unknown_entries_unchanged(self):
        for server in SERVERS:
            cfg, roster, client, _, _ = self.environment(server)
            cfg["tts"]["character_overrides"] = {
                "un": {"provider": "sapi", "voice_id": "character-only"},
                "unknown": {"provider": "off"}, "pi": {"provider": "off"}}
            self.assertEqual(self.synthesize(client, roster[0], narrator=True)[1], "edge")
            self.assertEqual(client._edge.call_args.args[1], client._EDGE_FEMALE)
            for cid in ("unknown", "pi"):
                self.assertEqual(self.synthesize(client, {"id": cid})[1], "edge")
            cfg["tts"]["character_overrides"]["un"] = {"provider": "bogus", "voice_id": "bad"}
            self.assertEqual(self.synthesize(client, roster[0])[1], "edge")

    def test_preview_override_is_local_validated_and_keeps_normal_calls(self):
        for server in SERVERS:
            for provider, function in DISPATCH.items():
                cfg, roster, client, loader, _ = self.environment(server)
                cfg["tts"]["character_overrides"] = {"un": {"provider": "edge", "voice_id": "saved"}}
                before = copy.deepcopy(cfg)
                character = copy.deepcopy(roster[0])
                with patch.object(client.os, "listdir", return_value=[]):
                    path, info = client.synthesize("preview", roster[0], character_override={
                        "provider": provider, "voice_id": "  unsaved  "})
                self.assertEqual(info, provider)
                args = getattr(client, function).call_args.args
                self.assertEqual(args[2] if provider == "sapi" else args[1], "unsaved")
                self.assertEqual(cfg, before)
                self.assertEqual(roster[0], character)
                loader.save_config.assert_not_called()
                self.assertEqual(self.synthesize(client, roster[0])[1], "edge")
                self.assertEqual(client._edge.call_args.args[1], "saved")
            cfg, roster, client, _, _ = self.environment(server)
            for override in ({"provider": "bogus", "voice_id": "v"}, {"voice_id": 1},
                             {"voice_id": "x" * 1025}, [], {"voice_id": " "}):
                self.assertIsNone(client.synthesize("test", roster[0], character_override=override)[0])
            cfg["tts"]["provider"] = "off"
            self.assertEqual(client.synthesize("test", roster[0], character_override={
                "provider": "openai", "voice_id": "v"}), (None, "tts_disabled"))
            client._cache_dir.assert_not_called()

    def test_config_validation_is_atomic_and_export_is_normalized(self):
        invalid = [None, False, True, [], "bad", {"unknown": {}}, {"pi": {}},
                   {"un": False}, {"un": []}, {"un": {"provider": False}},
                   {"un": {"provider": 1}}, {"un": {"provider": "bogus"}},
                   {"un": {"voice_id": False}}, {"un": {"voice_id": 1}},
                   {"un": {"voice_id": None}}, {"un": {"voice_id": "x" * 1025}},
                   {"un": {"extra": "bad"}}, {"el": {}, "un": {"voice_id": []}}]
        for server in SERVERS:
            cfg, roster, client, loader, env = self.environment(server)
            cfg["tts"]["character_overrides"] = {"un": {"provider": "edge", "voice_id": "original"}}
            before = copy.deepcopy(cfg)
            for value in invalid:
                with self.subTest(server=server, value=value):
                    result = env["config_set"]({"section": "tts", "key": "character_overrides", "value": value})
                    self.assertFalse(result["ok"])
                    self.assertEqual(cfg, before)
                    loader.save_config.assert_not_called()
            value = {"un": {"voice_id": "  \u0413\u043e\u043b\u043e\u0441  "}, "el": {"provider": "off"},
                     "sh": {"provider": "custom", "voice_id": "x" * 1024}}
            self.assertEqual(env["config_set"]({"section": "tts", "key": "character_overrides", "value": value}), {"ok": True})
            expected = {"un": {"provider": "auto", "voice_id": "\u0413\u043e\u043b\u043e\u0441"},
                        "el": {"provider": "off", "voice_id": ""}, "sh": value["sh"]}
            self.assertEqual(cfg["tts"]["character_overrides"], expected)
            loader.save_config.assert_called_once_with()
            cfg["tts"]["character_overrides"].update({"unknown": {}, "pi": {}, "bad": False})
            stored = copy.deepcopy(cfg)
            self.assertEqual(env["get_config_state"]()["config"]["tts"], {
                "provider": "edge", "character_overrides": expected, "elevenlabs_default_voice": "",
                "openai_tts_model": "", "custom_tts_url": ""})
            self.assertEqual(cfg, stored)
            roster.append({"id": "pi"})
            self.assertEqual(client.normalize_character_overrides({"pi": {}}, strict=True),
                             {"pi": {"provider": "auto", "voice_id": ""}})
            self.assertEqual(env["config_set"]({"section": "tts", "key": "character_overrides", "value": {}}), {"ok": True})
            self.assertEqual(cfg["tts"]["character_overrides"], {})

    def test_tts_api_contract_and_edge_status_preserved(self):
        for server in SERVERS:
            _, roster, client, _, env = self.environment(server)
            client.synthesize = Mock(return_value=("offline-cache/test.mp3", "edge"))
            self.assertEqual(env["tts"]({"text": "hello", "character": "el"}),
                             {"ok": True, "path": os.path.abspath("offline-cache/test.mp3"), "provider": "edge"})
            client.synthesize.assert_called_with("hello", roster[1], False)
            client.synthesize.return_value = (None, "tts_disabled")
            self.assertEqual(env["tts"]({"text": "hello", "narrator": True}),
                             {"ok": False, "error": "tts_disabled"})
            client.synthesize.assert_called_with("hello", None, True)
            _, roster, client, _, _ = self.environment(server)
            client._edge.used = "actual-voice"
            self.assertEqual(self.synthesize(client, roster[0])[1], "edge \u00b7 actual-voice")


if __name__ == "__main__":
    unittest.main()
