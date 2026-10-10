"""Offline variety regressions for both installations, without API or config I/O."""
import ast
import builtins
import json
from pathlib import Path
import random
import re
import sys
import textwrap
import types
import unittest
from unittest.mock import patch


DEV = Path(__file__).resolve().parents[1]
WORKSHOP = Path(r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310")
CAMPERS = ["us", "mi", "dv", "sl", "un", "el", "sh", "mz", "mt", "cs"]


def cameo_environment(path):
    source = path.read_text(encoding="utf-8-sig")
    nodes = []
    for block in re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:]:
        for node in ast.parse(textwrap.dedent(block)).body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                    "es_ai_maybe_cameo", "es_ai_scene_snapshot", "es_ai_cameo_capacity",
                    "es_ai_cameo_group_size"}:
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in {
                        "ES_AI_CAMEO_BY_LOC", "ES_AI_LOC_OWNERS", "ES_AI_CAMEO_PAIRS"}
                    for t in node.targets):
                nodes.append(node)
    env = {"_es_random": random.Random(42), "_es_ai_cameo_builtins": builtins,
           "ES_AI_LOC_CUR": ["beach"], "ES_AI_SHOWN": [{"id": "uv"}],
           "ES_AI_CHARS": [(cid, cid, "") for cid in CAMPERS + ["uv"]],
           "ES_AI_CAMEO_CD": [0], "ES_AI_CAMEO_COOLDOWN": 5, "ES_AI_CAMEO_NEARBY": {},
           "ES_AI_CAMEO_P_COMPANION": 1,
           "es_ai_cameo_on": lambda: True,
           "es_ai_read_cameo_settings": lambda: {"cameo_freq": 100, "cameo_max_extra": 2},
           "es_ai_cameo_chance": lambda *args: 1,
           "es_ai_recent_snapshot": lambda n: []}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
    env["ES_AI_LOCATION_INDEX"] = dict.fromkeys(list(env["ES_AI_CAMEO_BY_LOC"]) + ["bus_stop"], {})
    return env


