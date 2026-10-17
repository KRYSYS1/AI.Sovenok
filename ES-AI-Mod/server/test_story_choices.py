"""Offline choice protocol tests against both installations; no live data or API calls."""
import copy
import json
import os
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

import test_story_events as stories
from test_paths import GAME_ROOT, existing_paths
from test_cameo_clothing import ROOTS, load
import test_cameo_clothing as clothing
import test_delivery as delivery


OPTIONS = [dict(id="help", text="Yes"), dict(id="refuse", text="No thanks")]


class ChoiceTests(unittest.TestCase):
    def test_installed_engine_click_to_actual_chat_input(self):
        executable = os.path.join(GAME_ROOT, 'lib', 'windows-i686', 'python.exe')
        if not os.path.isfile(executable):
            self.skipTest('Installed Ren\'Py Python 2 unavailable')
        runner = r'''
import ast, io, json, os, sys, types
engine, roots = json.load(sys.stdin)
def namespace(**kw):
    value = types.ModuleType('fixture')
    value.__dict__.update(kw)
    return value
def extract(path, names, env, indent=False):
    with io.open(path, encoding='utf-8') as stream:
        source = stream.read().lstrip(u'\ufeff')
    if indent:
        source = '\n'.join(line[4:] if line.startswith('    ') else '# ' + line for line in source.splitlines())
    nodes = [n for n in ast.parse(source.encode('utf-8')).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(nodes) == len(names), names
    for node in nodes:
        node.decorator_list = []
    eval(compile(ast.Module(nodes), path, 'exec'), env)
class Action(object): pass
class DictEquality(object): pass
opened, clicked, shown, checkpoints = [], [], [], []
env = dict(Action=Action, DictEquality=DictEquality, main_menu=True,
           ShowMenu=lambda name: lambda: opened.append(name), random=__import__('random'))
extract(os.path.join(engine, 'renpy', 'common', '00action_control.rpy'), ['Return'], env, True)
env['Return'](None)()
assert opened == ['main_menu']  # Reproduce original bug with the actual action.
opened[:] = []
extract(os.path.join(engine, 'renpy', 'ui.py'), ['ChoiceActionBase', 'ChoiceReturn'], env)
extract(os.path.join(engine, 'renpy', 'exports.py'), ['MenuEntry', 'display_menu'], env)
config = namespace(auto_choice_delay=0, fix_rollback_without_choice=False,
                   choice_screen_chosen=True, choice_layer='screens', menu_showed_window=False,
                   implicit_with_none=False)
renpy = namespace(config=config)
renpy.exports = namespace(mode=lambda *a: None, roll_forward_info=lambda: None,
                          in_fixed_rollback=lambda: False)
renpy.game = namespace(context=lambda: namespace(current='es_ai_chat_input'),
                       persistent=namespace(_chosen={}))
renpy.ui = namespace(ChoiceReturn=env['ChoiceReturn'])
def interact(**kwargs):
    action = shown[-1][clicked[-1]].action
    assert action is not None
    return action()
renpy.ui.interact = interact
env.update(renpy=renpy, get_menu_args=lambda: ((), {}), choice_for_skipping=lambda: None,
           in_fixed_rollback=lambda: False, has_screen=lambda name: True,
           show_screen=lambda name, **kw: shown.append(kw['items']), log=lambda *a: None,
           checkpoint=checkpoints.append)
renpy.display_menu = env['display_menu']
for root in roots:
    extract(os.path.join(root, 'es_ai_api.rpy'),
            ['es_ai_sanitize_text', 'es_ai_story_choices_record', 'es_ai_story_choices_menu',
             'es_ai_story_input_take', 'es_ai_chat_async'], env, True)
    with io.open(os.path.join(root, 'es_ai_chat.rpy'), encoding='utf-8') as stream:
        chat = stream.read().split('label es_ai_chat_input:', 1)[1].split('    show screen es_ai_thinking', 1)[0]
    # Execute the actual label's input/empty-input branch, stopping before request/wait.
    code = []
    for line in chat.splitlines():
        line = line[4:]
        if line.lstrip().startswith('$ '):
            line = line.replace('$ ', '', 1)
        if line.lstrip().startswith('jump '):
            line = line[:len(line)-len(line.lstrip())] + 'raise Jump()'
        code.append(line)
    input_code = compile('\n'.join(code), 'es_ai_chat_input', 'exec')
    class Jump(Exception): pass
    for index, typed in ((2, 'My own reply'), (0, 'unused'), (2, '')):
        requests, inputs, clocks = [], [], []
        env.update(ES_AI_STORY_INPUT=dict(pending='stale', selection=dict(id='stale'), choice=None),
                   ES_AI_FREE_SCENE=[True], _es_ai_cameo_builtins=__import__('__builtin__'),
                   ES_AI_LOC_LAST_CHAR=['un'], es_ai_char_id='un', es_ai_voice_text='',
                   es_ai_clock_sync=lambda: None, es_ai_char_name=lambda cid: cid, Jump=Jump,
                   es_ai_delivery_flush=lambda: None, es_ai_request_trace=lambda *a: {},
                   es_ai_log=lambda *a: None, es_ai_clock_begin=lambda **kw: clocks.append(1) or 1,
                   es_ai_chat_active=[True], es_ai_public_record=lambda *a: None,
                   es_ai_clock_snapshot=lambda: {}, es_ai_public_snapshot=lambda: [],
                   es_ai_story_ack_snapshot=lambda: [], es_ai_location_context=lambda: 'square',
                   es_ai_scene_snapshot=lambda *a: {}, es_ai_run_async=lambda kind, fn: fn(),
                   es_ai_http=lambda path, payload: requests.append(payload) or dict(ok=True))
        renpy.input = lambda *a, **kw: inputs.append(1) or typed
        clicked.append(index)
        env['es_ai_story_choices_record'](dict(token='a'*36, version=4,
            options=[dict(id='help', text='Yes'), dict(id='no', text='No')]))
        before = len(shown)
        env['es_ai_story_choices_menu']()
        env['es_ai_story_choices_menu']()
        assert len(shown) == before + 1
        assert not requests and not clocks and not opened
        try:
            eval(input_code, env)
        except Jump:
            assert typed == '' and index == 2
            assert not requests and not clocks
            continue
        assert env['es_ai_char_id'] == 'un'
        assert env['_inp'] == ('Yes' if index == 0 else typed)
        assert len(inputs) == (0 if index == 0 else 1)
        env['es_ai_chat_async'](env['es_ai_char_id'], env['_inp'])
        assert len(requests) == len(clocks) == 1
        assert requests[0]['character'] == 'un'
        assert ('story_choice' in requests[0]) == (index == 0)
        if index == 0:
            assert requests[0]['story_choice'] == dict(token='a'*36, version=4, id='help')
        assert env['ES_AI_STORY_INPUT']['selection'] is None
print('Real bundled display_menu -> ChoiceReturn click -> actual chat input branch passed in both roots; Return(None) regression reproduced')
'''
        result = subprocess.run([executable, '-B', '-c', runner],
                                input=json.dumps([GAME_ROOT, ROOTS]), text=True,
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_installed_renpy_screen_parser(self):
        executable = os.path.join(GAME_ROOT, 'lib', 'windows-i686', 'python.exe')
        if not os.path.isfile(executable):
            self.skipTest('Installed Ren\'Py Python 2 unavailable')
        # Run installed lexer/parser/registrations, not a hand-maintained keyword list.
        # Only runtime displayables and AST storage are inert; no screen executes.
        runner = r'''
import ast, io, json, os, sys, types
assert sys.version_info[:2] == (2, 7)
engine, roots = json.load(sys.stdin)
def module(name, path=None):
    value = types.ModuleType(name)
    if path is not None:
        value.__path__ = [path]
    sys.modules[name] = value
    if '.' in name:
        parent, attr = name.rsplit('.', 1)
        setattr(sys.modules[parent], attr, value)
    return value
renpy = module('renpy', os.path.join(engine, 'renpy'))
renpy.update_path = lambda: None
for name in ('display', 'test', 'ast', 'object', 'config', 'game', 'scriptedit', 'ui', 'text', 'atl'):
    module('renpy.' + name)
module('renpy.sl2', os.path.join(engine, 'renpy', 'sl2'))
slast = module('renpy.sl2.slast')
class Node(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.children, self.keyword, self.positional, self.entries = [], [], [], []
        self.tag = self.variable = None
        self.__dict__.update(kwargs)
    def has_python(self):
        return False
    def has_noncondition_child(self):
        return bool(self.children)
    def keyword_exist(self, name):
        return any(k == name for k, v in self.keyword)
for name in ('SLBlock', 'SLDisplayable', 'SLIf', 'SLShowIf', 'SLFor', 'SLPython',
             'SLPass', 'SLDefault', 'SLUse', 'SLTransclude', 'SLCustomUse', 'SLScreen'):
    setattr(slast, name, type(name, (Node,), {}))
class PyExpr(unicode):
    def __new__(cls, text, *args):
        return unicode.__new__(cls, text)
renpy.ast.PyExpr = PyExpr
renpy.ast.PyCode = renpy.ast.ParameterInfo = renpy.ast.ArgumentInfo = Node
renpy.object.Sentinel = lambda name: object()
renpy.config.basedir = renpy.config.renpy_base = engine
renpy.config.keyword_after_python = True
renpy.game.context = lambda: type('Context', (), {'init_phase': False})()
renpy.scriptedit.files, renpy.scriptedit.lines = set(), {}
class Line(object):
    def __init__(self, filename, number, start):
        self.start = start
renpy.scriptedit.Line = Line
# Rendering callables are only recorded by DisplayableParser, never invoked.
for branch, names in {
    'display.layout': 'Container Null MultiBox Grid Side Window',
    'display.behavior': 'Timer Input Button Bar MouseArea OnEvent',
    'display.motion': 'Transform',
    'display.dragdrop': 'Drag DragGroup',
    'text.text': 'Text',
}.items():
    target = module('renpy.' + branch)
    for name in names.split():
        setattr(target, name, type(name, (object,), {}))
for name in ('_key', '_imagebutton', '_textbutton', '_label', '_imagemap', '_hotspot', '_hotbar'):
    setattr(renpy.ui, name, lambda *a, **kw: None)
# Read static transform property registrations without importing the renderer.
with io.open(os.path.join(engine, 'renpy', 'display', 'transform.py'), encoding='utf-8') as stream:
    transform = ast.parse(stream.read())
renpy.atl.PROPERTIES = set()
for node in transform.body:
    if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ('add_property', 'add_gl_property')):
        renpy.atl.PROPERTIES.add(ast.literal_eval(node.value.args[0]))
    if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ALIASES'
                                           for t in node.targets)):
        renpy.atl.PROPERTIES.update(ast.literal_eval(key) for key in node.value.keys)
import renpy.parser as parser
import renpy.sl2.slparser as slparser
import renpy.sl2.slproperties
import renpy.sl2.sldisplayables
slparser.init()
registry = {p.name: p for p in slparser.all_statements}
assert 'substitute' in registry['text'].keyword
assert 'substitute' in registry['textbutton'].keyword
assert 'text_substitute' not in registry['textbutton'].keyword
assert 'substitute' not in registry['button'].keyword
def screens(filename, source):
    logical = parser.list_logical_lines(filename, source)
    lexer = parser.Lexer(parser.group_logical_lines(logical))
    result = []
    while lexer.advance():
        if lexer.keyword('screen'):
            result.append(slparser.parse_screen(lexer, lexer.get_location()))
    return result
bad = u'screen regression(items):\n    textbutton item.caption action Return(None) text_substitute False\n'
try:
    screens('<old-choice>', bad)
except parser.ParseError as error:
    assert "'text_substitute' is not a keyword argument or valid child for the textbutton statement" in error.message
else:
    raise AssertionError('original invalid textbutton syntax was accepted')
assert len(screens('<valid-textbutton>', bad.replace('text_substitute', 'substitute'))) == 1
total = 0
for root in roots:
    count, files, choices = 0, 0, []
    for filename in sorted(os.listdir(root)):
        if not filename.endswith('.rpy'):
            continue
        with io.open(os.path.join(root, filename), encoding='utf-8') as stream:
            source = stream.read()
        parsed = screens(filename, source)
        count += len(parsed)
        files += 1
        choices.extend(node for node in parsed if node.name == 'es_ai_story_choice')
    assert len(choices) == 1
    screen = choices[0]
    assert screen.modal == 'True'
    window = screen.children[0]
    assert 'choice_box.png' in dict(window.keyword)['background']
    assert dict(window.keyword)['padding'] == '(75, 50)'
    box = window.children[0]
    loop = box.children[0]
    button = loop.children[0]
    text = button.children[0]
    assert button.args[1] is registry['button'].displayable
    assert dict(button.keyword)['action'] == 'item.action'
    assert text.args[1] is registry['text'].displayable
    assert text.positional == ['item.caption']
    assert dict(text.keyword)['substitute'] == 'False'
    assert dict(text.keyword)['font'] == 'header_font'
    assert dict(text.keyword)['size'] == '37'
    assert 'persistent.timeofday' in dict(text.keyword)['color']
    assert 'persistent.timeofday' in dict(text.keyword)['hover_color']
    assert 'text_substitute' not in dict(button.keyword)
    print('root: %s; %s screens in %s rpy files parsed' % (root, count, files))
    total += count
assert total > 0
print('Python %s; installed parser.py Lexer + slparser.parse_screen + slproperties/sldisplayables registration; old syntax rejected; %s screens passed' % (sys.version.split()[0], total))
'''
        result = subprocess.run([executable, '-B', '-c', runner],
                                input=json.dumps([GAME_ROOT, ROOTS]), text=True,
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('old syntax rejected;', result.stdout)
        print(result.stdout.strip())

    def setup_manager(self, root):
        fixture = stories.StoryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        mod = stories.module(root)
        mod.manager = fixture.manager(mod)
        fixture.offer(mod.manager)
        return fixture, mod

    def token(self, manager):
        return manager.prepare(dict(enabled=True, choices_enabled=True), ["un", "sl", "mt"], "un")

    def offer(self, mod):
        token = self.token(mod.manager)
        value = mod.manager.stage_choices(token, OPTIONS, None, "Will you help?")
        self.assertIsNotNone(value)
        self.assertTrue(mod.manager.commit(token, None, "Will you help?"))
        return value

    def test_settings_dependency_and_disabled_lazy(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            mod = stories.module(root)
            with patch.object(mod.manager, "_load", side_effect=AssertionError("disabled I/O")):
                self.assertIsNone(mod.manager.prepare(dict(choices_enabled=True), [], "un"))
            self.assertFalse(mod.settings({})["choices_enabled"])
            self.assertTrue(mod.valid_setting("choices_enabled", True))
            self.assertFalse(mod.valid_setting("choices_enabled", 1))

    def test_parse_strips_before_actions_and_rejects_malformed(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            mod = stories.module(root)
            tag = '[choices:' + json.dumps(dict(options=OPTIONS)) + ']'
            self.assertEqual(mod.parse_choices("Hello " + tag), ("Hello", OPTIONS))
            invalid = [tag + tag, '[choices {"options":[]}]', '[choices:{bad}]',
                       '[choices:unfinished]', '[choices:{"options":[{"id":"a","text":"x"}]}]']
            for value in invalid:
                clean, options = mod.parse_choices("Hello " + value + " [action:goto:beach]")
                self.assertEqual(" ".join(clean.split()), "Hello [action:goto:beach]")
                self.assertIsNone(options)

    def test_strict_bounds_duplicates_markup_and_unknown_fields(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            mod = stories.module(root)
            for options in ([], OPTIONS[:1], OPTIONS * 3, [OPTIONS[0], OPTIONS[0]],
                            [OPTIONS[0], dict(id="other", text="YES")],
                            [OPTIONS[0], dict(id="b", text="x" * 161)],
                            [OPTIONS[0], dict(id="b", text="[action:goto:beach]")],
                            [OPTIONS[0], dict(id="b", text="{b}yes{/b}")],
                            [OPTIONS[0], dict(id="b", text="hi\nthere")],
                            [OPTIONS[0], dict(id="b", text="yes", action="goto")]):
                self.assertIsNone(mod.choice_options(dict(options=options)), options)
            self.assertIsNotNone(mod.choice_options(dict(options=[OPTIONS[0], dict(id="b", text="x" * 160)])))

    def test_only_plot_and_cooldown_duplicate_and_readonly(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture, mod = self.setup_manager(root)
            manager = mod.manager
            off = fixture.token(manager)
            self.assertIsNone(manager.stage_choices(off, OPTIONS, None, "Hi"))
            read = manager.prepare(dict(enabled=True, choices_enabled=True), ["un"], "un", True)
            self.assertIsNone(manager.stage_choices(read, OPTIONS, None, "Hi"))
            value = self.offer(mod)
            for _ in range(5):
                self.assertIsNone(manager.stage_choices(self.token(manager), OPTIONS, None, "Hi"))
                manager.commit(self.token(manager), None, "Hi")
            self.assertIsNone(manager.stage_choices(self.token(manager), OPTIONS, None, "Hi"))
            different = [dict(id="a", text="Ask for details"), dict(id="b", text="Leave it")]
            self.assertIsNotNone(manager.stage_choices(self.token(manager), different, None, "Hi"))
            self.assertIsNone(manager.select_choice(dict(value, id="help"), "Yes"))
            manager.state["status"] = "inactive"
            self.assertIsNone(manager.stage_choices(self.token(manager), different, None, "Hi"))

    def test_selected_commit_requires_ack_no_forgery_replay_or_forced_acceptance(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            for cid, text, expected in (("help", "Yes", "active"), ("refuse", "No thanks", "declined")):
                fixture, mod = self.setup_manager(root)
                offer = self.offer(mod)
                manager = mod.manager
                selection = dict(token=offer["token"], version=offer["version"], id=cid)
                before = copy.deepcopy(manager.state)
                self.assertIsNone(manager.select_choice(selection, "invented"))
                self.assertIsNone(manager.select_choice(dict(selection, token="fake"), text))
                cfg = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=True, choices_enabled=True)))
                with patch.dict(sys.modules, config_loader=cfg):
                    token = self.token(manager)
                    mod.bind_selection(token, selection, text)
                    self.assertIn("CURRENT SELECTED BRANCH", token["context"])
                    self.assertEqual(manager.state, before)
                    result = mod.response_metadata(token, dict(status="active"), "Okay", None, text)
                    self.assertEqual(manager.state, before)
                    self.assertIn("story_ack", result)
                    manager.acknowledge_direct([result["story_ack"]])
                    self.assertEqual(manager.state["status"], expected)
                    self.assertEqual(manager.state["decisions"], [dict(id=cid, text=text)])
                    committed = copy.deepcopy(manager.state)
                    manager.acknowledge_direct([result["story_ack"]])
                    self.assertEqual(manager.state, committed)
                    self.assertIsNone(manager.select_choice(selection, text))

    def test_failed_delivery_and_restart_fail_closed(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture, mod = self.setup_manager(root)
            offer = self.offer(mod)
            selection = dict(token=offer["token"], version=offer["version"], id="help")
            token = self.token(mod.manager)
            cfg = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=True, choices_enabled=True)))
            with patch.dict(sys.modules, config_loader=cfg):
                mod.bind_selection(token, selection, "Yes")
                before = copy.deepcopy(mod.manager.state)
                self.assertFalse(mod.manager.commit(token, None, ""))
                self.assertEqual(mod.manager.state, before)
                result = mod.response_metadata(token, dict(status="active"), "Okay", None, "Yes")
                with patch.object(mod.os, "replace", side_effect=OSError("disk full")):
                    mod.manager.acknowledge_direct([result["story_ack"]])
                self.assertEqual(mod.manager.state, before)
                restarted = mod.StoryManager(mod.manager.path)
                restarted.acknowledge_direct([result["story_ack"]])
                self.assertEqual(restarted.state['decisions'], [OPTIONS[0]])
                self.assertEqual(restarted.state['turns'], before['turns'] + 1)
                self.assertIsNone(restarted.select_choice(selection, "Yes"))

    def test_restart_shown_reply_saved_ack_commits_once_without_latest_offer(self):
        for root in (stories.DEV, stories.WORKSHOP):
            with self.subTest(root=root):
                self.assertTrue(os.path.isfile(os.path.join(root, 'story_events.py')))
                fixture, mod = self.setup_manager(root)
                offer = self.offer(mod)
                selection = dict(token=offer['token'], version=offer['version'], id='help')
                cfg = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=True, choices_enabled=True)))
                with patch.dict(sys.modules, config_loader=cfg):
                    token = self.token(mod.manager)
                    mod.bind_selection(token, selection, 'Yes')
                    metadata = mod.response_metadata(token, dict(status='active'), 'Let us search.', None, 'Yes')
                before = copy.deepcopy(mod.manager.state)
                with open(mod.manager._pending_path(), encoding='utf-8') as stream:
                    pending = json.load(stream)['events'][metadata['story_ack']['token']]
                bound = pending['validated_selection']
                self.assertEqual(bound, pending['token']['selected_choice'])
                self.assertEqual(bound['signature'], before['choice_signature'])
                self.assertEqual(bound['version'], before['version'])
                client_root = os.path.join(os.path.dirname(root), 'mod') if root == stories.DEV else os.path.dirname(root)
                with delivery.tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                    env, events, acks = delivery.DeliveryTests().speech_env(client_root, directory)
                    env['es_ai_delivery_say'](delivery.DisplayCharacter(env['config']), 'Let us search.',
                                              'un', 'Let us search.', metadata['story_ack'])
                    with open(env['es_ai_delivery_path'](), encoding='utf-8') as stream:
                        saved_ack = json.load(stream)['story_acks'][0]
                fresh = stories.module(root)
                fresh.manager = fresh.StoryManager(mod.manager.path)
                self.assertIsNone(fresh.manager.latest_choice)
                self.assertIsNone(fresh.manager.select_choice(selection, 'Yes'))
                with patch.dict(sys.modules, config_loader=cfg):
                    new_token = self.token(fresh.manager)
                    fresh.bind_selection(new_token, selection, 'Yes')
                    self.assertNotIn('selected_choice', new_token)
                    with patch.object(fresh.os, 'replace', side_effect=OSError('disk full')):
                        self.assertEqual(fresh.acknowledge_direct([saved_ack]), [])
                    self.assertEqual(fresh.manager.state, before)
                    self.assertIn(saved_ack['token'], fresh.manager.pending_direct)
                    forged_ack = dict(saved_ack, selected_choice=dict(id='forged', text='Injected branch'))
                    self.assertEqual(fresh.acknowledge_direct([forged_ack]), [saved_ack])
                    committed = copy.deepcopy(fresh.manager.state)
                    self.assertEqual(committed['decisions'], [OPTIONS[0]])
                    self.assertEqual(committed['turns'], before['turns'] + 1)
                    self.assertEqual(committed['status'], 'active')
                    fresh.acknowledge_direct([saved_ack])
                    self.assertEqual(fresh.manager.state, committed)

    def test_restart_selection_stale_revision_retires_whole_delivery(self):
        for root in (stories.DEV, stories.WORKSHOP):
            fixture, mod = self.setup_manager(root)
            offer = self.offer(mod)
            cfg = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=True, choices_enabled=True)))
            with patch.dict(sys.modules, config_loader=cfg):
                token = self.token(mod.manager)
                mod.bind_selection(token, dict(token=offer['token'], version=offer['version'], id='help'), 'Yes')
                result = mod.response_metadata(token, dict(status='active'), 'Okay', None, 'Yes')
            mod.manager.commit(self.token(mod.manager), None, 'Another reply')
            before = copy.deepcopy(mod.manager.state)
            fresh = stories.module(root).StoryManager(mod.manager.path)
            fresh.acknowledge_direct([result['story_ack']])
            self.assertEqual(fresh.state, before)
            self.assertNotIn(result['story_ack']['token'], fresh.pending_direct)

    def test_malformed_envelopes_never_release_nested_actions(self):
        for root in (stories.DEV, stories.WORKSHOP):
            mod = stories.module(root)
            malformed = ['[choices:{bad "text":"[action:goto:beach]"}]',
                         '[choices {bad "text":"[action:goto:beach]"}]',
                         '[choices:{bad "text":"escaped \\\" ] [action:goto:beach]"}]',
                         '[choices:{bad "options":[[action:goto:beach]]}]',
                         '[choices:{bad "text":"' + 'x' * (mod.LIMIT + 1) + '[action:goto:beach]"}]']
            for tag in malformed:
                for suffix in (' [emotion:normal]', ' [action:goto:library]'):
                    clean, options = mod.parse_choices('Hello ' + tag + suffix)
                    self.assertEqual(' '.join(clean.split()), 'Hello' + suffix, (root, tag))
                    self.assertIsNone(options)
            for tag in ('[choices:{bad "text":"[action:goto:beach]"}',
                        '[choices:{bad [action:goto:beach]',
                        '[choices:unfinished [action:goto:beach]'):
                self.assertEqual(mod.parse_choices('Hello ' + tag), ('Hello', None))
            self.assertEqual(mod.parse_choices('Hello [choices ordinary prose continues'),
                             ('Hello ordinary prose continues', None))

    def test_disabled_actual_chat_strips_malformed_choices_before_action_parser(self):
        for root in (stories.DEV, stories.WORKSHOP):
            fixture, mod = self.setup_manager(root)
            env, llm, conversation, modules = fixture.endpoint_env(root, mod, False)
            env['normalize_location'] = lambda value: value
            llm.chat.return_value = 'Hello [choices:{bad "text":"[action:goto:beach]"}] [action:goto:library]'
            with patch.dict(sys.modules, modules):
                result = env['chat'](dict(character='un', text='пойдём в библиотеку'))
            self.assertNotIn('choices', result)
            self.assertEqual(result['reply'], 'Hello')
            self.assertEqual(result.get('goto'), 'library')
            self.assertEqual(conversation.add_exchange.call_args.args[2], 'Hello')

    def test_client_menu_queue_cancel_and_standard_payload(self):
        for root in ROOTS:
            env = clothing.ClothingTests().environment(root)
            load(os.path.join(root, "es_ai_api.rpy"), env, ["es_ai_sanitize_text", "es_ai_story_choices_record",
                "es_ai_story_choices_menu", "es_ai_story_input_take", "es_ai_chat_async"])
            env.update(ES_AI_STORY_INPUT=dict(pending=None, selection=None, choice=None), ES_AI_FREE_SCENE=[True])
            offer = dict(token="a" * 36, version=4, options=OPTIONS)
            calls = []
            env["renpy"].display_menu = lambda items, **kw: calls.append((items, kw)) or "help"
            env["es_ai_story_choices_record"](offer)
            self.assertFalse(calls)
            env["es_ai_story_choices_menu"]()
            self.assertEqual(calls[0][0][-1][1], ("custom",))
            self.assertEqual(env["es_ai_story_input_take"](), "Yes")
            self.assertIsNone(env["es_ai_story_input_take"]())
            sent = []
            env.update(es_ai_delivery_flush=lambda: None, es_ai_request_trace=lambda *a: {},
                       es_ai_log=lambda *a: None, es_ai_clock_begin=lambda **kw: 1,
                       es_ai_chat_active=[True], es_ai_public_record=lambda *a: None,
                       es_ai_clock_snapshot=lambda: {}, es_ai_public_snapshot=lambda: [],
                       es_ai_story_ack_snapshot=lambda: [], es_ai_location_context=lambda: "square",
                       es_ai_scene_snapshot=lambda *a: {}, es_ai_run_async=lambda kind, fn: fn(),
                       es_ai_http=lambda path, payload: sent.append((path, payload)) or dict(ok=True))
            env["es_ai_chat_async"]("un", "Yes")
            self.assertEqual(sent[0][0], "/chat")
            self.assertEqual(sent[0][1]["text"], "Yes")
            self.assertEqual(sent[0][1]["story_choice"], dict(token="a" * 36, version=4, id="help"))
            env["es_ai_story_choices_record"](offer)
            env["renpy"].display_menu = lambda *a, **kw: ("custom",)
            env["es_ai_story_choices_menu"]()
            self.assertIsNone(env["es_ai_story_input_take"]())
            self.assertIsNone(env["ES_AI_STORY_INPUT"]["choice"])

    def test_delivery_callback_only_and_full_group_ordering(self):
        helper = delivery.DeliveryTests()
        for root in ROOTS:
            import tempfile
            with tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                env, events, acks = helper.speech_env(root, directory)
                collected = []
                env["es_ai_story_choices_record"] = collected.append
                speaker = delivery.DisplayCharacter(env["config"], fail=True)
                with self.assertRaises(RuntimeError):
                    env["es_ai_delivery_say"](speaker, "Hi", "un", "Hi", None, {"token": "x"})
                self.assertFalse(collected)
                speaker = delivery.DisplayCharacter(env["config"])
                env["es_ai_delivery_say"](speaker, "Hi", "un", "Hi", None, {"token": "x"})
                self.assertEqual(collected, [{"token": "x"}])
            with open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8") as stream:
                source = stream.read()
            block = source.split("label es_ai_chat_input:", 1)[1].split("label es_ai_chat_stt:", 1)[0]
            self.assertLess(block.index("es_ai_try_cameo"), block.index("es_ai_story_choices_menu"))
            self.assertLess(block.index("es_ai_delivery_flush"), block.index("es_ai_story_choices_menu"))

    def test_actual_chat_selection_trace_and_empty_failure(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture, mod = self.setup_manager(root)
            env, llm, conversation, modules = fixture.endpoint_env(root, mod, True)
            modules["config_loader"].cfg["story_events"]["choices_enabled"] = True
            offer = self.offer(mod)
            selection = dict(token=offer["token"], version=offer["version"], id="help")
            before = copy.deepcopy(mod.manager.state)
            with patch.dict(sys.modules, modules):
                llm.chat.return_value = '(normal) Let us plan. [story:{"status":"active"}]'
                result = env["chat"](dict(character="un", text="Yes", story_choice=selection))
                self.assertEqual(mod.manager.state, before)
                self.assertIn("story_ack", result)
                self.assertEqual(llm.chat.call_args.args[0][-1], dict(role="user", content="Yes"))
                self.assertIn("CURRENT SELECTED BRANCH", llm.chat.call_args.args[0][0]["content"])
                self.assertEqual(conversation.add_exchange.call_args.args[1], "Yes")
                mod.manager.acknowledge_direct([result["story_ack"]])
                self.assertEqual(mod.manager.state["decisions"], [OPTIONS[0]])

    def test_overdue_initial_offer_choices_in_same_chat_generation(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture = stories.StoryTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            mod = stories.module(root)
            mod.manager = fixture.manager(mod)
            mod.manager._load()
            mod.manager.state.update(turns=16, version=16)
            env, llm, _, modules = fixture.endpoint_env(root, mod, True)
            modules['config_loader'].cfg['story_events'].update(intensity='high', choices_enabled=True)
            llm.chat.return_value = ('Will you help? [story:{"status":"offered","title":"Signal",'
                                     '"summary":"Inspect a faulty signal"}] [choices:' +
                                     json.dumps(dict(options=OPTIONS)) + ']')
            with patch.dict(sys.modules, modules):
                result = env['chat'](dict(character='un', text='Continue'))
            self.assertEqual(result['choices']['options'], OPTIONS)
            self.assertEqual(mod.manager.state['status'], 'inactive')
            mod.manager.acknowledge_direct([result['story_ack']])
            self.assertEqual(mod.manager.state['status'], 'offered')
            self.assertFalse(mod.manager.state['offer_due'])
            llm.chat.assert_called_once()
            prompt = llm.chat.call_args.args[0][0]['content']
            self.assertIn('act as the plot proposer', prompt)
            self.assertIn('not only after acceptance', prompt)
            self.assertNotIn('story:', result['reply'])

    def test_overdue_direct_offer_choices_budget_and_ack_only_commit(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture = stories.StoryTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            mod = stories.module(root)
            mod.manager = fixture.manager(mod)
            mod.manager._load()
            mod.manager.state.update(turns=16, version=16)
            env, llm, _, modules = fixture.endpoint_env(root, mod, True)
            modules['config_loader'].cfg['story_events'].update(intensity='high', choices_enabled=True)
            env['resolve_direct_address'] = lambda *a: ['sl']
            env['scene_diagnostics'] = lambda *a: dict(origin='chat', status='ok', address_id='sl', address_reason='name')
            with patch.dict(sys.modules, modules):
                routed = env['chat'](dict(character='un', text='Slavya, continue'))
                llm.chat.assert_not_called()
                payload = dict(character='sl', active_id='un', player_text='Slavya, continue',
                               story_token=routed['story_token'])
                before = copy.deepcopy(mod.manager.state)
                llm.chat.return_value = 'Ordinary reply'
                env['cameo'](dict(character='sl', player_text='Continue'))
                self.assertEqual(llm.chat.call_args.kwargs['override_max_tokens'], 100)
                llm.chat.reset_mock()
                llm.chat.return_value = ('Will you help? [story:{"status":"offered","title":"Signal",'
                                         '"summary":"Inspect a faulty signal"}] [choices:' +
                                         json.dumps(dict(options=OPTIONS)) + ']')
                result = env['cameo'](payload)
                llm.chat.assert_called_once()
                self.assertEqual(llm.chat.call_args.kwargs['override_max_tokens'], 600)
                self.assertEqual(result['choices']['options'], OPTIONS)
                self.assertEqual(mod.manager.state, before)
                self.assertIsNone(mod.manager.latest_choice)
                mod.manager.acknowledge_direct([result['story_ack']])
                self.assertEqual(mod.manager.state['status'], 'offered')
                self.assertEqual(mod.manager.state['turns'], 17)
                self.assertFalse(mod.manager.state['offer_due'])
                self.assertIsNotNone(mod.manager.latest_choice)

    def test_direct_choices_only_become_current_after_ack(self):
        for root in existing_paths((stories.DEV, stories.WORKSHOP)):
            fixture, mod = self.setup_manager(root)
            cfg = types.SimpleNamespace(cfg=dict(story_events=dict(enabled=True, choices_enabled=True)))
            key = mod.manager.direct_request(self.token(mod.manager), "Slavya, details?", ["sl"], "un")
            payload = dict(story_token=key, active_id="un", player_text="Slavya, details?")
            with patch.dict(sys.modules, config_loader=cfg):
                result = mod.direct_delivery(payload, "sl", None, "Will you help?", OPTIONS)
                self.assertIn("choices", result)
                self.assertIsNone(mod.manager.latest_choice)
                mod.manager.acknowledge_direct([result["story_ack"]])
                value = result["choices"]
                self.assertIsNotNone(mod.manager.select_choice(dict(token=value["token"], version=value["version"], id="help"), "Yes"))


if __name__ == "__main__":
    unittest.main()
