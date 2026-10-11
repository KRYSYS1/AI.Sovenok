# -*- coding: utf-8 -*-
"""Offline integration of the accepted location audit in both installations."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import re
import struct
import types
import unittest
import zlib
from pathlib import Path

from test_bunker_location import COPIES, load_selected, locations
from test_cameo_variety import cameo_environment


NEW = {
    "old_building_inside": ("Старый корпус внутри", "Old Building Interior", "int_old_building_night"),
    "library_ext": ("У библиотеки", "Outside the Library", "ext_library_day"),
    "mine_descent": ("Спуск в шахту", "Mine Descent", "int_catacombs_hole"),
    "mine_room": ("Комната в шахте", "Mine Room", "int_mine_room"),
    "mine_exit": ("Выход из шахты", "Mine Exit", "int_mine_exit_night_light"),
    "mine_crossroad": ("Развилка шахты", "Mine Crossroad", "int_mine_crossroad"),
    "mine_coalface": ("Забой шахты", "Mine Coalface", "int_mine_coalface"),
    "mine_halt": ("Привал в шахте", "Mine Rest Stop", "int_mine_halt"),
    "bus_410": ("Автобус 410", "Bus 410", "int_liaz"),
}
EDGES = {
    "old_building_inside": ["old_building", "catacombs"],
    "library_ext": ["square", "library"],
    "mine_descent": ["catacombs", "mine"],
    "mine_crossroad": ["mine", "mine_room", "mine_coalface", "mine_halt", "mine_exit"],
    "mine_room": ["mine_crossroad"], "mine_coalface": ["mine_crossroad"],
    "mine_halt": ["mine_crossroad"], "mine_exit": ["mine_crossroad", "square"],
    "bus_410": ["bus_stop"],
}


class LocationSublocationTests(unittest.TestCase):
    def test_graph_reachability_and_reciprocal_new_edges(self):
        for client, _ in COPIES:
            with self.subTest(client=str(client)):
                env = locations(client)
                index, graph = env["ES_AI_LOCATION_INDEX"], env["ES_AI_MAP"]
                self.assertEqual(len(index), 49)
                self.assertEqual(len(index), len(env["ES_AI_LOCATIONS"]))
                self.assertEqual(set(index), set(graph))
                for loc, neighbors in graph.items():
                    self.assertEqual(len(neighbors), len(set(neighbors)))
                    self.assertTrue(set(neighbors) <= set(index), loc)
                reached, pending = set(), ["square"]
                while pending:
                    loc = pending.pop()
                    if loc not in reached:
                        reached.add(loc)
                        pending.extend(graph[loc])
                self.assertEqual(reached, set(index))
                for loc, neighbors in EDGES.items():
                    self.assertEqual(graph[loc], neighbors)
                    for neighbor in neighbors:
                        self.assertIn(loc, graph[neighbor])
                self.assertEqual(graph["catacombs"], ["old_building_inside", "bunker", "mine_descent"])
                self.assertEqual(graph["mine"], ["mine_descent", "mine_crossroad"])
                self.assertEqual(graph["library"], ["library_ext"])
                self.assertNotIn("catacombs", graph["old_building"])
                self.assertNotIn("bus_410", graph["camp_gate"])
                self.assertEqual(graph["bunker"], ["catacombs"])

    def test_separate_backgrounds_phases_and_same_place_fallbacks(self):
        for client, _ in COPIES:
            env = locations(client)
            index = env["ES_AI_LOCATION_INDEX"]
            self.assertEqual(index["old_building"]["bgs"], ["bg ext_old_building_night"])
            self.assertEqual(index["library"]["bgs"], ["bg int_library_day"])
            self.assertEqual(index["mine"]["bgs"], ["bg int_mine"])
            available = {"bg " + row[2] for row in NEW.values()} | {"bg ext_library_night"}
            env["renpy"] = types.SimpleNamespace(has_image=lambda bg: bg in available)
            for loc, (name, _, tag) in NEW.items():
                self.assertEqual(index[loc]["name"], name)
                self.assertIsNone(index[loc]["dress"])
                self.assertFalse(index[loc].get("romantic"))
                self.assertTrue(index[loc]["context_only"])
                for phase in ("morning", "day", "sunset", "night"):
                    env["ES_AI_TIME"] = [phase]
                    expected = "bg ext_library_night" if loc == "library_ext" and phase in ("sunset", "night") else "bg " + tag
                    self.assertEqual(env["es_ai_loc_bg"](index[loc]), expected)
            exit_tags = ["bg int_mine_exit_night_light", "bg int_mine_exit_night_nolight", "bg int_mine_exit_night_torch"]
            self.assertEqual(index["mine_exit"]["bgs"], exit_tags)
            for offset, expected in enumerate(exit_tags):
                env["renpy"].has_image = lambda bg, offset=offset: bg in exit_tags[offset:]
                for phase in ("morning", "day", "sunset", "night"):
                    env["ES_AI_TIME"] = [phase]
                    self.assertEqual(env["es_ai_loc_bg"](index["mine_exit"]), expected)
            env["renpy"].has_image = lambda bg: False
            self.assertEqual(env["es_ai_loc_bg"](index["mine"]), "bg int_mine")
            env["renpy"].has_image = lambda bg: bg == "bg ext_library_day"
            self.assertEqual(env["es_ai_loc_bg"](index["library_ext"]), "bg ext_library_day")

    def test_registered_original_background_tags(self):
        path = Path(GAME_ROOT) / "game/resources.rpyc"
        if not path.is_file():
            self.skipTest("Stock resources.rpyc unavailable")
        data = path.read_bytes()
        if data.startswith(b"RENPY RPC2"):
            slot, offset, length = struct.unpack("<III", data[10:22])
            self.assertEqual(slot, 1)
            data = data[offset:offset + length]
        raw = zlib.decompress(data)
        # Read pickle string opcodes without executing the game's serialized AST.
        tokens = set()
        for match in re.finditer(b"(?:U(.)|[XT](....))", raw, re.S):
            length = match.group(1)[0] if match.group(1) else struct.unpack("<I", match.group(2))[0]
            tokens.add(raw[match.end():match.end() + length])
        self.assertIn(b"bg", tokens)
        for client, _ in COPIES:
            index = locations(client)["ES_AI_LOCATION_INDEX"]
            for loc in NEW:
                item = index[loc]
                tags = item["bgs"] + sum(item.get("time_bgs", {}).values(), [])
                for tag in tags:
                    self.assertIn(tag.split(" ", 1)[1].encode("ascii"), tokens, tag)

    def test_alias_specificity_canonical_ids_and_movement_gate(self):
        for client, server in COPIES:
            env = locations(client)
            backend = load_selected(server / "main.py", {
                "_LOCATION_ALIASES", "normalize_location", "detect_location_in_text"}, {"re": re})
            self.assertEqual({loc for loc, _ in backend["_LOCATION_ALIASES"]}, set(env["ES_AI_LOCATION_INDEX"]))
            for loc in env["ES_AI_LOCATION_INDEX"]:
                self.assertEqual(env["es_ai_location_id"](loc), loc)
                self.assertEqual(backend["normalize_location"](loc), loc)
                self.assertEqual(backend["detect_location_in_text"](loc), loc)
            for loc, aliases in env["ES_AI_LOC_ALIASES"]:
                if loc not in NEW:
                    continue
                for alias in aliases:
                    text = alias.upper()
                    self.assertEqual(env["es_ai_location_id"](text), loc, text)
                    self.assertEqual(backend["normalize_location"](text), loc, text)
                    self.assertEqual(backend["detect_location_in_text"](text), loc, text)
                    self.assertEqual(env["es_ai_location_from_dialog"]("Пойдём к " + alias, ""), loc)
                    self.assertIsNone(env["es_ai_location_from_dialog"](alias, ""))
                    self.assertIsNone(env["es_ai_location_from_dialog"]("Не пойдём к " + alias, "Идём к " + alias))
                    self.assertIsNone(env["es_ai_location_from_dialog"]("Где " + alias + "?", "Пойдём к " + alias))
            self.assertEqual(env["es_ai_location_id"]("комната в шахте под старым корпусом"), "mine_room")

    def test_map_bounds_spacing_all_ids_and_translations(self):
        for client, server in COPIES:
            index = locations(client)["ES_AI_LOCATION_INDEX"]
            pins = load_selected(client / "es_ai_map.rpy", {"ES_AI_MAP_PIN"}, renpy=True)["ES_AI_MAP_PIN"]
            window = load_selected(server / "settings_window.py", {"ES_MAP_PIN"})["ES_MAP_PIN"]
            self.assertEqual(pins, window)
            self.assertEqual(set(pins), set(index))
            i18n = load_selected(server / "ui_i18n.py", {"EN", "tr"})
            for loc, (name, english, _) in NEW.items():
                x, y = pins[loc]
                self.assertTrue(11 <= x <= 1167 and 11 <= y <= 652)
                for other, (ox, oy) in pins.items():
                    if other != loc:
                        self.assertGreaterEqual((x - ox) ** 2 + (y - oy) ** 2, 22 ** 2, (loc, other))
                self.assertEqual(i18n["tr"](name, "ru"), name)
                self.assertEqual(i18n["tr"](name, "en"), english)

    def test_cameo_pools_snapshot_and_server_action_acceptance(self):
        parents = {"old_building_inside": "old_building", "library_ext": "library", "mine_descent": "catacombs", "bus_410": "road"}
        for client, server in COPIES:
            env = cameo_environment(client / "es_ai_cameo.rpy")
            env["ES_AI_LOCATION_INDEX"] = locations(client)["ES_AI_LOCATION_INDEX"]
            backend = load_selected(server / "main.py", {
                "_LOCATION_ALIASES", "_ACTION_GOTO_RE", "_ACTION_TIME_RE", "_ACTION_DRESS_RE",
                "normalize_location", "parse_action_tags", "scene_encounter"}, {"re": re})
            rules = load_selected(server / "characters_store.py", {"reply_rules", "_EMOTIONS"})["reply_rules"]({"id": "un", "age": 18})
            for loc in NEW:
                self.assertIn(loc + " (", rules)
                self.assertNotIn(loc, env["ES_AI_LOC_OWNERS"])
                self.assertEqual(env["ES_AI_CAMEO_BY_LOC"][loc], env["ES_AI_CAMEO_BY_LOC"][parents.get(loc, "mine")])
                env["ES_AI_LOC_CUR"][0] = loc
                snapshot = env["es_ai_scene_snapshot"]("un")
                self.assertEqual(snapshot["location_id"], loc)
                self.assertEqual(snapshot["destination_capacity"][loc], 2)
                self.assertIn(loc, snapshot["destination_group_sizes"])
                self.assertEqual(set(snapshot["destinations"][loc]),
                                 set(env["ES_AI_CAMEO_BY_LOC"][loc]) - set(snapshot["present"]) - {"un"})
                self.assertEqual(env["es_ai_cameo_capacity"](loc, {"cameo_max_extra": 6}), 3)
                _, goto, _, _ = backend["parse_action_tags"]("Идём [action:goto:" + loc + "]")
                self.assertEqual(backend["normalize_location"](goto), loc)
                self.assertEqual(backend["scene_encounter"](snapshot, goto)["capacity"], 2)


if __name__ == "__main__":
    unittest.main()
