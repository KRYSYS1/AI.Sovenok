"""Offline delivery tests; all writable paths are in the approved temp directory."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import json
import os
import sys
import tempfile
import textwrap
import threading
import types
import subprocess
import unittest
import __future__
from unittest.mock import Mock, patch

from test_story_events import DEV, WORKSHOP, TEMP, module, StoryTests
from test_cameo_clothing import ROOTS, StoreDict, StoreList

ENGINE = GAME_ROOT


class DisplayCharacter:
    """The installed engine's callback ordering, including global callbacks."""
    def __init__(self, config, callback=None, interaction=None, fail=False, repeat=1):
        self.config = config
        self.display_args = dict(callback=callback)
        self.interaction = interaction
        self.fail = fail
        self.repeat = repeat

    def __call__(self, text, callback=None):
        callbacks = self.config.all_character_callbacks + [callback]
        for event in ("begin", "show"):
            for fn in callbacks:
                fn(event, interact=True, type="say", custom="inherited")
        if self.fail:
            raise RuntimeError("text display validation failed")
        for _ in range(self.repeat):
            for fn in callbacks:
                fn("show_done", interact=True, type="say", custom="inherited")
        if self.interaction:
            self.interaction()
        for fn in callbacks:
            fn("end", interact=True, type="say", custom="inherited")


