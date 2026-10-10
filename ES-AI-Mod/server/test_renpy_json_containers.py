"""Offline Python 2/3 regressions for JSON crossing the Ren'Py store boundary."""
import ast
import io
import json
import os
import random
import re
import sys
import textwrap
import unittest
try:
    import __builtin__ as builtins
except ImportError:
    import builtins


ROOTS = (
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mod"),
    r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310",
)


class RevertableDict(dict):
    pass


class RevertableList(list):
    pass


class Stub(object):
    pass


def extract(root, filename, names, assignments=()):
    with io.open(os.path.join(root, filename), encoding="utf-8-sig") as stream:
        source = stream.read()
    blocks = re.split(r"^init [^\n]*python:\s*\n", source, flags=re.M)[1:]
    nodes = []
    for block in blocks:
        for node in ast.parse(textwrap.dedent(block)).body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in assignments for t in node.targets):
                nodes.append(node)
            elif isinstance(node, ast.Import) and any(
                    alias.asname == "_es_ai_cameo_builtins" for alias in node.names):
                nodes.append(node)
    module = ast.Module(body=nodes, type_ignores=[]) if sys.version_info[0] >= 3 else ast.Module(body=nodes)
    return compile(module, filename, "exec")


class JsonContainerTests(unittest.TestCase):
    def setUp(self):
        self.original_open = io.open
        self.original_builtin_module = sys.modules.get("__builtin__")
        sys.modules["__builtin__"] = builtins

    def tearDown(self):
        io.open = self.original_open
        if self.original_builtin_module is None:
            sys.modules.pop("__builtin__", None)
        else:
            sys.modules["__builtin__"] = self.original_builtin_module

    def environment(self, root):
        persistent = Stub()
        persistent.es_ai_cameo = True
        renpy = Stub()
        renpy.with_statement = lambda *a: None
        self.logs, self.spoken, self.calls, self.arrivals = [], [], [], []
        env = {"dict": RevertableDict, "list": RevertableList,
               "basestring": getattr(builtins, "basestring", str),
               "unicode": getattr(builtins, "unicode", str), "long": getattr(builtins, "long", int),
               "persistent": persistent, "renpy": renpy, "dissolve": None,
               "_es_random": random.Random(42), "ES_AI_SERVER_DIR": root,
               "ES_AI_CHARS": [(c, c, "") for c in ("un", "dv", "us", "sh")],
               "ES_AI_SHOWN": RevertableList([{"id": "un"}]),
               "ES_AI_LOC_CUR": ["square"], "ES_AI_LOC_LAST_CHAR": ["un"],
               "ES_AI_CLOCK": dict(enabled=False, lines=0),
               "ES_AI_LOC_LAST_EMO": [None], "ES_AI_CAMEO_CD": [0],
               "ES_AI_CAMEO_COOLDOWN": 5, "ES_AI_ROMANCEABLE": [],
               "es_ai_recent_push": lambda *a: None, "es_ai_recent_snapshot": lambda n: [],
               "es_ai_cameo_name": lambda cid: cid, "es_ai_log": self.logs.append,
               "es_ai_refresh_girls": lambda: None,
               "es_ai_cameo_clear": lambda: None,
               "es_ai_cameo_speak": lambda cid, *a: self.spoken.append(cid),
               "es_ai_location_id": lambda loc: loc,
               "es_ai_location_from_dialog": lambda *a: None,
               "es_ai_set_location": lambda *a, **k: self.arrivals.append(k["cameo_arrive"]),
               "es_ai_dress_from_context": lambda *a: None, "es_ai_location": lambda: {}}

        def line(cid, active, romantic, **kwargs):
            self.calls.append((cid, kwargs["mode"], kwargs["on_topic"]))
            return json.loads('{"reply":"Hi","emotion":"smile"}')

        def unexpected(*a, **k):
            raise AssertionError("Explicit JSON request fell into random cameo flow")

        env.update(es_ai_cameo_line=line, es_ai_cameo_tick=unexpected,
                   es_ai_maybe_cameo=unexpected, es_ai_is_romantic_moment=unexpected)
        code = extract(root, "es_ai_cameo.rpy", {
            "es_ai_read_cameo_settings", "es_ai_read_cameo_flag", "es_ai_cameo_on",
            "es_ai_write_cameo_setting", "es_ai_scene_snapshot", "es_ai_try_cameo",
            "es_ai_cameo_enter", "es_ai_cameo_dress", "es_ai_cameo_register", "es_ai_cameo_leave",
            "es_ai_cameo_unregister", "es_ai_cameo_take_nearby", "es_ai_cameo_capacity", "es_ai_cameo_group_size",
            "es_ai_cameo_deliver_group"}, {"ES_AI_CAMEO_DEFAULTS", "ES_AI_CAMEO_BY_LOC",
                                      "ES_AI_CAMEO_ACTIVE", "ES_AI_CAMEO_NEARBY"})
        exec(code, env)
        env["ES_AI_LOCATION_INDEX"] = dict.fromkeys(list(env["ES_AI_CAMEO_BY_LOC"]) + ["bus_stop"], {})
        exec(extract(root, "es_ai_locations.rpy", {"es_ai_apply_actions"}), env)
        # Redirect every config read/write to memory, including workshop user config.
        env["es_ai_user_config_path"] = lambda: os.path.join(root, "config.json")
        self.config = {"cameo_enabled": True, "cameo_stay": True,
                       "cameo_freq": 0, "cameo_max_extra": 2}
        self.written = []

        def fake_open(path, mode="r", **kwargs):
            self.assertEqual(os.path.basename(path), "config.json")
            if mode == "r":
                return io.StringIO(env["unicode"](json.dumps(self.config)))
            self.assertEqual(mode, "w")
            output = Stub()
            output.write = self.written.append
            output.close = lambda: None
            return output

        io.open = fake_open
        return env

    def check(self, root):
        env = self.environment(root)
        incoming = json.loads('{"cameo":["dv","us"],"scene_debug":'
            '{"status":"selected","origin":"intent","chosen_cameo":["dv","us"],'
            '"direct_result":[],"present":["un"],"enabled":true,"capacity":2}}')
        self.assertIs(type(incoming), builtins.dict)
        self.assertIs(type(incoming["cameo"]), builtins.list)
        self.assertFalse(isinstance(incoming, env["dict"]))
        self.assertFalse(isinstance(incoming["cameo"], env["list"]))
        st = env["es_ai_read_cameo_settings"]()
        self.assertIs(type(st), RevertableDict, "Settings construction must remain rollback-aware")
        self.assertEqual(st["cameo_freq"], 0)
        configured_max = self.config.pop("cameo_max_extra")
        self.assertEqual(env["es_ai_read_cameo_settings"]()["cameo_max_extra"], 6)
        self.config["cameo_max_extra"] = configured_max
        env["es_ai_try_cameo"]("un", "group", incoming)
        self.assertTrue(self.spoken)
        self.assertTrue(set(self.spoken) <= {"dv", "us"})
        self.assertEqual(self.calls, [(cid, "here", True) for cid in self.spoken])
        self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["un", "dv", "us"])
        diagnostic = json.loads(self.logs[0].split("scene server: ", 1)[1])
        self.assertEqual(diagnostic["status"], "selected")
        self.assertEqual(diagnostic["chosen_cameo"], ["dv", "us"])
        self.assertEqual(diagnostic["direct_result"], [])
        self.assertNotIn("missing-scene-debug", self.logs[0])
        self.spoken[:] = []
        env["es_ai_try_cameo"]("un", "direct", json.loads('{"cameo":["us"]}'))
        self.assertEqual(self.spoken, ["us"])
        self.assertEqual(self.calls[-1], ("us", "stay", True))
        self.assertEqual(len(env["ES_AI_SHOWN"]), 3)
        for cameo, enabled, expected in ((["us"], True, False), (["sh"], True, False),
                (["unknown"], True, True), (["un"], True, True), ([], True, True),
                ("us", True, True), (["us"], False, True)):
            self.config["cameo_enabled"] = enabled
            env["es_ai_apply_actions"](json.loads(json.dumps({"goto": "beach", "cameo": cameo})))
            self.assertEqual(self.arrivals[-1], expected)
        self.assertFalse(env["es_ai_read_cameo_flag"]())
        self.spoken[:] = []
        env["es_ai_try_cameo"]("un", "disabled", incoming)
        self.assertEqual(self.spoken, [])
        self.config.update(cameo_enabled=True, cameo_stay=False, cameo_freq="17",
                           cameo_ctx=200, unrelated={"preserve": [1, 2]})
        st = env["es_ai_read_cameo_settings"]()
        self.assertFalse(st["cameo_stay"])
        self.assertEqual(st["cameo_freq"], 17)
        self.assertEqual(st["cameo_ctx"], 100)
        env["ES_AI_SHOWN"][:] = [{"id": "un"}]
        env["es_ai_try_cameo"]("un", "no stay", incoming)
        self.assertTrue(self.spoken)
        self.assertTrue(set(self.spoken) <= {"dv", "us"})
        self.assertEqual(env["ES_AI_SHOWN"], [{"id": "un"}])
        self.spoken[:] = []
        self.config["cameo_stay"] = True
        env["es_ai_try_cameo"]("un", "direct new", json.loads('{"cameo":["us"]}'))
        self.assertEqual(self.spoken, ["us"])
        self.assertEqual(self.calls[-1], ("us", "here", True))
        self.assertEqual([g["id"] for g in env["ES_AI_SHOWN"]], ["un", "us"])
        env["es_ai_write_cameo_setting"]("cameo_freq", 23)
        saved = json.loads("".join(self.written))
        self.assertEqual(saved["unrelated"], {"preserve": [1, 2]})
        self.assertEqual(saved["cameo_freq"], 23)
        self.assertFalse(any("cameo error:" in log for log in self.logs), self.logs)

    def test_dev(self):
        self.check(ROOTS[0])

    def test_workshop(self):
        self.check(ROOTS[1])


if __name__ == "__main__":
    print("Runtime: " + sys.version)
    unittest.main()
