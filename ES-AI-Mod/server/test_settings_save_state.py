"""Save-state regressions with stubbed persistence and real, offline Tk windows."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tkinter as tk
import tkinter.ttk as ttk
import types
import unittest
from unittest.mock import Mock, mock_open, patch

from test_player_identity import DEV, WORKSHOP


def helpers(root, env):
    path = root / "settings_window.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and
                 n.name == "run_settings_window")
    names = {"settings_snapshot", "prompt_dirty", "refresh_save_state",
             "schedule_save_state", "persona_modified", "save_all",
             "save_current_prompt", "prompt_save", "prompt_select"}
    nodes = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
    return owner


class SettingsSaveStateTests(unittest.TestCase):
    def environment(self, root):
        data = {"player": {"id": "player", "name": "Player", "persona": "original"},
                "characters": [{"id": "un", "name": "NPC", "persona": "npc"}]}
        env = dict(json=json, native_vars=["model"], root=Mock(),
                   character_overrides={}, flush_character_voice=Mock(), load_character_voice=Mock(),
                      cameo_on=[True], auto_primary_on=[False], activity_on=[True], clock_on=[False], clock_show_time=[True], story_on=[False],
                   story_intensity=["low"], ui_lang=["ru"], saved_state=[None],
                   player_name_var=Mock(), prompt_data=copy.deepcopy(data),
                   prompt_targets=[("un", "NPC", False), ("player", "Player", True)],
                   prompt_idx=[1], persona_text=Mock(), pr_save=Mock(),
                   b_save=types.SimpleNamespace(kind="primary", _paint=Mock()),
                   chars_path="stub-characters.json", pr_chips=[Mock(), Mock()],
                   persona_who=Mock(), show_result=Mock(), set_status=Mock(),
                   tr=lambda text: text, _post=Mock(), layout=Mock())
        env["root"].getvar.return_value = "model-a"
        env["player_name_var"].get.return_value = "Player"
        env["persona_text"].get.return_value = "original"
        owner = helpers(root, env)
        save = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "save_all")
        for n in ast.walk(save):
            if isinstance(n, ast.Name) and n.id.endswith("_var") and n.id not in env:
                env[n.id] = Mock(get=Mock(return_value="1"))
        env.update(cfg={}, llm_cfg={}, tts_cfg={}, stt_cfg={}, keys={}, key_vars={},
                   prov_display={"groq": "Groq"}, TTS_MAP={"Auto": "auto"},
                   STT_MAP={"Auto": "auto"},
                   ui_i18n=types.SimpleNamespace(EDGE_VOICES={"ru": ("female", "male")}),
                   config_loader=types.SimpleNamespace(save_config=Mock(), save_keys=Mock(),
                                                       normalize_llm_urls=Mock()),
                   clock_values=Mock(return_value={"enabled": False, "start_time": "08:00",
                                                  "minutes_per_exchange": 5, "revision": 3}),
                   clock_read_config=Mock(return_value={"game_clock": {
                       "enabled": False, "start_time": "08:00", "minutes_per_exchange": 5,
                       "revision": 3}}))
        env["llm_provider_var"].get.return_value = "Groq"
        env["tts_var"].get.return_value = env["stt_var"].get.return_value = "Auto"
        env["clock_time_var"].get.return_value = "08:00"
        env["saved_state"][0] = env["settings_snapshot"]()
        return env, data, owner

    def test_clean_changed_and_reverted_baseline(self):
        for root in existing_paths((DEV, WORKSHOP)):
            with self.subTest(root=root):
                env, _, _ = self.environment(root)
                env["refresh_save_state"]()
                self.assertEqual(env["b_save"].kind, "chip")
                env["root"].getvar.return_value = "model-b"
                env["refresh_save_state"]()
                self.assertEqual(env["b_save"].kind, "primary")
                env["root"].getvar.return_value = "model-a"
                env["refresh_save_state"]()
                self.assertEqual(env["b_save"].kind, "chip")
                for key, value in (("auto_primary_on", True), ("activity_on", False), ("clock_on", True), ("clock_show_time", False), ("story_on", True),
                                   ("story_intensity", "high"), ("ui_lang", "en")):
                    previous = env[key][0]
                    env[key][0] = value
                    env["refresh_save_state"]()
                    self.assertEqual(env["b_save"].kind, "primary", key)
                    env[key][0] = previous
                env["player_name_var"].get.return_value = "New Name"
                env["refresh_save_state"]()
                self.assertEqual(env["b_save"].kind, "primary")
                env["pr_save"].set_selected.assert_called_with(True)

    def test_activity_save_false_is_independent_and_becomes_baseline(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, data, _ = self.environment(root)
            env["activity_on"][0] = False
            env["refresh_save_state"]()
            self.assertEqual(env["b_save"].kind, "primary")
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                self.assertTrue(env["save_all"]())
            self.assertIs(env["cfg"]["npc_activity_enabled"], False)
            self.assertIs(env["cfg"]["cameo_enabled"], True)
            self.assertIs(env["cfg"]["scene_auto_primary"], False)
            self.assertEqual(env["b_save"].kind, "chip")

    def test_success_saves_name_persona_and_clears_highlights(self):
        for root in existing_paths((DEV, WORKSHOP)):
            with self.subTest(root=root):
                env, data, _ = self.environment(root)
                env["root"].getvar.return_value = "model-b"
                env["player_name_var"].get.return_value = "New Name"
                env["persona_text"].get.return_value = "new persona"
                data["other"] = "latest disk value"
                opener = mock_open(read_data=json.dumps(data))
                with patch("builtins.open", opener):
                    self.assertTrue(env["save_all"]())
                saved = json.loads("".join(c.args[0] for c in opener().write.call_args_list))
                self.assertEqual(saved["player"]["name"], "New Name")
                self.assertEqual(saved["player"]["persona"], "new persona")
                self.assertEqual(saved["other"], "latest disk value")
                self.assertEqual(env["b_save"].kind, "chip")
                env["pr_save"].set_selected.assert_called_with(False)
                self.assertEqual(env["saved_state"][0], env["settings_snapshot"]())
                env["config_loader"].save_config.assert_called_once_with()
                env["config_loader"].save_keys.assert_called_once_with()
                env["_post"].assert_called_once_with("/reload")

    def test_display_only_save_persists_without_clock_reset(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, data, owner = self.environment(root)
            nodes = [n for n in owner.body if isinstance(n, ast.FunctionDef)
                     and n.name == "clock_values"]
            env["clock_step_var"] = Mock(get=Mock(return_value="5"))
            exec(compile(ast.Module(body=nodes, type_ignores=[]), "clock-values", "exec"), env)
            env["clock_show_time"][0] = False
            env["refresh_save_state"]()
            self.assertEqual(env["b_save"].kind, "primary")
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                self.assertTrue(env["save_all"]())
            self.assertEqual(env["cfg"]["game_clock"], dict(enabled=False, show_time=False,
                             start_time="08:00", minutes_per_exchange=5, revision=3))
            self.assertEqual(env["b_save"].kind, "chip")

    def test_clock_settings_use_userdata_path_without_writes(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, _, owner = self.environment(root)
            env.update(os=os, config_loader=types.SimpleNamespace(
                       user_data_dir=lambda: "stub-userdata", _DIR="wrong-server-dir"))
            nodes = [n for n in owner.body if isinstance(n, ast.FunctionDef)
                     and n.name in ("clock_config_path", "clock_read_config")]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), "clock-path", "exec"), env)
            config = {"game_clock": {"show_time": False, "revision": 7}}
            opener = mock_open(read_data=json.dumps(config))
            with patch("os.path.exists", return_value=True), patch("builtins.open", opener):
                self.assertEqual(env["clock_read_config"](), config)
            opener.assert_called_once_with(os.path.join("stub-userdata", "config.json"), encoding="utf-8")

    def test_failures_retain_main_save_highlight_and_baseline(self):
        for root in existing_paths((DEV, WORKSHOP)):
            for failure in ("persona", "config", "keys", "validation"):
                with self.subTest(root=root, failure=failure):
                    env, data, _ = self.environment(root)
                    baseline = env["saved_state"][0]
                    env["root"].getvar.return_value = "model-b"
                    env["refresh_save_state"]()
                    if failure == "persona":
                        env["save_current_prompt"] = Mock(side_effect=OSError("write failed"))
                    elif failure == "validation":
                        env["clock_values"].return_value = None
                    else:
                        getattr(env["config_loader"], "save_" + failure).side_effect = OSError("write failed")
                    with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                        self.assertFalse(env["save_all"]())
                    self.assertEqual(env["saved_state"][0], baseline)
                    self.assertEqual(env["b_save"].kind, "primary")
                    env["_post"].assert_not_called()

    def test_name_only_write_failure_stays_dirty_after_refresh(self):
        for root in existing_paths((DEV, WORKSHOP)):
            for target in ("save_config", "save_keys"):
                env, data, _ = self.environment(root)
                env["player_name_var"].get.return_value = "Unsaved Name"
                getattr(env["config_loader"], target).side_effect = OSError("write failed")
                with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                    self.assertFalse(env["save_all"]())
                env["refresh_save_state"]()
                self.assertEqual(env["b_save"].kind, "primary")
                env["pr_save"].set_selected.assert_called_with(True)

    def test_persona_modified_does_not_reschedule_clear_event(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, _, _ = self.environment(root)
            env["persona_text"].edit_modified.side_effect = [True, None, False]
            env["persona_modified"]()
            env["persona_modified"]()
            env["root"].after_idle.assert_called_once_with(env["refresh_save_state"])
            self.assertEqual(env["persona_text"].edit_modified.call_args_list[1].args, (False,))

    def test_prompt_select_restores_old_highlight_reset_without_globals(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, _, owner = self.environment(root)
            env["prompt_select"](0)
            env["pr_save"].set_selected.assert_called_once_with(False)
            env["player_name_var"].set.assert_not_called()
            self.assertNotIn("globals()", ast.unparse(next(n for n in owner.body
                             if isinstance(n, ast.FunctionDef) and n.name == "prompt_select")))

    def test_snapshot_tracks_only_persisted_inputs(self):
        for root in existing_paths((DEV, WORKSHOP)):
            env, _, owner = self.environment(root)
            assignment = next(n for n in owner.body if isinstance(n, ast.Assign) and
                              any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                  and t.value.id == "native_vars" for t in n.targets))
            names = {n.id for n in assignment.value.elts}
            self.assertTrue({"clock_time_var", "clock_step_var", "model_var"} <= names)
            self.assertFalse({"hist_char_var", "lang_var", "player_name_var", "no_key_var"} & names)
            self.assertTrue(all(not name.startswith("hist") for name in names))

    def test_reset_choices_preserve_settings_for_keys_only(self):
        for root in existing_paths((DEV, WORKSHOP)):
            for settings, keys in ((True, False), (False, True)):
                env, _, owner = self.environment(root)
                reset = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and
                             n.name == "reset_all")
                for n in ast.walk(reset):
                    if isinstance(n, ast.Name) and n.id.endswith(("_var", "_val", "_sw")):
                        env.setdefault(n.id, Mock())
                env.update(es_confirm_toggles=Mock(return_value={"vals": {
                               "settings": settings, "keys": keys}}),
                           DEFAULTS={"provider": "Groq", "max_tokens": 400,
                                     "temperature": 0.9, "tts": "Auto", "stt": "Auto"},
                           LLM_PRESETS={"Groq": ("url", "model", "key")},
                           select_story_intensity=Mock(), llm_refresh=Mock(),
                           tts_refresh=Mock(), stt_refresh=Mock(), sync_key_field=Mock(),
                           key_vars={"key": Mock()}, save_all=Mock(return_value=True))
                env["story_on"][0] = env["clock_on"][0] = True
                env["character_overrides"]["un"] = {"provider": "off", "voice_id": ""}
                env["clock_show_time"][0] = False
                env["activity_on"][0] = False
                exec(compile(ast.Module(body=[reset], type_ignores=[]), "reset", "exec"), env)
                env["reset_all"]()
                self.assertEqual(env["story_on"][0], not settings)
                self.assertEqual(env["clock_on"][0], not settings)
                self.assertEqual(env["clock_show_time"][0], settings)
                self.assertEqual(env["activity_on"][0], settings)
                if settings:
                    self.assertEqual(env["character_overrides"], {})
                    env["load_character_voice"].assert_called_once_with()
                    env["clock_time_var"].set.assert_called_once_with("08:00")
                    env["clock_step_var"].set.assert_called_once_with("5")
                    env["select_story_intensity"].assert_called_once_with("low")
                    env["key_vars"]["key"].set.assert_not_called()
                else:
                    self.assertIn("un", env["character_overrides"])
                    env["load_character_voice"].assert_not_called()
                    env["model_var"].set.assert_not_called()
                    env["key_vars"]["key"].set.assert_called_once_with("")

    def test_real_tk_both_copies_offline(self):
        import ui_i18n

        for root_dir in existing_paths((DEV, WORKSHOP)):
            with self.subTest(root=root_dir):
                loader = types.ModuleType("config_loader")
                loader.cfg = {"game_clock": {"enabled": False, "start_time": "08:00",
                                             "minutes_per_exchange": 5, "revision": 0}}
                loader.keys = {}
                loader._DIR = str(root_dir)
                loader.reload_all = Mock()
                loader.save_config = Mock()
                loader.save_keys = Mock()
                loader.normalize_llm_urls = Mock()
                store = types.ModuleType("characters_store")
                store.characters = Mock(return_value=[])
                store.get_character = Mock()
                modules = {"config_loader": loader, "characters_store": store,
                           "ui_i18n": ui_i18n, "llm_client": types.ModuleType("llm_client"),
                           "tts_client": types.ModuleType("tts_client"),
                           "stt_client": types.ModuleType("stt_client")}
                path = root_dir / "settings_window.py"
                spec = importlib.util.spec_from_file_location("settings_smoke", path)
                window = importlib.util.module_from_spec(spec)
                original_path = sys.path[:]
                real_open = open
                writes = mock_open()

                def safe_open(path, mode="r", *args, **kwargs):
                    if any(flag in mode for flag in "wax+"):
                        self.assertEqual(os.fspath(path), str(root_dir / "es_characters.json"))
                        return writes(path, mode, *args, **kwargs)
                    return real_open(path, mode, *args, **kwargs)

                def mainloop(root):
                    # Inspect existing debug callbacks' closures, without production hooks.
                    env = {}
                    pending = list(root._es_debug.values())
                    seen = set()
                    while pending:
                        fn = pending.pop()
                        if isinstance(fn, (list, tuple)):
                            pending.extend(fn)
                            continue
                        if not isinstance(fn, types.FunctionType) or id(fn) in seen:
                            continue
                        seen.add(id(fn))
                        values = {name: cell.cell_contents for name, cell in
                                  zip(fn.__code__.co_freevars, fn.__closure__ or ())}
                        env.update(values)
                        pending.extend(values.values())
                        if "lang_btn" in values:
                            pending.extend((values["lang_btn"].command, values["lang_btn"].src))
                        if "individual_add" in values:
                            pending.append(values["individual_add"].command)
                    try:
                        root.update_idletasks()
                        self.assertEqual(env["b_save"].kind, "chip")
                        self.assertFalse(any(isinstance(w, ttk.Combobox) for w in
                                             root.winfo_children()))
                        owner = next(n for n in ast.parse(path.read_text(encoding="utf-8-sig")).body
                                     if isinstance(n, ast.FunctionDef) and n.name == "run_settings_window")
                        self.assertFalse(any(isinstance(n, ast.Call) and
                                             isinstance(n.func, ast.Attribute) and
                                             n.func.attr == "Combobox" for n in ast.walk(owner)))
                        lang = env["lang_btn"]
                        menu = env["lang_menu"]
                        self.assertEqual(lang.src, "Язык/Lang")
                        self.assertEqual(lang.text, window.tr("Язык/Lang"))
                        self.assertEqual(len(env["canvas"].find_withtag(lang.tag)), 2)
                        self.assertTrue(all(env["canvas"].itemcget(item, "state") == "normal"
                                            for item in env["canvas"].find_withtag(lang.tag)))
                        self.assertEqual([menu.entrycget(i, "label") for i in range(2)],
                                         ["Русский", "English"])
                        with patch.object(menu, "tk_popup") as popup, \
                                patch.object(menu, "grab_release") as release:
                            lang.command()
                            popup.assert_called_once_with(env["canvas"].winfo_rootx() + lang.x,
                                                          env["canvas"].winfo_rooty() + lang.y + lang.h)
                            release.assert_called_once_with()
                        for tab in range(6):
                            root._es_debug["switch_tab"](tab)
                            root.update_idletasks()
                            self.assertEqual(env["b_save"].kind, "chip")
                        root._es_debug["switch_tab"](0)
                        initial_provider = env["llm_provider_var"].get()
                        initial_url = env["url_var"].get()
                        initial_model = env["model_var"].get()
                        for geometry in ("820x640", "960x740", "1280x900"):
                            root.geometry(geometry)
                            root.update()
                            if "b_export" in env:
                                for language in ("ru", "en"):
                                    window.ui_lang[0] = language
                                    for button in (env["b_hist"], env["b_reset"], env["b_folder"],
                                                   env["b_export"], env["b_import"], env["b_deps"], env["b_save"]):
                                        button.retranslate()
                                    root._es_debug["layout"]()
                                    self.assertLess(env["b_hist"].y, env["b_folder"].y)
                                    self.assertLess(env["b_reset"].y, env["b_folder"].y)
                                    self.assertLessEqual(env["b_folder"].x + env["b_folder"].w, env["b_export"].x)
                                    self.assertLessEqual(env["b_export"].x + env["b_export"].w, env["b_import"].x)
                                    buttons = [env[n] for n in ("b_hist", "b_reset", "b_folder", "b_export",
                                                               "b_import", "b_deps", "b_save")]
                                    for button in buttons:
                                        self.assertGreaterEqual(button.x, 28)
                                        self.assertLessEqual(button.x + button.w, env["canvas"].winfo_width() - 28)
                                    for first in buttons:
                                        for second in buttons:
                                            if first is not second and first.y == second.y and first.x < second.x:
                                                self.assertLessEqual(first.x + first.w, second.x)
                                window.ui_lang[0] = "ru"
                            chips = env["llm_chips"]
                            cerebras = next(c for c in chips if c.src == "Cerebras")
                            cohere = next(c for c in chips if c.src == "Cohere")
                            self.assertEqual(chips[chips.index(cohere) + 1], cerebras)
                            cerebras.command()
                            root.update_idletasks()
                            self.assertEqual(env["url_var"].get(), "https://api.cerebras.ai/v1")
                            self.assertEqual(env["model_var"].get(), "qwen-3.8-27b")
                            self.assertTrue(cerebras.visible)
                            self.assertGreaterEqual((cerebras.y, cerebras.x), (cohere.y, cohere.x))
                            self.assertGreater(env["url_f"].geo[1], max(c.y + c.h for c in chips))
                        env["llm_provider_var"].set(initial_provider)
                        env["url_var"].set(initial_url)
                        env["model_var"].set(initial_model)
                        env["llm_refresh"]()
                        root.geometry("960x740")
                        root.update()
                        root._es_debug["switch_tab"](1)
                        self.assertFalse(env["character_overrides"])
                        self.assertFalse(env["individual_rows"])
                        self.assertTrue(env["individual_add"].visible)
                        targets = env["voice_targets"]
                        env["add_voice_character"](targets[0][0])
                        env["add_voice_character"](targets[1][0])
                        root.update_idletasks()
                        self.assertEqual(len(env["character_overrides"]), 2)
                        self.assertGreater(env["canvas"].coords(env["individual_sec"].id)[1],
                                           env["canvas"].coords(env["tts_sec"].id)[1])
                        rows = list(env["individual_rows"].values())
                        for row in rows:
                            self.assertEqual(row["character"].y, row["provider"].y)
                            self.assertGreater(row["voice"].geo[0], row["provider"].x + row["provider"].w)
                            self.assertEqual((row["remove"].w, row["remove"].h), (34, 34))
                            self.assertEqual(row["remove"].text, "×")
                        rows[0]["voice_var"].set("offline-first-ID")
                        rows[1]["voice_var"].set("offline-second-ID")
                        self.assertEqual(env["character_overrides"][targets[0][0]]["voice_id"], "offline-first-ID")
                        self.assertEqual(env["character_overrides"][targets[1][0]]["voice_id"], "offline-second-ID")
                        for language in ("ru", "en"):
                            root.geometry("820x640" if language == "en" else "960x740")
                            root.update()
                            window.ui_lang[0] = language
                            rows[0]["provider"].retranslate()
                            self.assertEqual(rows[0]["provider"].text,
                                             "Global provider" if language == "en" else "Общий провайдер")
                            for provider in window.TTS_PROVIDERS:
                                root._es_debug["tts"](provider)
                                root.update_idletasks()
                                last = {"edge": "edge_mf", "sapi": "sapi_mf", "fish": "fv_mf",
                                        "elevenlabs": "el_voice_mf", "openai": "oa_voice_mf",
                                        "custom": "cu_vm"}.get(window.TTS_MAP[provider])
                                if last:
                                    self.assertGreater(env["canvas"].coords(env["individual_sec"].id)[1],
                                                       env[last].geo[1] + 34)
                                self.assertLess(env["tts_test"].y + 34,
                                                env["canvas"].coords(env["individual_sec"].id)[1])
                                env["tts_bar"].command("moveto", 1)
                                root.update_idletasks()
                                self.assertEqual(env["tts_scroll"][0], env["tts_scroll"][1])
                                self.assertTrue(env["individual_add"].visible)
                                for obj in env["MANAGED"]:
                                    if not obj.visible:
                                        continue
                                    target = getattr(obj, "tag", None) or getattr(obj, "id", None) or getattr(obj, "img_id", None)
                                    box = env["canvas"].bbox(target) if target is not None else None
                                    if box:
                                        self.assertGreaterEqual(box[1], 150)
                                        height = env["canvas"].winfo_height()
                                        self.assertLessEqual(box[3], (height if height > 10 else window.WIN_H) - 78)
                        window.ui_lang[0] = "ru"
                        for cid in list(env["character_overrides"]):
                            env["remove_voice_character"](cid)
                        root._es_debug["tts"]("Авто")
                        env["tts_bar"].command("moveto", 0)
                        root._es_debug["switch_tab"](3)
                        self.assertTrue(env["auto_primary_sw"].visible)
                        self.assertTrue(env["activity_sw"].visible)
                        self.assertTrue(env["activity_on"][0])
                        self.assertEqual(env["canvas"].itemcget(env["activity_lbl"].id, "text"),
                                         window.tr("Занятость персонажей"))
                        env["activity_sw"].command()
                        root.update_idletasks()
                        self.assertFalse(env["activity_on"][0])
                        self.assertEqual(env["b_save"].kind, "primary")
                        env["activity_sw"].command()
                        root.update_idletasks()
                        self.assertEqual(env["b_save"].kind, "chip")
                        self.assertFalse(env["auto_primary_on"][0])
                        env["auto_primary_sw"].command()
                        root.update_idletasks()
                        self.assertTrue(env["auto_primary_on"][0])
                        self.assertEqual(env["b_save"].kind, "primary")
                        env["auto_primary_sw"].command()
                        root.update_idletasks()
                        self.assertEqual(env["b_save"].kind, "chip")
                        env["clock_sw"].command()
                        root.update_idletasks()
                        self.assertGreater(env["canvas"].coords(env["clock_show_sw"].img_id)[0],
                                           env["canvas"].coords(env["clock_sw"].img_id)[0])
                        self.assertEqual(env["canvas"].itemcget(env["clock_show_lbl"].id, "text"),
                                         window.tr("Показывать время"))
                        env["clock_show_sw"].command()
                        self.assertFalse(env["clock_show_time"][0])
                        self.assertTrue(env["clock_on"][0])
                        self.assertEqual(env["b_save"].kind, "primary")
                        env["clock_show_sw"].command()
                        env["clock_sw"].command()
                        root.update_idletasks()
                        for name in ("clock_show_sw", "clock_show_lbl", "clock_time_l",
                                     "clock_time_f", "clock_step_l", "clock_step_f", "clock_minus", "clock_plus"):
                            self.assertFalse(env[name].visible, name)
                        self.assertEqual(env["b_save"].kind, "chip")
                        env["model_var"].set("offline-smoke-model")
                        root.update_idletasks()
                        self.assertEqual(env["b_save"].kind, "primary")
                        with patch("builtins.open", safe_open):
                            env["b_save"].command()
                        self.assertEqual(env["b_save"].kind, "chip")
                        loader.save_config.assert_called_once_with()
                        self.assertIs(loader.cfg["npc_activity_enabled"], True)
                        loader.save_keys.assert_called_once_with()
                        window._post.assert_called_once_with("/reload")
                        language = "English" if window.ui_lang[0] == "ru" else "Русский"
                        with patch("builtins.open", safe_open):
                            menu.invoke(1 if language == "English" else 0)
                            root.update_idletasks()
                        self.assertEqual(window.ui_lang[0], "en" if language == "English" else "ru")
                        self.assertEqual(lang.text, window.tr("Язык/Lang"))
                        self.assertEqual(env["canvas"].itemcget(env["clock_show_lbl"].id, "text"),
                                         window.tr("Показывать время"))
                        self.assertEqual(lang.w, lang.nat_w)
                        self.assertEqual(env["b_save"].kind, "chip")
                        env["persona_text"].insert("end", " offline persona")
                        root.update()
                        self.assertEqual(env["b_save"].kind, "primary")
                        with patch("builtins.open", safe_open):
                            env["pr_save"].command()
                        self.assertEqual(env["b_save"].kind, "chip")
                    finally:
                        for callback in root.tk.splitlist(root.tk.call("after", "info")):
                            root.after_cancel(callback)
                        root.destroy()

                try:
                    with patch.dict(sys.modules, modules), patch("urllib.request.urlopen", Mock()), \
                            patch("threading.Thread.start", Mock()), patch.object(tk.Tk, "mainloop", mainloop):
                        spec.loader.exec_module(window)
                        window._already_running = Mock(return_value=False)
                        window._post = Mock()
                        window.run_settings_window()
                finally:
                    sys.path[:] = original_path


if __name__ == "__main__":
    unittest.main()
