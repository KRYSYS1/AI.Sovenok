"""Run offline with the installed Ren'Py Python 2 interpreter, never live config."""
from __future__ import print_function
import io
import json
import os
import shutil
import sys
import tempfile
import types
import __future__
import ast
try:
    import __builtin__ as builtins
except ImportError:
    import builtins

# Ren'Py's bundled interpreter does not add the script directory to sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_paths import TEMP


class StoreDict(dict):
    pass


class StoreList(list):
    pass


class StoreStr(str):
    pass


def check_init(code):
    """Execute every init statement, with all external effects forbidden."""
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected init I/O, callback, worker or HTTP")

    name = "_es_ai_delivery_backend"
    for callbacks in (False, True):
        for reused in (False, True):
            sys.modules.pop(name, None)
            config = types.ModuleType("offline_config")
            if callbacks:
                config.quit_callbacks = [forbidden]
            fake = types.ModuleType(name)
            fake.lock = __import__("threading").RLock()
            fake.loaded = False
            fake.running = False
            fake.data = dict(version=1, public_events=[], story_acks=[])
            fake.retired = set()
            if reused:
                sys.modules[name] = fake
            env = dict(str=StoreStr, dict=StoreDict, list=StoreList, all=forbidden, config=config,
                       open=forbidden, es_ai_log=forbidden, es_ai_run_async=forbidden,
                       es_ai_http=forbidden, es_ai_public_snapshot=forbidden,
                       es_ai_story_ack_snapshot=forbidden)
            try:
                eval(code, env)
                backend = env["_delivery_backend"]
                require(type(backend.__name__) is str)
                require(sys.modules[name] is backend)
                require(not reused or backend is fake)
                require(not backend.loaded and not backend.running)
                if callbacks:
                    require(config.quit_callbacks == [forbidden, env["es_ai_delivery_flush"]])
                # Only this synthetic path and BytesIO can be read; no real user data.
                path = "offline-delivery.json"
                expected = dict(version=1, public_events=[dict(id="restart", text=u"\u0442\u0435\u0441\u0442")],
                                story_acks=[dict(token="t", delivery_id="d")])
                raw = json.dumps(expected).encode("utf-8")
                reads = []
                def read_file(filename, mode):
                    require(filename == path and mode == "rb")
                    reads.append(filename)
                    return io.BytesIO(raw)
                env["es_ai_delivery_path"] = lambda: path
                env["_delivery_os"] = type("OfflineOS", (), {
                    "path": type("OfflinePath", (), {"exists": staticmethod(lambda p: p == path)})})
                env["open"] = read_file
                env["_es_ai_delivery_load"]()
                env["_es_ai_delivery_load"]()
                require(backend.loaded and backend.data == expected and reads == [path])
                require(type(backend.data) is dict)
                require(type(backend.data["public_events"]) is list)
                env["open"] = forbidden
                eval(code, env)
                require(env["_delivery_backend"] is backend)
                require(backend.loaded and backend.data == expected and reads == [path])
                if callbacks:
                    require(config.quit_callbacks[0] is forbidden and len(config.quit_callbacks) == 3)
                print("full init + in-memory load: callbacks=%s reused=%s module_name=%s" %
                      (callbacks, reused, type(backend.__name__).__name__))
            finally:
                sys.modules.pop(name, None)


def require(value):
    if not value:
        raise AssertionError("Python 2 delivery check failed")