class DeliveryTests(unittest.TestCase):
    def client(self, root, directory):
        with open(os.path.join(root, "es_ai_delivery.rpy"), encoding="utf-8") as stream:
            source = stream.read().split("init 12 python:\n", 1)[1]
        env = dict(config=types.SimpleNamespace(quit_callbacks=[lambda: None],
                                              character_callback=None, all_character_callbacks=[]),
                   unicode=str, es_ai_log=Mock(), es_ai_public_snapshot=lambda: [],
                   es_ai_story_ack_snapshot=lambda: [], es_ai_run_async=Mock())
        with patch.dict(sys.modules):
            sys.modules.pop("_es_ai_delivery_backend", None)
            exec(compile(textwrap.dedent(source), "delivery", "exec"), env)
        env["es_ai_delivery_path"] = lambda: os.path.join(directory, "delivery_outbox.json")
        return env

    def speech_env(self, root, directory):
        env = self.client(root, directory)
        events, acks = [], []
        env.update(ES_AI_CLOCK=dict(lines=0), es_ai_public_snapshot=lambda: events,
                   es_ai_story_ack_snapshot=lambda: acks,
                   es_ai_public_record=lambda cid, raw: events.append(dict(id=str(len(events)), speaker_id=cid, text=raw)),
                   es_ai_story_ack_record=lambda ack: acks.append(ack) if ack else None)
        return env, events, acks

    def test_shadowed_builtin_types_restart_empty_and_nonempty(self):
        for root in ROOTS:
            for nonempty in (False, True):
                with self.subTest(root=root, nonempty=nonempty), tempfile.TemporaryDirectory(dir=TEMP) as directory:
                    env = self.client(root, directory)
                    env.update(list=StoreList, dict=StoreDict)
                    expected = dict(version=1, public_events=[dict(id="restart")] if nonempty else [],
                                    story_acks=[dict(token="t", delivery_id="d")] if nonempty else [])
                    env["_es_ai_delivery_save"](expected)
                    restarted = self.client(root, directory)
                    restarted.update(list=StoreList, dict=StoreDict)
                    restarted["all"] = Mock(side_effect=AssertionError("Ren'Py Character named all"))
                    restarted["es_ai_delivery_flush"](send=False)
                    self.assertTrue(restarted["_delivery_backend"].loaded)
                    self.assertEqual(restarted["_delivery_backend"].data, expected)
                    self.assertIs(type(restarted["_delivery_backend"].data), dict)
                    self.assertIs(type(restarted["_delivery_backend"].data["public_events"]), list)
                    restarted["es_ai_run_async"].assert_not_called()
                    restarted["es_ai_log"].assert_not_called()

    def test_final_display_persisted_before_quit_exception(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env, events, acks = self.speech_env(root, directory)
                ack = dict(token="token", delivery_id="delivery")
                def quit_during_interaction():
                    with open(env["es_ai_delivery_path"]()) as stream:
                        saved = json.load(stream)
                    self.assertEqual(saved["public_events"], events)
                    self.assertEqual(saved["story_acks"], [ack])
                    env["es_ai_run_async"].assert_not_called()
                    env["config"].quit_callbacks[-1]()
                    raise SystemExit("window quit")
                speaker = DisplayCharacter(env["config"], interaction=quit_during_interaction)
                with self.assertRaises(SystemExit):
                    env["es_ai_delivery_say"](speaker, "safe", "sl", "raw", ack)
                self.assertEqual(len(events), 1)
                self.assertEqual(acks, [ack])
                self.assertEqual(env["ES_AI_CLOCK"]["lines"], 1)

    def test_failed_display_does_not_record_or_save(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env, events, acks = self.speech_env(root, directory)
                speaker = DisplayCharacter(env["config"], fail=True)
                with self.assertRaises(RuntimeError):
                    env["es_ai_delivery_say"](speaker, "safe", "sl", "raw", dict(token="t", delivery_id="d"))
                self.assertFalse(events)
                self.assertFalse(acks)
                self.assertFalse(os.path.exists(env["es_ai_delivery_path"]()))
                self.assertEqual(env["ES_AI_CLOCK"]["lines"], 0)

    def test_existing_callbacks_global_fallback_list_and_single_preserved(self):
        for root in ROOTS:
            for variant in ("single", "list", "fallback"):
                with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                    env, events, acks = self.speech_env(root, directory)
                    calls = []
                    old = lambda event, **kw: calls.append((event, kw))
                    global_calls = []
                    env["config"].all_character_callbacks.append(lambda event, **kw: global_calls.append(event))
                    env["config"].character_callback = old
                    original = old if variant == "single" else ([old] if variant == "list" else None)
                    speaker = DisplayCharacter(env["config"], callback=original, repeat=2)
                    env["es_ai_delivery_say"](speaker, "safe", "sl", "raw")
                    self.assertIs(speaker.display_args["callback"], original)
                    self.assertEqual([event for event, kw in calls], ["begin", "show", "show_done", "show_done", "end"])
                    self.assertEqual(global_calls, [event for event, kw in calls])
                    self.assertTrue(all(kw["custom"] == "inherited" for event, kw in calls))
                    self.assertEqual(len(events), 1)

    def test_reentrant_speech_and_repeated_show_done_record_once_per_call(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env, events, acks = self.speech_env(root, directory)
                inner = DisplayCharacter(env["config"], repeat=3)
                def old(event, **kw):
                    if event == "show":
                        env["es_ai_delivery_say"](inner, "inner", "mt", "inner raw")
                outer = DisplayCharacter(env["config"], callback=old, repeat=3)
                env["es_ai_delivery_say"](outer, "outer", "sl", "outer raw")
                self.assertEqual([e["speaker_id"] for e in events], ["mt", "sl"])
                self.assertEqual(len({e["id"] for e in events}), 2)
                self.assertEqual(env["ES_AI_CLOCK"]["lines"], 2)
                env["es_ai_run_async"].assert_not_called()

    def test_display_save_failure_keeps_queues_and_logs(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env, events, acks = self.speech_env(root, directory)
                env["_es_ai_delivery_save"] = Mock(side_effect=OSError("disk full"))
                env["es_ai_delivery_say"](DisplayCharacter(env["config"]), "safe", "sl", "raw", dict(token="t", delivery_id="d"))
                self.assertEqual(len(events), 1)
                self.assertEqual(len(acks), 1)
                env["es_ai_log"].assert_called_once()
                env["es_ai_run_async"].assert_not_called()

    def test_owned_speech_paths_use_display_helper_and_reset_guard_on_quit(self):
        from test_cameo_clothing import ClothingTests, load
        for root in ROOTS:
            for cameo in (False, True):
                with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                    legacy = ClothingTests().environment(root)
                    env, events, acks = self.speech_env(root, directory)
                    actual_say = env["es_ai_delivery_say"]
                    backend_names = dict(env)
                    env.update(legacy)
                    for key in backend_names:
                        if key.startswith(("_delivery", "_es_ai_delivery", "es_ai_delivery")) or key == "config":
                            env[key] = backend_names[key]
                    env.update(es_ai_delivery_say=actual_say,
                               es_ai_public_record=backend_names["es_ai_public_record"],
                               es_ai_public_snapshot=backend_names["es_ai_public_snapshot"],
                               es_ai_story_ack_record=backend_names["es_ai_story_ack_record"],
                               es_ai_story_ack_snapshot=backend_names["es_ai_story_ack_snapshot"],
                               ES_AI_CLOCK=dict(lines=0), es_ai_girl_enter=lambda *a: None,
                               ES_AI_LOC_HAS_GIRL=[False])
                    load(os.path.join(root, "es_ai_api.rpy"), env, {"es_ai_say_girl"})
                    load(os.path.join(root, "es_ai_cameo.rpy"), env, {"es_ai_cameo_speak"})
                    def quit_now():
                        raise SystemExit("quit")
                    env["es_ai_speakers"] = dict(sl=DisplayCharacter(env["config"], interaction=quit_now))
                    with self.assertRaises(SystemExit):
                        if cameo:
                            env["es_ai_cameo_speak"]("sl", "visible", story_ack=dict(token="t", delivery_id="d"))
                        else:
                            env["es_ai_say_girl"]("sl", "visible")
                    self.assertFalse(env["es_ai_internal_speaking"][0])
                    self.assertEqual(len(events), 1)
                    with open(env["es_ai_delivery_path"]()) as stream:
                        saved = json.load(stream)
                    self.assertEqual(saved["public_events"], events)
                    self.assertEqual(len(saved["story_acks"]), int(cameo))

    def test_installed_engine_callback_contract(self):
        if not os.path.isfile(os.path.join(ENGINE, "renpy", "character.py")):
            self.skipTest("Game engine source unavailable")
        with open(os.path.join(ENGINE, "renpy", "character.py"), encoding="utf-8") as stream:
            source = stream.read()
        display = source[source.index("def display_say("):source.index("class ADVCharacter")]
        self.assertLess(display.index("what_text = show_function"), display.index('c("show_done"'))
        self.assertLess(display.index('raise Exception("The say screen'), display.index('c("show_done"'))
        self.assertLess(display.index('c("show_done"'), display.index("renpy.ui.interact"))
        self.assertIn("callback = renpy.config.all_character_callbacks + callback", display)
        self.assertIn("return Character(kind=self, **kwargs)(what, interact=interact", source)
        # Execute the installed engine's real per-call cloning branch, not a guessed API.
        branch = source.split('        if kwargs:\n', 1)[1].split('\n\n', 1)[0]
        self.assertIn("Character(kind=self", branch)
        env = dict(Character=Mock(return_value=Mock(return_value="shown")), self=object(),
                   kwargs=dict(callback=Mock()), what="text", interact=True, _call_done=True,
                   multiple=None, _mode=None, _with_none=None)
        function = "def invoke():\n" + textwrap.indent(textwrap.dedent(branch), "    ")
        exec(function, env)
        self.assertEqual(env["invoke"](), "shown")
        self.assertIs(env["Character"].call_args.kwargs["callback"], env["kwargs"]["callback"])

    def test_actual_python2_init_compile_and_shadowed_restart(self):
        if not os.path.isfile(os.path.join(ENGINE, "lib", "windows-i686", "python.exe")):
            self.skipTest("Bundled Python 2 unavailable")
        from test_deploy_workshop import deploy
        fixtures = []
        for root in ROOTS:
            files = []
            for filename in ("es_ai_delivery.rpy", "es_ai_api.rpy", "es_ai_cameo.rpy"):
                with open(os.path.join(root, filename), "rb") as stream:
                    files.append((filename, deploy.init_blocks(stream.read())))
            fixtures.append((root, files))
        command = [os.path.join(ENGINE, "lib", "windows-i686", "python.exe"), "-O", "-B",
                   os.path.join(DEV, "delivery_py2_check.py")]
        result = subprocess.run(command, input=json.dumps(fixtures), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("both roots Python 2", result.stdout)
        self.assertEqual(result.stdout.count("full init + in-memory load:"), 4 * len(ROOTS))
        self.assertEqual(result.stdout.count("module_name=str"), 4 * len(ROOTS))
        print(result.stdout)
        # Prove the harness catches the original startup crash, without editing either install.
        original = json.dumps(fixtures).replace(
            '_delivery_types.ModuleType(_delivery_builtins.str(\\"_es_ai_delivery_backend\\"))',
            '_delivery_types.ModuleType(\\"_es_ai_delivery_backend\\")')
        self.assertNotEqual(original, json.dumps(fixtures))
        broken = subprocess.run(command, input=original, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(broken.returncode, 0)
        self.assertIn("TypeError", broken.stderr)
        self.assertIn("module.__init__() argument 1 must be string, not unicode", broken.stderr)
        print("original unfixed ModuleType negative control: " + broken.stderr.splitlines()[-1])

    def test_python3_entire_init_unicode_literals_shadowed_str_and_reused_module(self):
        from test_deploy_workshop import deploy
        from delivery_py2_check import check_init
        for root in ROOTS:
            with self.subTest(root=root), patch.dict(sys.modules):
                with open(os.path.join(root, "es_ai_delivery.rpy"), "rb") as stream:
                    blocks = deploy.init_blocks(stream.read())
                self.assertEqual(len(blocks), 1)
                code = compile(blocks[0], "delivery", "exec", __future__.unicode_literals.compiler_flag, True)
                check_init(code)

    def test_lazy_final_flush_restart_failure_and_duplicate_workers(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env = self.client(root, directory)
                path = env["es_ai_delivery_path"]()
                self.assertFalse(os.path.exists(path))
                self.assertEqual(len(env["config"].quit_callbacks), 2)
                event = dict(id="final", text="Actual speech")
                ack = dict(token="a", delivery_id="b")
                env["es_ai_public_snapshot"] = lambda: [event]
                env["es_ai_story_ack_snapshot"] = lambda: [ack]
                env["config"].quit_callbacks[-1]()
                with open(path) as stream:
                    self.assertEqual(json.load(stream)["public_events"], [event])
                env["es_ai_delivery_flush"]()
                self.assertEqual(env["es_ai_run_async"].call_count, 1)
                env["es_ai_http"] = Mock(return_value=dict(ok=False))
                env["_es_ai_delivery_send"]()
                self.assertEqual(env["_delivery_backend"].data["story_acks"], [ack])
                restarted = self.client(root, directory)
                restarted["es_ai_delivery_flush"]()
                restarted["es_ai_http"] = Mock(return_value=dict(ok=True, public_event_ids=["final"], story_acks=[ack]))
                restarted["_es_ai_delivery_send"]()
                with open(path) as stream:
                    data = json.load(stream)
                self.assertEqual(data, dict(version=1, public_events=[], story_acks=[]))
                self.assertEqual(restarted["es_ai_http"].call_args.kwargs, dict(timeout=2))

    def test_worker_does_not_remove_concurrent_new_events(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env = self.client(root, directory)
                events = [dict(id="first")]
                env["es_ai_public_snapshot"] = lambda: events
                env["es_ai_delivery_flush"]()
                def send(route, payload, timeout):
                    if payload["public_events"][0]["id"] == "first":
                        events.append(dict(id="second"))
                        env["es_ai_delivery_flush"]()
                        return dict(ok=True, public_event_ids=["first"])
                    return dict(ok=False)
                env["es_ai_http"] = send
                env["_es_ai_delivery_send"]()
                self.assertEqual(env["_delivery_backend"].data["public_events"], [dict(id="second")])

    def test_local_retirement_save_failure_and_unknown_version_preserve_file(self):
        for root in ROOTS:
            with tempfile.TemporaryDirectory(dir=TEMP) as directory:
                env = self.client(root, directory)
                event = dict(id="retained")
                env["es_ai_public_snapshot"] = lambda: [event]
                env["es_ai_delivery_flush"]()
                env["es_ai_http"] = Mock(return_value=dict(ok=True, public_event_ids=["retained"]))
                save = env["_es_ai_delivery_save"]
                env["_es_ai_delivery_save"] = Mock(side_effect=OSError("disk full"))
                env["_es_ai_delivery_send"]()
                self.assertEqual(env["_delivery_backend"].data["public_events"], [event])
                env["_es_ai_delivery_save"] = save
                save(dict(version=2, public_events=[event], story_acks=[]))
                restarted = self.client(root, directory)
                restarted["es_ai_delivery_flush"]()
                restarted["es_ai_run_async"].assert_not_called()
                with open(env["es_ai_delivery_path"]()) as stream:
                    self.assertEqual(json.load(stream)["version"], 2)

    def test_server_pending_survives_restart_and_failed_save(self):
        for root in existing_paths((DEV, WORKSHOP)):
            fixture = StoryTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            mod = module(root)
            manager = fixture.manager(mod)
            fixture.offer(manager)
            key = manager.direct_request(fixture.token(manager), "yes", ["sl"], "un")
            ack = manager.direct_delivery(key, "sl", "un", "yes", dict(status="active"), "Agreed")
            restarted = mod.StoryManager(manager.path)
            with patch.object(mod.os, "replace", side_effect=OSError("disk full")):
                self.assertEqual(restarted.acknowledge_direct([ack]), [])
            self.assertIn(key, restarted.pending_direct)
            results = []
            threads = [threading.Thread(target=lambda: results.append(restarted.acknowledge_direct([ack]))) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(restarted.state["status"], "active")
            again = mod.StoryManager(manager.path)
            self.assertEqual(again.acknowledge_direct([ack]), [ack])
            self.assertEqual(again.prepare(dict(enabled=True), ["sl", "un"])["version"], restarted.state["version"])

    def test_flush_endpoint_has_no_model_call_and_rejects_bad_payload(self):
        for root in existing_paths((DEV, WORKSHOP)):
            with open(os.path.join(root, "main.py"), encoding="utf-8-sig") as stream:
                tree = ast.parse(stream.read())
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "scene_flush")
            env = dict(json=json)
            memory = types.SimpleNamespace(ingest=Mock(return_value=["event"]))
            stories = types.SimpleNamespace(acknowledge_direct=Mock(return_value=[]))
            with patch.dict(sys.modules, scene_memory=memory, story_events=stories):
                exec(compile(ast.Module(body=[node], type_ignores=[]), "flush", "exec"), env)
                self.assertFalse(env["scene_flush"](dict(public_events=[{}] * 41))["ok"])
                memory.ingest.assert_not_called()
                self.assertEqual(env["scene_flush"]({}), dict(ok=True, public_event_ids=["event"], story_acks=[]))

    def test_exchange_and_exit_hooks(self):
        for root in ROOTS:
            for filename, labels in (("es_ai_chat.rpy", ("es_ai_leave:", "es_ai_leave_chat:")),
                                     ("es_ai_overlay.rpy", ("es_ai_overlay_close:",))):
                with open(os.path.join(root, filename), encoding="utf-8-sig") as stream:
                    source = stream.read()
                for label in labels:
                    self.assertIn("label " + label + "\n    $ es_ai_delivery_flush()", source)
                self.assertIn("$ es_ai_delivery_flush()", source)


if __name__ == "__main__":
    unittest.main()
