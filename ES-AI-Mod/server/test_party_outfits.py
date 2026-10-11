# -*- coding: utf-8 -*-
"""Party clothing regressions, with real Python 2 client coverage."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import os
import re
import subprocess
import sys
import types
import unittest
import struct
import zlib
import io
import pickle
from unittest.mock import patch
import test_cameo_clothing as clothing
from test_cameo_clothing import ROOTS, DEV, WORKSHOP, load


class PartyTests(unittest.TestCase):
    def test_latest_live_request_and_reply(self):
        text = u"Славя, приоденьсе в платье, я собираюсь пойти с тобой на концерт."
        reply = u"Конечно, Колян, я надену платье — мне хочется выглядеть нарядно на нашем вечере. А ты уже знаешь, где будет концерт?"
        for root in ROOTS:
            for cid, name in (("sl", u"Славя"), ("mt", u"Ольга")):
                for command in (text.replace(u"Славя", name), name + u", приоденься в платье",
                                u"Надень платье"):
                    env = self.environment(root)
                    env["ES_AI_LOC_LAST_CHAR"][0] = cid
                    env["ES_AI_SHOWN"][:] = [{"id": cid, "emo": "normal"}]
                    env["ES_AI_DRESS"][0] = "cover"
                    env["es_ai_apply_actions"]({"dress": "dress", "reply": reply}, command)
                    self.assertEqual(env["ES_AI_DRESS"][0], "dress")
                    self.assertFalse(env["ES_AI_PARTY"][0])
                    self.assertEqual(env["es_ai_resolve_sprite"](cid, "normal", "dress"),
                                     cid + " normal dress")
                for command in (name + u", не приоденьсе в платье", u"Лена, приоденьсе в платье"):
                    env = self.environment(root)
                    env["ES_AI_LOC_LAST_CHAR"][0] = cid
                    env["ES_AI_SHOWN"][:] = [{"id": cid, "emo": "normal"}]
                    env["es_ai_apply_actions"]({"dress": "dress", "reply": reply}, command)
                    self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_live_concert_and_future_clothing_inputs(self):
        for root in ROOTS:
            for text in (u"пошли на концер к большой сцене - там уже все собрались",
                         u"идём на концерт", u"Лена, пошли к сцене на концерт"):
                env = self.environment(root)
                env["es_ai_apply_actions"]({"reply": "Yes"}, text)
                self.assertTrue(env["ES_AI_PARTY"][0])
                self.assertEqual(env["ES_AI_DRESS"][0], "dress")
                for g in env["ES_AI_SHOWN"][1:]:
                    self.assertEqual(g["dress"], "dress" if g["id"] in ("sl", "us") else None)
            env = self.environment(root)
            env["es_ai_apply_actions"]({}, u"пошли к тебе, ты переоденешься в платье")
            self.assertEqual(env["ES_AI_DRESS"][0], "dress")
            self.assertFalse(env["ES_AI_PARTY"][0])

    def environment(self, root):
        env = clothing.ClothingTests().environment(root)
        load(os.path.join(root, "es_ai.rpy"), env,
             {"es_ai_has_party_dress", "es_ai_resolve_sprite", "es_ai_fallback_emotion"})
        load(os.path.join(root, "es_ai_locations.rpy"), env)
        env["ES_AI_LOC_CUR"][0] = "square"
        env["ES_AI_LOC_LAST_CHAR"][0] = "un"
        env["ES_AI_CHARS"] = [(cid, cid, "") for cid in ("un", "sl", "us", "mt", "mi", "dv")]
        env["ES_AI_SHOWN"][:] = [{"id": "un", "emo": "normal"}] + [
            {"id": cid, "emo": "normal", "cameo": True} for cid in ("sl", "us", "mi", "dv")]
        images = {cid + " normal pioneer" for cid, _, _ in env["ES_AI_CHARS"]}
        images.update(cid + " normal dress" for cid in ("un", "sl", "us", "mt"))
        env["renpy"].has_image = lambda tag, exact=False: tag in images if exact else any(i.startswith(tag) for i in images)
        env["es_ai_refresh_girls"] = lambda: None
        env["es_ai_location_from_dialog"] = lambda *a: None
        env["es_ai_char_id"] = "un"
        env["es_ai_location"] = lambda: {"dress": None}
        return env

    def test_active_group_and_new_cameo(self):
        for root in ROOTS:
            for text in (u"Пошли на дискотеку", u"Пошли на концерт", u"Пойдём на бал",
                         u"Пошли на вечеринку", u"Готовимся к празднику"):
                env = self.environment(root)
                env["es_ai_apply_actions"]({"reply": "Yes"}, text)
                self.assertEqual(env["ES_AI_DRESS"][0], "dress")
                self.assertTrue(env["ES_AI_PARTY"][0])
                for g in env["ES_AI_SHOWN"][1:]:
                    self.assertEqual(g["dress"], "dress" if g["id"] in ("sl", "us") else None)
                env["es_ai_cameo_enter"]("mt", "normal")
                self.assertEqual(env["ES_AI_SHOWN"][-1]["dress"], "dress")

    def test_explicit_and_named_only(self):
        for root in ROOTS:
            for text in (u"Надень платье", u"Переоденься для дискотеки", u"ты переоденешься в платье"):
                env = self.environment(root)
                env["es_ai_apply_actions"]({"reply": "Yes"}, text)
                self.assertEqual(env["ES_AI_DRESS"][0], "dress")
                self.assertFalse(env["ES_AI_PARTY"][0])
                self.assertTrue(all(g.get("dress") != "dress" for g in env["ES_AI_SHOWN"][1:]))
            env = self.environment(root)
            env["es_ai_apply_actions"]({"dress": "dress"}, u"Славя, надень платье")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            self.assertEqual(env["ES_AI_SHOWN"][1]["dress"], "dress")
            for cid in ("mi", "dv"):
                env["ES_AI_LOC_LAST_CHAR"][0] = cid
                env["es_ai_set_dress"]("dress")
                self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_questions_negation_cancellation_and_cover(self):
        for root in ROOTS:
            for text in (u"Где концерт?", u"Не пойдём на дискотеку", u"Концерт отменили",
                         u"Пошли на сцену", u"Не надень платье", u"Не переоденься для дискотеки",
                         u"когда ты переоденешься в платье?", u"ты не переоденешься в платье"):
                env = self.environment(root)
                env["es_ai_apply_actions"]({"dress": "dress", "reply": u"Идём на концерт"}, text)
                self.assertFalse(env["ES_AI_PARTY"][0])
                self.assertIsNone(env["ES_AI_DRESS"][0])
            env = self.environment(root)
            env["es_ai_apply_actions"]({}, u"Пошли на дискотеку")
            env["es_ai_apply_actions"]({}, u"Славя, надень форму")
            self.assertEqual(env["ES_AI_SHOWN"][1]["dress"], "pioneer")
            env["es_ai_cameo_enter"]("sl", "normal", dress="dress")
            self.assertEqual(env["ES_AI_SHOWN"][1]["dress"], "pioneer")
            env["es_ai_apply_actions"]({}, u"Надень форму")
            env["es_ai_apply_actions"]({}, u"Привет")
            self.assertEqual(env["ES_AI_DRESS"][0], "cover")
            env["es_ai_apply_actions"]({}, u"Концерт отменили")
            self.assertFalse(env["ES_AI_PARTY"][0])

    def test_travel_resets_and_reapplies_after_goto(self):
        for root in ROOTS:
            env = self.environment(root)
            env["renpy"].scene = lambda: None
            env["renpy"].show = lambda *a: None
            env["es_ai_loc_bg"] = lambda loc: "bg"
            env["es_ai_cameo_on_arrive"] = lambda: None
            env["es_ai_apply_actions"]({"goto": "stage_big", "travel_all": True}, u"Пошли на концерт")
            self.assertTrue(env["ES_AI_PARTY"][0])
            self.assertEqual(env["ES_AI_DRESS"][0], "dress")
            env["es_ai_set_location"]("square", travel_all=True)
            self.assertFalse(env["ES_AI_PARTY"][0])
            self.assertIsNone(env["ES_AI_DRESS"][0])
            self.assertTrue(all(g.get("dress") != "dress" for g in env["ES_AI_SHOWN"][1:]))
            env["es_ai_set_location"]("stage", travel_all=True)
            self.assertFalse(env["ES_AI_PARTY"][0])

    def test_exact_assets_and_normal_preference(self):
        for root in ROOTS:
            env = self.environment(root)
            images = {"un angry pioneer", "un normal dress", "mi normal pioneer", "dv normal pioneer2"}
            env["renpy"].has_image = lambda tag, exact=False: tag in images if exact else any(i.startswith(tag) for i in images)
            self.assertTrue(env["es_ai_has_party_dress"]("un"))
            self.assertFalse(env["es_ai_has_party_dress"]("mi"))
            self.assertFalse(env["es_ai_has_party_dress"]("dv"))
            self.assertEqual(env["es_ai_resolve_sprite"]("un", "angry", "dress"), "un normal dress")
            self.assertEqual(env["es_ai_resolve_sprite"]("mi", "normal", "dress"), "mi normal pioneer")
            self.assertEqual(env["es_ai_resolve_sprite"]("dv", "normal", "dress"), "dv normal pioneer2")
            for bad in ("nude", "body", "dress nude", "undress"):
                env["es_ai_set_dress"](bad)
                self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_server_authorization_and_neutral_age(self):
        for root in ROOTS:
            server = os.path.join(DEV, "server") if root == ROOTS[0] else os.path.join(root, "server")
            env = {"re": re, "cfg": {}}
            load(os.path.join(server, "main.py"), env, {"cameo", "normalize_dress", "parse_action_tags",
                 "parse_cameo_tags", "clock_prompt", "game_clock_valid"}, False)
            llm = types.ModuleType("llm_client")
            store = types.ModuleType("characters_store")
            store.get_character = lambda cid: {"name": cid, "persona": "Old concert memory", "age": 14}
            store.map_emotion = lambda cid, emo: emo
            store.reply_rules = lambda ch: "AGE SAFETY RULES"
            store.player_block = lambda: ""
            prompts = []
            llm.chat = lambda messages, **kw: prompts.append(messages[0]["content"]) or "(normal) Hi [action:dress:dress]"
            llm.sanitize_in_character = lambda s: s
            llm.strip_prompt_leak = lambda s, p: s
            with patch.dict(sys.modules, llm_client=llm, characters_store=store,
                            scene_memory=types.SimpleNamespace(ingest=lambda events: None, prompt=lambda cid: "")):
                for cid in ("un", "sl", "us", "mt", "mi", "dv"):
                    out = env["cameo"]({"character": cid, "party": True, "dress": "dress", "dress_reason": "party"})
                    self.assertEqual(out.get("dress"), "dress" if cid in ("un", "sl", "us", "mt") else None)
                    self.assertIn("AGE SAFETY RULES", prompts[-1])
                for text, expected in ((u"Славя, приоденьсе в платье, я собираюсь пойти с тобой на концерт.", "dress"),
                                       (u"Славя, приоденься в платье", "dress"), (u"Славя, не приоденьсе в платье", None),
                                       (u"Славя, надень платье", "dress"), (u"Славя, переоденешься в платье", "dress"), (u"Славя, не надень платье", None),
                                       (u"Лена, надень платье", None), (u"Где концерт?", None)):
                    self.assertEqual(env["cameo"]({"character": "sl", "location_id": "stage", "player_text": text}).get("dress"), expected)
                self.assertIn("AUTHORITATIVE CURRENT CLOTHING: pioneer", prompts[-1])

    def test_python2_unicode_context(self):
        exe = os.path.join(GAME_ROOT, "lib/windows-i686/python.exe")
        if not os.path.isfile(exe):
            self.skipTest("Bundled Python 2 unavailable")
        code = "import ast,io,re,textwrap; " + \
            "s=io.open(__import__('sys').argv[1],encoding='utf-8').read().lstrip(u'\\ufeff'); " + \
            "b=re.split(r'^init [^\\n]*python:\\s*\\n',s,flags=re.M)[1:]; " + \
            "nodes=[n for block in b for n in ast.parse(textwrap.dedent(block)).body if isinstance(n,ast.FunctionDef) and n.name=='es_ai_party_context']; " + \
            "e={}; exec compile(ast.Module(body=nodes),'<party>','exec') in e; " + \
            "assert e['es_ai_party_context'](u'\\u041f\\u043e\\u0448\\u043b\\u0438 \\u043d\\u0430 \\u043a\\u043e\\u043d\\u0446\\u0435\\u0440\\u0442') is True"
        for root in ROOTS:
            subprocess.check_call([exe, "-c", code, os.path.join(root, "es_ai_cameo.rpy")])

    def test_stock_dress_declarations(self):
        path = os.path.join(GAME_ROOT, "game/sprites.rpyc")
        if not os.path.isfile(path):
            self.skipTest("Stock sprites.rpyc unavailable")
        with open(path, "rb") as stream:
            data = stream.read()
        if data.startswith(b"RENPY RPC2"):
            slot, offset, length = struct.unpack("<III", data[10:22])
            self.assertEqual(slot, 1)
            data = data[offset:offset + length]
        class Node:
            def __new__(cls, *args):
                node = object.__new__(cls)
                node.args = args
                return node
            def __setstate__(self, state):
                self.state = state
        class Reader(pickle.Unpickler):
            def find_class(self, module, name):
                return Node
        tree = Reader(io.BytesIO(zlib.decompress(data)), encoding="utf-8").load()
        images, seen = {}, set()
        def walk(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            if isinstance(value, Node):
                walk(getattr(value, "state", None))
            elif isinstance(value, dict):
                name = value.get("imgname")
                if isinstance(name, tuple):
                    images[name] = value
                for item in value.values():
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
        walk(tree)
        self.assertGreater(len(images), 1000)
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, Node):
                for text in strings(value.args):
                    yield text
                for text in strings(getattr(value, "state", None)):
                    yield text
            elif isinstance(value, dict):
                for item in value.values():
                    for text in strings(item):
                        yield text
            elif isinstance(value, (list, tuple)):
                for item in value:
                    for text in strings(item):
                        yield text
        archive = os.path.join(os.path.dirname(path), "archive.rpa")
        if not os.path.isfile(archive) or not os.path.isfile(os.path.join(GAME_ROOT, "renpy/display/image.py")):
            self.skipTest("Stock archive or image registry unavailable")
        with open(archive, "rb") as stream:
            header = stream.readline().split()
            stream.seek(int(header[1], 16))
            index = pickle.loads(zlib.decompress(stream.read()))
        filenames = {name.decode("utf-8") if isinstance(name, bytes) else name for name in index}
        for cid in ("sl", "mt"):
            expression = "\n".join(strings(images[(cid, "normal", "dress")]))
            self.assertIn("dress", expression)
            layers = re.findall(r"[\"'](images/[^\"']+\.png)[\"']", expression)
            self.assertTrue(layers, expression)
            for filename in layers:
                self.assertIn(filename, filenames)
            self.assertTrue(any("/normal/" in filename and "_dress.png" in filename for filename in layers))
        engine = os.path.join(GAME_ROOT, "renpy/display/image.py")
        registry = {"images": images}
        load(engine, registry, {"image_exists"}, False)
        for root in ROOTS:
            env = self.environment(root)
            env["renpy"].has_image = registry["image_exists"]
            for cid in ("un", "sl", "us", "mt"):
                self.assertIn((cid, "normal", "dress"), images)
                self.assertTrue(env["es_ai_has_party_dress"](cid))
                tag = env["es_ai_resolve_sprite"](cid, "normal", "dress")
                self.assertTrue(registry["image_exists"](tag, exact=True))
                self.assertIn("dress", tag.split())
            for cid in ("mi", "dv"):
                self.assertFalse(env["es_ai_has_party_dress"](cid))


if __name__ == "__main__":
    unittest.main()
