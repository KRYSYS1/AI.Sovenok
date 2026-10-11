"""Offline independent-row regressions for both settings windows."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import importlib.util
import json
import types
import unittest
from unittest.mock import Mock, mock_open, patch

from test_player_identity import DEV, WORKSHOP
import test_settings_save_state as save_tests
from test_story_settings import Widget


class Var:
    def __init__(self, value=""):
        self.value = value
        self.callbacks = {}

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        for callback in list(self.callbacks.values()):
            callback()

    def trace_add(self, mode, callback):
        token = str(len(self.callbacks))
        self.callbacks[token] = callback
        return token

    def trace_remove(self, mode, token):
        del self.callbacks[token]


class Control(Widget):
    def __init__(self, text="", command=None, **kwargs):
        super().__init__()
        self.command = command
        self.src = text
        self.tag = str(id(self))
        self.img_id = id(self)
        self.widget = Mock()
        self.icon = Mock()
        self.nat_w = kwargs.get("min_w", 100)
        self.options = kwargs

    def set_text(self, text):
        self.src = text

    def hide(self):
        pass


class IndividualVoiceSettingsTests(unittest.TestCase):
    def environment(self, server):
        env, data, owner = save_tests.SettingsSaveStateTests().environment(server)
        env.update(voice_targets=[("un", "Lena"), ("el", "Elektronik"), ("sl", "Slavya")],
                   individual_rows={}, individual_providers={"auto": "Общий провайдер", "off": "Выключено",
                   "edge": "edge-tts", "openai": "OpenAI"}, tk=types.SimpleNamespace(StringVar=Var),
                   MANAGED=[], I18N_WIDGETS=[], lookup_icons=set(), canvas=Mock(),
                   lookup=dict(token=0, top=None, lb=None, sb=None, loading=False), Field=Control)
        def chip(*args, **kwargs):
            control = Control(*args, **kwargs)
            env["MANAGED"].append(control)
            env["I18N_WIDGETS"].append(control)
            return control
        def field(var, loader):
            control = chip()
            env["lookup_icons"].update((control.widget, control.icon))
            return control
        env.update(Chip=chip, lookup_field=field, load_openai_voices=Mock())
        names = {"flush_character_voice", "load_character_voice", "select_voice_provider",
                 "lookup_character_voice", "lookup_arrived", "close_lookup", "choose_lookup",
                 "scroll_tts", "refresh_voice_rows", "add_voice_character", "remove_voice_character",
                  "rename_voice_character", "voice_lookup_current", "preview_character_voice"}
        nodes = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "individual-rows", "exec"), env)
        return env, data, owner

    def test_initial_load_independent_edits_and_revert(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, _, _ = self.environment(server)
            baseline = env["settings_snapshot"]()
            env["load_character_voice"]()
            self.assertEqual(env["settings_snapshot"](), baseline)
            env["add_voice_character"]("el")
            env["add_voice_character"]("un")
            rows = env["individual_rows"]
            rows["el"]["provider_var"].set("edge")
            rows["el"]["voice_var"].set("  actual-ID  ")
            rows["un"]["voice_var"].set("second-ID")
            self.assertEqual(env["character_overrides"]["el"], {"provider": "edge", "voice_id": "actual-ID"})
            self.assertEqual(env["character_overrides"]["un"]["voice_id"], "second-ID")
            self.assertIsNot(rows["el"]["voice"], rows["un"]["voice"])
            env["remove_voice_character"]("el")
            env["remove_voice_character"]("un")
            self.assertEqual(env["settings_snapshot"](), baseline)
            self.assertFalse(env["MANAGED"])
            self.assertFalse(env["I18N_WIDGETS"])
            self.assertFalse(env["lookup_icons"])

    def test_off_inherit_unknown_fields_and_save_copy(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, data, _ = self.environment(server)
            env["character_overrides"].update(un={"provider": "inherit", "voice_id": "", "future": True},
                                              unknown={"provider": "off", "future": True})
            baseline = env["settings_snapshot"]()
            env["load_character_voice"]()
            env["flush_character_voice"]()
            self.assertEqual(env["settings_snapshot"](), baseline)
            env["select_voice_provider"](env["individual_rows"]["un"], "off")
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                self.assertTrue(env["save_all"]())
            self.assertEqual(env["tts_cfg"]["character_overrides"]["un"],
                             {"provider": "off", "voice_id": "", "future": True})
            self.assertTrue(env["tts_cfg"]["character_overrides"]["unknown"]["future"])
            env["individual_rows"]["un"]["voice_var"].set("later")
            self.assertEqual(env["tts_cfg"]["character_overrides"]["un"]["voice_id"], "")

    def test_lookup_loaders_ids_and_stale_results(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, _, _ = self.environment(server)
            env["add_voice_character"]("un")
            row = env["individual_rows"]["un"]
            loaders = {name: Mock() for name in ("edge", "eleven", "fish", "openai", "sapi")}
            env.update({"load_" + name + "_voices": loader for name, loader in loaders.items()})
            env.update(open_lookup=Mock(side_effect=lambda *args: env["lookup"].update(top=Mock())),
                       tts_var=Var("Auto"), TTS_MAP={"Auto": "auto"}, refill_lookup=Mock(),
                       tts_client=types.SimpleNamespace(available_providers=Mock(return_value={"edge": True})))
            for provider, name in (("edge", "edge"), ("elevenlabs", "eleven"), ("fish", "fish"),
                                   ("openai", "openai"), ("sapi", "sapi"), ("custom", "openai"), ("auto", "edge")):
                row["provider_var"].set(provider)
                env["lookup_character_voice"](row)
                self.assertIs(env["open_lookup"].call_args.args[3], loaders[name])
            env["lookup"].update(token=2, lb=Mock(), loading=False, var=row["voice_var"], entry=Mock(),
                                 shown=[("Display name", "actual-ID")])
            env["lookup"]["lb"].curselection.return_value = (0,)
            env["lookup"]["lb"].get.return_value = "Display name"
            env["choose_lookup"]()
            self.assertEqual(env["character_overrides"]["un"]["voice_id"], "actual-ID")
            env["lookup_character_voice"](row)
            token = env["lookup"]["token"]
            row["generation"] += 1
            env["lookup_arrived"]((token, [("stale", "wrong-ID")]))
            env["refill_lookup"].assert_not_called()
            env["rename_voice_character"](row, "el")
            env["lookup_arrived"]((token, [("stale", "wrong-ID")]))
            env["refill_lookup"].assert_not_called()
            self.assertEqual(env["character_overrides"]["el"]["voice_id"], "actual-ID")

    def test_translations_snapshot_order_and_selector_exclusion(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, _, owner = self.environment(server)
            spec = importlib.util.spec_from_file_location("voice_i18n", server / "ui_i18n.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for ru, en in (("ИНДИВИДУАЛЬНЫЕ ГОЛОСА", "INDIVIDUAL VOICES"), ("ПЕРСОНАЖ", "CHARACTER"),
                           ("ПРОВАЙДЕР", "PROVIDER"), ("Общий провайдер", "Global provider"),
                           ("VOICE ID", "VOICE ID"), ("Добавить персонажа", "Add character"),
                           ("Прослушать голос", "Preview voice")):
                self.assertEqual(module.tr(ru, "ru"), ru)
                self.assertEqual(module.tr(ru, "en"), en)
            self.assertFalse(any(isinstance(n, ast.Name) and n.id in
                                 {"voice_character_var", "voice_provider_var", "voice_id_var"} for n in ast.walk(owner)))
            env["character_overrides"].update(el={"voice_id": "x", "provider": "edge"}, un={"provider": "off"})
            before = env["settings_snapshot"]()
            env["character_overrides"] = dict(reversed(list(env["character_overrides"].items())))
            self.assertEqual(env["settings_snapshot"](), before)

    def test_layout_all_providers_and_scroll_clamp(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, _, owner = self.environment(server)
            function = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "lay_tts")
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("place", "set"):
                    if isinstance(node.func.value, ast.Name):
                        env[node.func.value.id] = Widget()
            providers = ("auto", "off", "edge", "elevenlabs", "fish", "openai", "sapi", "custom")
            env.update(H=34, LBL=20, ROW=70, PASS=[1], tts_scroll=[0, 0, 1], tts_bar=Mock(),
                       tts_chips=[], TTS_NOTES={}, TTS_MAP={p: p for p in providers}, tts_var=Var("auto"),
                        result_txt={"tts": Widget(), "voice_preview": Widget()}, flow=lambda chips, x, y, width: y + 34)
            env["add_voice_character"]("un")
            env["add_voice_character"]("el")
            env["tts_note"].set = Mock()
            exec(compile(ast.Module(body=[function], type_ignores=[]), "voice-layout", "exec"), env)
            for width, height in ((820, 640), (960, 740), (1280, 900)):
                for provider in providers:
                    env["tts_var"].set(provider)
                    env["tts_scroll"][0] = 10000
                    # Pure geometry harness: real Tk smoke verifies clipping separately.
                    managed = env["MANAGED"]
                    env["MANAGED"] = []
                    env["lay_tts"](28, width - 28, 150, height - 78)
                    env["MANAGED"] = managed
                    self.assertEqual(env["tts_scroll"][0], env["tts_scroll"][1])
                    self.assertLess(env["tts_test"].geo[1] + 34, env["individual_sec"].geo[1])
                    for row in env["individual_rows"].values():
                        controls = row["controls"]
                        self.assertEqual(len({control.geo[1] for control in controls}), 1)
                        for left, right in zip(controls, controls[1:]):
                            self.assertLess(left.geo[0] + left.geo[2], right.geo[0])
                        self.assertEqual(row["remove"].geo[2], 34)
                        self.assertEqual(row["remove"].src, "×")
                        self.assertEqual(row["preview"].geo[2], 34)
                        self.assertEqual(row["preview"].src, "\U0001f50a")
                        self.assertEqual(row["preview"].options["h"], 34)
                    self.assertGreater(env["individual_add"].geo[1], env["individual_rows"]["el"]["voice"].geo[1] + 34)

    def test_preview_uses_unsaved_row_snapshot_without_saving(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, _, _ = self.environment(server)
            jobs = []
            client = types.SimpleNamespace(synthesize=Mock(return_value=("preview.wav", "sapi")),
                                           available_providers=Mock(return_value={"edge": True}))
            env.update(voice_preview_busy=[False], tts_var=Var("edge"),
                       TTS_MAP={"edge": "edge", "off": "off", "auto": "auto"},
                       prompt_data={"characters": [{"id": "el", "gender": "m"}]},
                       show_result=Mock(), tr=lambda text: text, play_mp3=Mock(),
                       tts_client=client, bg=lambda kind, job: jobs.append(job))
            env["save_all"] = Mock(side_effect=AssertionError("preview must not save"))
            env["add_voice_character"]("el")
            env["add_voice_character"]("un")
            row = env["individual_rows"]["el"]
            for global_provider, provider, voice in (("edge", "auto", " "), ("off", "sapi", "v"),
                                                     ("edge", "off", "v")):
                env["tts_var"].set(global_provider)
                row["provider_var"].set(provider)
                row["voice_var"].set(voice)
                env["preview_character_voice"](row)
                self.assertFalse(jobs)
                self.assertTrue(env["show_result"].call_args.args[1].startswith("✗"))
            env["tts_var"].set("edge")
            row["provider_var"].set("auto")
            row["voice_var"].set("  unsaved-ID  ")
            snapshot = env["settings_snapshot"]()
            env["preview_character_voice"](row)
            env["preview_character_voice"](env["individual_rows"]["un"])
            self.assertEqual(len(jobs), 1)
            row["voice_var"].set("later-ID")
            env["remove_voice_character"]("el")
            jobs.pop()()
            call = client.synthesize.call_args
            self.assertEqual(call.args[1], {"id": "el", "gender": "m"})
            self.assertEqual(call.kwargs["character_override"], {"provider": "edge", "voice_id": "unsaved-ID"})
            env["play_mp3"].assert_called_once_with("preview.wav")
            self.assertFalse(env["voice_preview_busy"][0])
            env["save_all"].assert_not_called()
            client.synthesize.return_value = (None, "invalid_character_override")
            remaining = env["individual_rows"]["un"]
            remaining["voice_var"].set("v")
            env["preview_character_voice"](remaining)
            self.assertTrue(jobs.pop()().startswith("✗"))
            self.assertFalse(env["voice_preview_busy"][0])
            self.assertNotEqual(env["settings_snapshot"](), snapshot)

    def test_custom_llm_hides_only_key_link(self):
        for server in existing_paths((DEV, WORKSHOP)):
            _, _, owner = self.environment(server)
            function = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "lay_llm")
            env = dict(H=34, LBL=20, ROW=70, flow=lambda *args: 190, llm_chips=[],
                       llm_provider_var=Var("Свой"), provider_keyname=lambda: "custom_llm_api_key",
                       temperature_var=Var(.7), result_txt={"llm": Widget()})
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.attr in ("place", "set"):
                        env[node.func.value.id] = Control()
            env["key_link"].place = Mock()
            exec(compile(ast.Module(body=[function], type_ignores=[]), "llm-layout", "exec"), env)
            env["lay_llm"](28, 792, 150, 560)
            env["key_link"].place.assert_not_called()
            self.assertEqual(env["key_f"].geo[2], 764)
            env["llm_provider_var"].set("OpenAI")
            env["lay_llm"](28, 792, 150, 560)
            env["key_link"].place.assert_called_once()

    def test_add_rename_duplicates_remove_and_placeholder_save(self):
        for server in existing_paths((DEV, WORKSHOP)):
            env, data, _ = self.environment(server)
            env["add_voice_character"]("un")
            row = env["individual_rows"]["un"]
            row["voice_var"].set("voice-one")
            env["character_overrides"]["un"]["future"] = True
            controls = row["controls"][:]
            env["rename_voice_character"](row, "el")
            self.assertNotIn("un", env["individual_rows"])
            self.assertEqual(env["individual_rows"]["el"]["controls"], controls)
            self.assertTrue(env["character_overrides"]["el"]["future"])
            env["add_voice_character"]("un")
            before = env["settings_snapshot"]()
            env["rename_voice_character"](row, "un")
            env["add_voice_character"]("el")
            env["add_voice_character"]("fake")
            self.assertEqual(env["settings_snapshot"](), before)
            count = len(env["MANAGED"])
            env["refresh_voice_rows"]()
            self.assertEqual(len(env["MANAGED"]), count)
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                self.assertTrue(env["save_all"]())
            self.assertEqual(env["tts_cfg"]["character_overrides"]["un"], {"provider": "auto", "voice_id": ""})
            env["remove_voice_character"]("el")
            self.assertFalse(row["voice_var"].callbacks)
            row["voice"].widget.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