class CameoVarietyTests(unittest.TestCase):
    def test_destination_free_slots_keep_travelers_present(self):
        for path in (DEV / "server/main.py", WORKSHOP / "server/main.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in {"scene_encounter", "parse_cameo_tags", "resolve_direct_address"}]
            env = {"re": re, "normalize_location": lambda value: value,
                   "_ACTION_CAMEO_RE": re.compile(r"\[action:cameo:([^\]]+)\]")}
            store = types.ModuleType("characters_store")
            store.characters = lambda: [{"id": cid, "name": cid} for cid in CAMPERS]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
            scene = {"enabled": True, "location_id": "beach", "capacity": 0,
                     "present": ["sl", "dv", "us", "el", "sh", "mi", "un"],
                     "traveling": ["dv", "us", "el", "sh", "mi", "un"], "travel_all": True,
                     "invitable": CAMPERS, "destination_capacity": {"mt_room": 2},
                     "destination_group_sizes": {"mt_room": 0}, "destinations": {"mt_room": ["mt"]}}
            normalized = env["scene_encounter"](scene, "mt_room")
            self.assertEqual(normalized["present"], scene["traveling"])
            self.assertEqual(normalized["capacity"], 0)
            self.assertEqual(normalized["group_size"], 0)
            with patch.dict(sys.modules, {"characters_store": store}):
                self.assertEqual(env["parse_cameo_tags"](
                    "Hi [action:cameo:dv,mt]", scene, "sl", "mt_room", "beach"), ("Hi", ["dv"]))
                self.assertEqual(env["resolve_direct_address"](
                    "Алиса, ты идешь?", scene, "sl", "beach", "mt_room"), ["dv"])

    def test_both_cameos(self):
        for path in (DEV / "mod/es_ai_cameo.rpy", WORKSHOP / "es_ai_cameo.rpy"):
            with self.subTest(path=str(path)):
                env = cameo_environment(path)
                pools = env["ES_AI_CAMEO_BY_LOC"]
                original = {loc: ids[:] for loc, ids in pools.items()}
                for loc in ("beach", "bathhouse"):
                    self.assertEqual(pools[loc], CAMPERS)
                    env["ES_AI_LOC_CUR"][0] = loc
                    snapshots = [env["es_ai_scene_snapshot"]("uv") for _ in range(20)]
                    for key in ("available", "invitable"):
                        self.assertGreater(len({tuple(s[key]) for s in snapshots}), 1)
                        self.assertTrue(all(set(s[key]) == set(CAMPERS) for s in snapshots))
                    self.assertGreater(len({tuple(s["destinations"][loc]) for s in snapshots}), 1)
                    for snapshot in snapshots:
                        self.assertEqual(snapshot["present"], ["uv"])
                        self.assertEqual(snapshot["capacity"], 2)
                        for destination, ids in snapshot["destinations"].items():
                            self.assertEqual(set(ids), set(pools[destination]) - {"uv"})
                    seen = set()
                    for _ in range(100):
                        env["ES_AI_CAMEO_CD"][0] = 0
                        result = env["es_ai_maybe_cameo"]("uv", False)
                        self.assertIn(len(set(result)), (1, 2))
                        self.assertTrue(set(result) <= set(CAMPERS))
                        seen.update(result)
                    self.assertEqual(seen, set(CAMPERS))
                self.assertEqual(pools, original, "Snapshot must not mutate location pools")

                # Force the first arrival, but let all its valid mates compete randomly.
                rng = env["_es_random"]
                choose = rng.choice
                with patch.object(rng, "choice", side_effect=lambda ids: "dv" if "dv" in ids else choose(ids)):
                    mates = set()
                    for _ in range(100):
                        env["ES_AI_CAMEO_CD"][0] = 0
                        result = env["es_ai_maybe_cameo"]("uv", False)
                        self.assertEqual(result[0], "dv")
                        if len(result) > 1:
                            mates.add(result[1])
                    self.assertEqual(mates, {"us", "un"})
                env["ES_AI_SHOWN"] = [{"id": "uv"}, {"id": "us"}]
                env["ES_AI_CAMEO_CD"][0] = 0
                result = env["es_ai_maybe_cameo"]("uv", False)
                self.assertEqual(len(result), 1)
                self.assertNotIn("us", result)
                self.assertEqual(env["es_ai_maybe_cameo"]("uv", False), [])
                env["ES_AI_CAMEO_CD"][0] = 0
                env["ES_AI_SHOWN"] = [{"id": cid} for cid in ["uv"] + CAMPERS[:6]]
                with patch.object(env["_es_random"], "random", side_effect=AssertionError("Full scene sampled arrival")):
                    self.assertEqual(env["es_ai_maybe_cameo"]("uv", False), [])
                self.assertEqual(len(env["ES_AI_SHOWN"]), 7)

    def test_both_prompts(self):
        for path in (DEV / "server/main.py", WORKSHOP / "server/main.py"):
            with self.subTest(path=str(path)):
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name in {"scene_prompt", "scene_encounter"}]
                env = {"json": json}
                store = types.ModuleType("characters_store")
                store.characters = lambda: [{"id": cid, "name": cid} for cid in CAMPERS]
                with patch.dict(sys.modules, {"characters_store": store}):
                    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
                    prompt = env["scene_prompt"]({"available": CAMPERS, "invitable": CAMPERS,
                                                  "enabled": True, "capacity": 2}, "mt")
                self.assertNotIn("[action:cameo:dv,sl]", prompt)
                self.assertIn("[action:cameo:<id>,<id>]", prompt)
                self.assertIn("actual character ID from the supplied roster", prompt)
                self.assertIn("do not always pick the same pair", prompt)
                self.assertIn("Keep explicitly named identities exact", prompt)
                intent = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "resolve_cameo_intent")
                instruction = next(n.value for n in ast.walk(intent) if isinstance(n, ast.Constant)
                                   and isinstance(n.value, str) and n.value.startswith("Resolve only"))
                self.assertIn("not always the same pair", instruction)
                self.assertIn("Keep explicitly named identities exact", instruction)


if __name__ == "__main__":
    unittest.main()