def check():
    require(sys.version_info[:2] == (2, 7))
    fixtures = json.load(sys.stdin)
    print("interpreter: %s; unicode_literals flag=%s" %
          (sys.version, __future__.unicode_literals.compiler_flag))
    for root, files in fixtures:
        print("root: %s" % root)
        for filename, blocks in files:
            for block in blocks:
                compile(block, filename, "exec", __future__.unicode_literals.compiler_flag, True)
            if filename == "es_ai_delivery.rpy":
                require(len(blocks) == 1)
                code = compile(blocks[0], filename, "exec", __future__.unicode_literals.compiler_flag, True)
                require(code.co_flags & __future__.unicode_literals.compiler_flag)
                check_init(code)
            if filename == "es_ai_api.rpy":
                names = set(("es_ai_sanitize_text", "es_ai_story_choices_record", "es_ai_story_choices_menu", "es_ai_story_input_take"))
                nodes = [node for block in blocks for node in ast.parse(block).body
                         if isinstance(node, ast.FunctionDef) and node.name in names]
                selected, menus = ["help"], []
                class Renpy(object):
                    def display_menu(self, items, **kwargs):
                        menus.append(items)
                        return selected[0]
                choice_env = dict(dict=StoreDict, list=StoreList, str=StoreStr,
                                  _es_ai_cameo_builtins=builtins, renpy=Renpy(), ES_AI_FREE_SCENE=[True],
                                  ES_AI_STORY_INPUT=dict(pending=None, selection=None, choice=None))
                eval(compile(ast.Module(nodes), filename, "exec", __future__.unicode_literals.compiler_flag, True), choice_env)
                offer = dict(token="a" * 36, version=3, options=[dict(id="help", text=u"\u0414\u0430"), dict(id="no", text=u"\u041d\u0435\u0442")])
                choice_env["es_ai_story_choices_record"](offer)
                require(not menus)
                choice_env["es_ai_story_choices_menu"]()
                require(menus[0][-1][1] == ("custom",))
                require(choice_env["es_ai_story_input_take"]() == u"\u0414\u0430")
                require(choice_env["ES_AI_STORY_INPUT"]["selection"]["id"] == "help")
                selected[0] = ("custom",)
                choice_env["es_ai_story_choices_record"](offer)
                choice_env["es_ai_story_choices_menu"]()
                require(choice_env["es_ai_story_input_take"]() is None)
                require(choice_env["ES_AI_STORY_INPUT"]["selection"] is None)
        directory = tempfile.mkdtemp(dir=TEMP)
        try:
            for nonempty in (False, True):
                sys.modules.pop("_es_ai_delivery_backend", None)
                config = types.ModuleType("offline_config")
                config.quit_callbacks = []
                config.character_callback = None
                errors, jobs, events, acks = [], [], [], []
                env = dict(str=StoreStr, dict=StoreDict, list=StoreList, config=config,
                           es_ai_log=errors.append, es_ai_run_async=lambda *a: jobs.append(a),
                           es_ai_public_snapshot=lambda: events, es_ai_story_ack_snapshot=lambda: acks)
                exec(code, env)
                path = os.path.join(directory, "delivery_outbox.json")
                env["es_ai_delivery_path"] = lambda: path
                expected = dict(version=1, public_events=[dict(id="restart")] if nonempty else [],
                                story_acks=[dict(token="t", delivery_id="d")] if nonempty else [])
                env["_es_ai_delivery_save"](expected)
                env["es_ai_delivery_flush"](send=False)
                require(not errors)
                require(env["_delivery_backend"].data == expected)
                require(type(env["_delivery_backend"].data) is dict)
                require(type(env["_delivery_backend"].data["public_events"]) is list)
                require(not jobs)

                env["ES_AI_CLOCK"] = dict(lines=0)
                env["es_ai_public_record"] = lambda cid, raw: events.append(dict(id="visible", text=raw))
                env["es_ai_story_ack_record"] = lambda ack: acks.append(ack) if ack else None
                ack = dict(token="ack", delivery_id="visible")

                class Character(object):
                    display_args = {"callback": None}

                    def __call__(self, text, callback=None):
                        callback("show", interact=True, type="say")
                        callback("show_done", interact=True, type="say")
                        callback("show_done", interact=True, type="say")
                        with open(path, "rb") as stream:
                            saved = json.load(stream)
                        require(saved["story_acks"][-1] == ack)
                        require(saved["public_events"][-1]["id"] == "visible")
                        raise SystemExit("quit during interaction")

                try:
                    env["es_ai_delivery_say"](Character(), "safe", "sl", "raw", ack)
                except SystemExit:
                    pass
                require(len(events) == 1 and acks == [ack])
                require(env["ES_AI_CLOCK"]["lines"] == 1)
                require(not jobs and not errors)
        finally:
            shutil.rmtree(directory)
    print("both roots Python 2 init compile, shadowed restart and display persistence passed")


if __name__ == "__main__":
    check()
