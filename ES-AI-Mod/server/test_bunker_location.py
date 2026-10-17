"""Exercise both bunker installations offline, without config/history/API I/O."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import builtins
import json
from pathlib import Path
import re
import sys
import textwrap
import types
import unittest
from unittest.mock import patch

from test_cameo_variety import cameo_environment


DEV = Path(__file__).resolve().parents[1]
WORKSHOP = Path(WORKSHOP_ROOT)
COPIES = ((DEV / "mod", DEV / "server"),) + tuple((root, root / "server") for root in existing_paths((WORKSHOP,)))


def load_selected(path, names, env=None, renpy=False):
    source = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:] if renpy else [source]
    nodes = []
    for block in blocks:
        if renpy:
            block = re.split(r"^\S", block, maxsplit=1, flags=re.M)[0]
        for node in ast.parse(textwrap.dedent(block)).body:
            if (isinstance(node, ast.FunctionDef) and node.name in names) or (
                    isinstance(node, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id in names for t in node.targets)):
                nodes.append(node)
    env = {} if env is None else env
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
    return env


def locations(client):
    env = load_selected(client / "es_ai_cameo.rpy", {"es_ai_clothing_cover_choice"}, {"unicode": str}, renpy=True)
    return load_selected(client / "es_ai_locations.rpy", {
        "ES_AI_LOCATIONS", "ES_AI_LOCATION_INDEX", "ES_AI_MAP", "ES_AI_LOC_ALIASES",
        "ES_AI_MOVE_WORDS", "es_ai_location_id", "es_ai_location_from_dialog",
        "es_ai_loc_bg", "es_ai_neighbors_text", "es_ai_location_context", "es_ai_location",
        "es_ai_apply_actions"}, env, renpy=True)


class BunkerLocationTests(unittest.TestCase):
    def test_separate_background_route_and_timeless_clock(self):
        for client, server in COPIES:
            with self.subTest(client=str(client)):
                env = locations(client)
                index = env["ES_AI_LOCATION_INDEX"]
                bunker = index["bunker"]
                self.assertEqual(bunker["name"], "Бомбоубежище")
                self.assertEqual(bunker["bgs"], ["bg int_catacombs_living"])
                self.assertEqual(index["catacombs"]["bgs"], ["bg int_catacombs_entrance"])
                self.assertEqual(len(index), len(env["ES_AI_LOCATIONS"]))
                self.assertIsNone(bunker["dress"])
                self.assertFalse(bunker.get("romantic"))
                self.assertNotIn("time_bgs", bunker)
                routes = env["ES_AI_MAP"]
                self.assertEqual(routes["bunker"], ["catacombs"])
                self.assertEqual(routes["catacombs"], ["old_building_inside", "bunker", "mine_descent"])
                self.assertEqual(routes["old_building_inside"], ["old_building", "catacombs"])
                self.assertEqual(routes["mine_descent"], ["catacombs", "mine"])
                self.assertNotIn("bunker", routes["old_building"])
                self.assertNotIn("bunker", routes["mine"])
                for neighbor in routes["catacombs"]:
                    self.assertIn("catacombs", routes[neighbor])
                env.update(renpy=types.SimpleNamespace(has_image=lambda bg: True),
                           ES_AI_LOC_CUR=["catacombs"])
                self.assertIn("Бомбоубежище", env["es_ai_neighbors_text"]())
                env["ES_AI_LOC_CUR"][0] = "bunker"
                self.assertEqual(env["es_ai_neighbors_text"](), "Катакомбы")
                self.assertIn("бомбоубежища", env["es_ai_location_context"]())
                for phase in ("morning", "day", "sunset", "night"):
                    env["ES_AI_TIME"] = [phase]
                    self.assertEqual(env["es_ai_loc_bg"](bunker), "bg int_catacombs_living")

    def test_client_and_server_aliases_and_canonical_ids(self):
        for client, server in COPIES:
            with self.subTest(client=str(client)):
                env = locations(client)
                backend = load_selected(server / "main.py", {
                    "_LOCATION_ALIASES", "normalize_location", "detect_location_in_text"}, {"re": re})
                for value in ("bunker", "БОМБОУБЕЖИЩЕ", "убежище", "бункер", "bomb shelter",
                              "к бомбоубежищу", "из убежища", "в бункере",
                              "бомбоубежище под старым корпусом", "бункер в катакомбах"):
                    self.assertEqual(env["es_ai_location_id"](value), "bunker", value)
                    self.assertEqual(backend["normalize_location"](value), "bunker", value)
                    self.assertEqual(backend["detect_location_in_text"](value), "bunker", value)
                    self.assertEqual(env["es_ai_location_from_dialog"]("пойдём в " + value, ""), "bunker")
                for value in ("бункерный", "суперубежище", "bunkering", "shelter", "убеж", "бомбо"):
                    self.assertNotEqual(env["es_ai_location_id"](value), "bunker", value)
                    self.assertNotEqual(backend["normalize_location"](value), "bunker", value)
                    self.assertNotEqual(backend["detect_location_in_text"](value), "bunker", value)
                for loc_id in env["ES_AI_LOCATION_INDEX"]:
                    self.assertEqual(backend["normalize_location"](loc_id), loc_id)
                self.assertIsNone(env["es_ai_location_from_dialog"]("где бомбоубежище?", ""))
                arrivals = []
                env.update(ES_AI_LOC_CUR=["catacombs"], ES_AI_LOC_LAST_CHAR=["un"],
                           ES_AI_LOC_LAST_EMO=[None], ES_AI_CLOCK={"enabled": False},
                           ES_AI_CHARS=[("un", "Лена", "")],
                           _es_ai_cameo_builtins=builtins, basestring=str,
                           es_ai_log=lambda *a: None, es_ai_cameo_on=lambda: False,
                           es_ai_dress_from_context=lambda *a: None,
                           es_ai_set_location=lambda loc, *a, **k: arrivals.append(loc))
                env["es_ai_apply_actions"]({"goto": "bunker"})
                self.assertEqual(arrivals, ["bunker"])

    def test_snapshot_capacity_and_server_cameo_acceptance(self):
        for client, server in COPIES:
            with self.subTest(client=str(client)):
                env = cameo_environment(client / "es_ai_cameo.rpy")
                env["ES_AI_LOCATION_INDEX"] = locations(client)["ES_AI_LOCATION_INDEX"]
                env["ES_AI_LOC_CUR"][0] = "bunker"
                self.assertEqual(env["ES_AI_CAMEO_BY_LOC"]["bunker"], env["ES_AI_CAMEO_BY_LOC"]["catacombs"])
                self.assertNotIn("bunker", env["ES_AI_LOC_OWNERS"])
                snapshot = env["es_ai_scene_snapshot"]("uv")
                self.assertEqual(snapshot["location_id"], "bunker")
                self.assertEqual(set(snapshot["available"]), {"cs", "sh"})
                self.assertEqual(snapshot["destination_capacity"]["bunker"], 2)
                self.assertIn("bunker", snapshot["destination_group_sizes"])
                self.assertEqual(set(snapshot["destinations"]["bunker"]), {"cs", "sh"})
                for _ in range(20):
                    env["ES_AI_CAMEO_CD"][0] = 0
                    self.assertTrue(set(env["es_ai_maybe_cameo"]("uv", False)) <= {"cs", "sh"})
                backend = load_selected(server / "main.py", {
                    "_LOCATION_ALIASES", "_ACTION_GOTO_RE", "_ACTION_TIME_RE", "_ACTION_DRESS_RE",
                    "_ACTION_CAMEO_RE", "normalize_location", "detect_location_in_text",
                    "parse_action_tags", "scene_encounter", "scene_prompt", "resolve_direct_address",
                    "parse_cameo_tags"}, {"re": re, "json": json})
                store = types.ModuleType("characters_store")
                store.characters = lambda: [{"id": cid, "name": name} for cid, name, _ in env["ES_AI_CHARS"]]
                with patch.dict(sys.modules, {"characters_store": store}):
                    current = dict(snapshot, location_id="catacombs")
                    cleaned, goto, _, _ = backend["parse_action_tags"]("Идём. [action:goto:bunker]")
                    self.assertEqual(cleaned, "Идём.")
                    self.assertEqual(backend["normalize_location"](goto), "bunker")
                    self.assertEqual(backend["scene_encounter"](current, goto)["capacity"], 2)
                    self.assertEqual(backend["resolve_direct_address"](
                        "Шурик!", current, "uv", "catacombs", goto), ["sh"])
                    self.assertEqual(backend["parse_cameo_tags"](
                        "Hi [action:cameo:sh,unknown]", current, "uv", goto, "catacombs"), ("Hi", ["sh"]))
                    self.assertIn('"bunker"', backend["scene_prompt"](current, "uv"))

    def test_map_coordinates_and_bilingual_label(self):
        for client, server in COPIES:
            with self.subTest(client=str(client)):
                pins = load_selected(client / "es_ai_map.rpy", {"ES_AI_MAP_PIN"}, renpy=True)["ES_AI_MAP_PIN"]
                window = load_selected(server / "settings_window.py", {"ES_MAP_PIN"})["ES_MAP_PIN"]
                self.assertEqual(pins["bunker"], window["bunker"])
                self.assertNotIn(pins["bunker"], [pos for key, pos in pins.items() if key != "bunker"])
                x, y = pins["bunker"]
                self.assertTrue(0 < x < 1178 and 0 < y < 663)
                self.assertLess(abs(x - pins["catacombs"][0]) + abs(y - pins["catacombs"][1]), 80)
                i18n = load_selected(server / "ui_i18n.py", {"EN", "tr"})
                self.assertEqual(i18n["tr"]("Бомбоубежище", "ru"), "Бомбоубежище")
                self.assertEqual(i18n["tr"]("Бомбоубежище", "en"), "Bomb Shelter")
                source = (server / "settings_window.py").read_text(encoding="utf-8-sig")
                self.assertIn('tr(lname)', source)

    def test_character_rules_advertise_bunker(self):
        for client, server in COPIES:
            with self.subTest(server=str(server)):
                rules = load_selected(server / "characters_store.py", {"reply_rules", "_EMOTIONS"})
                self.assertIn("bunker (бомбоубежище)", rules["reply_rules"]({"id": "un", "age": 18}))


if __name__ == "__main__":
    unittest.main()
