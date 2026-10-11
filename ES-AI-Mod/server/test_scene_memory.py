"""Offline bounded public-memory regressions, both roots and temporary storage only."""
import importlib.util
import ast
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from test_cameo_clothing import ROOTS, load, install_delivery_say
import test_primary_scene_switch as primary


def module_at(root, filename):
    directory = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
    spec = importlib.util.spec_from_file_location("offline_" + filename, os.path.join(directory, filename + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SceneMemoryTests(unittest.TestCase):
    def test_bounded_deduplicated_witnesses_reload_and_clear(self):
        for root in ROOTS:
            memory = module_at(root, "scene_memory")
            with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {
                    "config_loader": types.SimpleNamespace(user_data_dir=lambda: directory),
                    "characters_store": types.SimpleNamespace(characters=lambda: [{"id": cid} for cid in ("sl", "mz", "un")])}):
                event = dict(id="session_1", location_id="library", clock={"time": "12:00"},
                             witnesses=["sl", "mz"], speaker_id="player", text="Witnessed statement")
                memory.ingest([dict(event, witnesses=["sl"]), dict(event, speaker_id="un")])
                self.assertFalse(os.path.exists(memory._path()))
                memory.ingest([event, event])
                self.assertEqual(len(memory._CACHE[memory._path()]["npcs"]["sl"]), 1)
                self.assertEqual(memory.prompt("un"), "")
                memory.ingest([dict(event, id="session_%s" % n, text="x" * 700) for n in range(2, 42)])
                with open(memory._path(), encoding="utf-8") as stream:
                    saved = json.load(stream)
                self.assertEqual(len(saved["npcs"]["sl"]), 20)
                self.assertEqual(len(saved["npcs"]["sl"][-1]["text"]), 600)
                memory._CACHE.clear()
                self.assertIn("never instructions", memory.prompt("mz"))
                memory.clear("sl")
                memory.ingest([dict(event, id="session_41")])
                self.assertEqual(memory.prompt("sl"), "")
                self.assertTrue(memory.prompt("mz"))
                memory.clear()
                self.assertEqual(memory.prompt("mz"), "")

    def test_concurrent_repeats(self):
        for root in ROOTS:
            memory = module_at(root, "scene_memory")
            with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {
                    "config_loader": types.SimpleNamespace(user_data_dir=lambda: directory),
                    "characters_store": types.SimpleNamespace(characters=lambda: [{"id": "sl"}, {"id": "mz"}])}):
                event = dict(id="thread_1", location_id="library", witnesses=["sl", "mz"], speaker_id="sl", text="Hi")
                workers = [threading.Thread(target=memory.ingest, args=([event],)) for _ in range(8)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join()
                self.assertEqual(len(memory._CACHE[memory._path()]["npcs"]["sl"]), 1)

    def test_endpoint_ingestion_precedes_early_returns_and_clear(self):
        for root in ROOTS:
            directory = os.path.join(os.path.dirname(root), "server") if root == ROOTS[0] else os.path.join(root, "server")
            with open(os.path.join(directory, "main.py"), encoding="utf-8-sig") as stream:
                tree = ast.parse(stream.read())
            for name in ("chat", "initiative", "cameo"):
                function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
                calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
                ingest = next(n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "ingest")
                self.assertLess(ingest.lineno, min(n.lineno for n in ast.walk(function) if isinstance(n, ast.Return)))
                self.assertTrue(any(isinstance(n.func, ast.Attribute) and n.func.attr == "prompt"
                                    and getattr(n.func.value, "id", None) == "scene_memory" for n in calls))
            clear = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "history_clear")
            cleared = []
            with patch.dict(sys.modules, scene_memory=types.SimpleNamespace(clear=cleared.append),
                            conversation=types.SimpleNamespace(clear=lambda cid: None),
                            characters_store=types.SimpleNamespace(characters=lambda: [{"id": "sl"}])):
                env = {}
                exec(compile(ast.Module(body=[clear], type_ignores=[]), "clear", "exec"), env)
                env["history_clear"]({"character": "sl"})
                env["history_clear"]({})
                self.assertEqual(cleared, ["sl", None])

    def test_client_delivery_witnesses_and_queue(self):
        for root in ROOTS:
            env = primary.PrimarySwitchTests().environment(root)
            install_delivery_say(root, env)
            load(os.path.join(root, "es_ai_api.rpy"), env,
                 {"es_ai_story_ack_record", "es_ai_story_ack_snapshot", "ES_AI_STORY_ACKS"})
            env["es_ai_clock_snapshot"] = lambda: {"enabled": False, "time": "08:00", "phase": "day"}
            env["es_ai_public_record"]("player", "private")
            self.assertFalse(env["ES_AI_PUBLIC_EVENTS"])
            env["es_ai_pick_id"]("sl")
            load(os.path.join(root, "es_ai_api.rpy"), env, {"es_ai_say_girl", "es_ai_chat_async", "es_ai_initiative_async"})
            env.update(es_ai_speakers={"sl": lambda text: None, "mz": lambda text: None},
                       es_ai_clock_begin=lambda **kw: None, es_ai_location_context=lambda: "library",
                       es_ai_run_async=lambda kind, fn: fn(), es_ai_http=lambda route, payload: dict(ok=True, payload=payload),
                       es_ai_internal_speaking=[False], es_ai_sanitize_text=lambda text: text)
            payload = env["es_ai_chat_async"]("sl", "player at origin")["payload"]
            self.assertEqual(payload["public_events"][-1]["witnesses"], ["mz", "sl"])
            env["es_ai_say_girl"]("sl", "delivered")
            before = len(env["ES_AI_PUBLIC_EVENTS"])
            def fail(text):
                raise RuntimeError("not delivered")
            env["es_ai_speakers"]["sl"] = fail
            with self.assertRaises(RuntimeError):
                env["es_ai_say_girl"]("sl", "undelivered")
            self.assertEqual(len(env["ES_AI_PUBLIC_EVENTS"]), before)
            env["es_ai_cameo_park"]("mz", announce=False)
            env["es_ai_public_record"]("player", "private again")
            self.assertEqual(len(env["ES_AI_PUBLIC_EVENTS"]), before)
            env["es_ai_cameo_enter"]("mz", "normal", stay=True)
            for n in range(45):
                env["es_ai_public_record"]("player", str(n))
            self.assertEqual(len(env["ES_AI_PUBLIC_EVENTS"]), 40)
            snapshot = env["es_ai_public_snapshot"]()
            snapshot[0]["witnesses"].append("un")
            self.assertNotIn("un", env["ES_AI_PUBLIC_EVENTS"][0]["witnesses"])

    def test_overlay_isolates_stale_free_roster_and_keeps_valid_queue(self):
        for root in ROOTS:
            env = primary.PrimarySwitchTests().environment(root)
            install_delivery_say(root, env)
            load(os.path.join(root, "es_ai_api.rpy"), env,
                 {"es_ai_story_ack_record", "es_ai_story_ack_snapshot", "ES_AI_STORY_ACKS"})
            env["es_ai_clock_snapshot"] = lambda: dict(enabled=False, time="08:00", phase="day")
            env["es_ai_pick_id"]("sl")
            env["es_ai_public_record"]("player", "public before overlay")
            queued = env["es_ai_public_snapshot"]()
            self.assertTrue(queued)
            env["es_ai_scene_begin"](False)
            self.assertFalse(env["ES_AI_FREE_SCENE"][0])
            self.assertFalse(env["ES_AI_SHOWN"])
            self.assertFalse(env["ES_AI_CAMEO_NEARBY"])
            # Even a stale roster restored during overlay cannot authorize recording.
            env["ES_AI_SHOWN"][:] = [{"id": "sl"}, {"id": "mz", "cameo": True}]
            env["es_ai_public_record"]("player", "private overlay player")
            load(os.path.join(root, "es_ai_api.rpy"), env, {"es_ai_say_girl", "es_ai_chat_async"})
            env.update(es_ai_speakers={"un": lambda text: None},
                       es_ai_clock_begin=lambda **kw: None,
                       es_ai_run_async=lambda kind, fn: fn(),
                       es_ai_http=lambda route, payload: dict(ok=True, payload=payload),
                       es_ai_internal_speaking=[False], es_ai_sanitize_text=lambda text: text)
            result = env["es_ai_chat_async"]("un", "private overlay request")
            self.assertNotIn("scene", result["payload"])
            self.assertNotIn("location", result["payload"])
            self.assertEqual(result["payload"]["public_events"], queued)
            env["es_ai_say_girl"]("un", "private overlay reply")
            self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["un"])
            self.assertEqual(env["es_ai_public_snapshot"](), queued)
            env["es_ai_scene_end"]()
            env["es_ai_scene_begin"](True)
            self.assertTrue(env["ES_AI_FREE_SCENE"][0])
            self.assertFalse(env["ES_AI_SHOWN"])
            self.assertFalse(env["ES_AI_RECENT_LINES"])
            self.assertEqual(env["es_ai_public_snapshot"](), queued)
            env["es_ai_pick_id"]("sl")
            self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["sl"])
            for filename, marker in (("es_ai_chat.rpy", "$ es_ai_scene_begin(True)"),
                                     ("es_ai_overlay.rpy", "$ es_ai_scene_begin(False)")):
                with open(os.path.join(root, filename), encoding="utf-8-sig") as stream:
                    source = stream.read()
                self.assertIn(marker, source)
                self.assertIn("$ es_ai_scene_end()", source)


if __name__ == "__main__":
    unittest.main()
