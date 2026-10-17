"""Offline primary-role and sprite regressions for both installations."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import os
import io
import re
import subprocess
import textwrap
import unittest

import test_cameo_clothing as clothing
from test_cameo_clothing import ROOTS, load


class PrimarySwitchTests(unittest.TestCase):
    def environment(self, root):
        env = clothing.ClothingTests().environment(root)
        load(os.path.join(root, "es_ai.rpy"), env,
             {"es_ai_resolve_sprite", "es_ai_has_party_dress", "es_ai_fallback_emotion"})
        load(os.path.join(root, "es_ai_locations.rpy"), env)
        env["ES_AI_FREE_SCENE"][0] = True
        with io.open(os.path.join(root, "es_ai_chat.rpy"), encoding="utf-8-sig") as stream:
            pick = re.search(r"    def es_ai_pick_id\(cid\):\n(?:        .*\n)+", stream.read()).group()
        exec(compile(textwrap.dedent(pick), "<pick>", "exec"), env)
        env["ES_AI_CHARS"] = [(cid, cid, "") for cid in ("mz", "sl", "mi", "dv", "un", "mt", "us", "el")]
        env["ES_AI_HEIGHTS"] = {}
        env["ES_AI_LOC_CUR"][0] = "library"
        env["ES_AI_LOC_LAST_CHAR"][0] = "mz"
        env["ES_AI_LOC_LAST_EMO"][0] = "shy"
        env["ES_AI_DRESS"][0] = "swim"
        env["ES_AI_SHOWN"][:] = [{"id": "mz", "emo": "shy", "tag": "mz normal pioneer"}]
        env["ES_AI_RECENT_LINES"][:] = [{"who": "mz", "text": "Old romantic exchange"}]
        env["ES_AI_CAMEO_PLAYER_TEXT"][0] = "sl, put on a swimsuit"
        env["es_ai_location"] = lambda: env["ES_AI_LOCATION_INDEX"][env["ES_AI_LOC_CUR"][0]]
        env["Transform"] = lambda **kw: kw
        shown, logs, hidden = [], [], []
        env["renpy"].show = lambda tag, **kw: shown.append((tag, kw))
        env["renpy"].hide = hidden.append
        env["renpy"].notify = lambda message: logs.append(message)
        images = {cid + " normal pioneer" for cid, _, _ in env["ES_AI_CHARS"]}
        images.update({"sl normal swim", "sl normal dress", "un normal dress"})
        env["renpy"].has_image = lambda tag, exact=False: tag in images if exact else any(i.startswith(tag) for i in images)
        env["es_ai_log"] = logs.append
        env["_images"], env["_shown"], env["_logs"], env["_hidden"] = images, shown, logs, hidden
        return env

    def test_library_new_primary_and_repeated_reply(self):
        for root in ROOTS:
            env = self.environment(root)
            env["es_ai_pick_id"]("sl")
            self.assertEqual(env["ES_AI_LOC_CUR"][0], "library")
            self.assertEqual(env["ES_AI_LOC_LAST_CHAR"][0], "sl")
            self.assertEqual(env["ES_AI_LOC_LAST_EMO"][0], "normal")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal pioneer")
            self.assertFalse(env["ES_AI_RECENT_LINES"])
            self.assertEqual(env["ES_AI_CAMEO_PLAYER_TEXT"][0], "")
            self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"sl", "mz"})
            self.assertEqual([g["id"] for g in env["ES_AI_CAMEO_ACTIVE"]], ["mz"])
            env["es_ai_location_from_dialog"] = lambda *a: None
            env["es_ai_apply_actions"]({"dress": "swim", "reply": "I am in a swimsuit"}, "Hello")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            env["es_ai_set_dress"]("swim")
            env["es_ai_girl_enter"]("sl", "normal")
            self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal swim")
            self.assertEqual(env["ES_AI_DRESS"][0], "swim")

    def test_present_and_nearby_own_outfit(self):
        for root in ROOTS:
            for nearby in (False, True):
                env = self.environment(root)
                record = dict(id="sl", emo="normal", cameo=True, dress="swim",
                              dress_reason="player", dress_location="library", tag="sl normal swim")
                if nearby:
                    env["ES_AI_CAMEO_NEARBY"]["library"] = [record]
                else:
                    env["ES_AI_SHOWN"].append(record)
                    env["es_ai_cameo_register"]("sl", 0)
                env["ES_AI_CAMEO_NEARBY"]["square"] = [{"id": "mi", "dress": "sport"}]
                env["es_ai_pick_id"]("sl")
                self.assertEqual(env["ES_AI_DRESS"][0], "swim")
                self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal swim")
                self.assertIn("square", env["ES_AI_CAMEO_NEARBY"])
                self.assertNotIn("sl", [g["id"] for g in env["ES_AI_CAMEO_ACTIVE"]])
                self.assertFalse(env["ES_AI_SHOWN"][0].get("cameo"))

    def test_party_promote_keeps_company_without_inventing_event(self):
        for root in ROOTS:
            env = self.environment(root)
            env["ES_AI_PARTY"][0] = True
            env["ES_AI_SHOWN"].extend([
                dict(id="sl", emo="normal", cameo=True, dress="dress", dress_reason="party",
                     dress_location="library", tag="sl normal dress"),
                dict(id="mi", emo="normal", cameo=True, dress="sport")])
            env["es_ai_pick_id"]("sl")
            self.assertTrue(env["ES_AI_PARTY"][0])
            self.assertEqual(env["ES_AI_DRESS"][0], "dress")
            self.assertEqual({g["id"] for g in env["ES_AI_SHOWN"]}, {"mz", "sl", "mi"})
            self.assertEqual({tag.split()[0] for tag, _ in env["_shown"]}, {"mz", "sl", "mi"})
            env = self.environment(root)
            env["es_ai_pick_id"]("sl")
            self.assertFalse(env["ES_AI_PARTY"][0])

    def test_capacity_parks_excess_without_deleting_nearby(self):
        for root in ROOTS:
            env = self.environment(root)
            env["ES_AI_SHOWN"].extend(dict(id=cid, emo="normal", cameo=True, dress=None)
                                     for cid in ("mi", "dv", "un"))
            env["es_ai_pick_id"]("sl")
            self.assertEqual(len(env["ES_AI_SHOWN"]), 4)
            self.assertEqual(len(env["ES_AI_CAMEO_NEARBY"]["library"]), 1)
            self.assertEqual(env["ES_AI_SHOWN"][0]["id"], "sl")

    def test_safe_exact_fallback_and_diagnostic_dedup(self):
        for root in ROOTS:
            env = self.environment(root)
            env["_images"].remove("dv normal pioneer")
            env["_images"].update({"dv normal pioneer2", "mi normal swim", "mi normal body"})
            env["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal"),
                                     dict(id="mi", emo="normal", cameo=True, dress="sport"),
                                     dict(id="dv", emo="normal", cameo=True, dress="sport")]
            env["ES_AI_DRESS"][0] = None
            env["es_ai_refresh_girls"]()
            self.assertEqual([g["tag"] for g in env["ES_AI_SHOWN"]],
                             ["sl normal pioneer", "mi normal pioneer", "dv normal pioneer2"])
            self.assertEqual(len(env["_logs"]), 3)
            env["es_ai_refresh_girls"]()
            self.assertEqual(len(env["_logs"]), 3)
            env["ES_AI_SHOWN"][1]["focused"] = True
            env["es_ai_refresh_girls"]()
            self.assertEqual(len(env["_logs"]), 4)
            self.assertIn("exact_matches=", env["_logs"][-1])
            self.assertIn("zorder=", env["_logs"][-1])
            self.assertEqual(env["es_ai_resolve_sprite"]("mi", "normal", "body"), "mi normal pioneer")
            env["_images"].remove("mi normal pioneer")
            self.assertIsNone(env["es_ai_resolve_sprite"]("mi", "normal", "sport"))

    def test_python2_compiles_and_executes_clients(self):
        exe = os.path.join(GAME_ROOT, "lib/windows-i686/python.exe")
        if not os.path.isfile(exe):
            self.skipTest("Bundled Python 2 unavailable")
        code = '''import ast,io,re,textwrap,sys,os,random,__builtin__,__future__,json
flags=__future__.unicode_literals.compiler_flag if int(sys.argv[2]) else 0
class Stub: pass
class StoreDict(dict): pass
class StoreList(list): pass
r=Stub()
r.has_image=lambda tag,exact=False: tag in ['sl normal pioneer','mz normal pioneer']
r.show=lambda *a,**kw:None
r.hide=lambda *a:None
r.notify=lambda *a:None
e=dict(renpy=r,_es_random=random.Random(7),_es_ai_cameo_builtins=__builtin__,
       dict=StoreDict,list=StoreList,ES_AI_HEIGHTS={},Transform=lambda **kw:kw,es_ai_log=lambda *a:None)
for filename in ['es_ai.rpy','es_ai_cameo.rpy','es_ai_locations.rpy']:
    s=io.open(os.path.join(sys.argv[1],filename),encoding='utf-8').read().lstrip(u'\\ufeff')
    nodes=[]
    for block in re.split(r'^init [^\\n]*python:\\s*\\n',s,flags=re.M)[1:]:
        block='\\n'.join(line for line in block.splitlines() if not line.strip() or line.startswith((' ','\\t')))
        for n in compile(textwrap.dedent(block),filename,'exec',ast.PyCF_ONLY_AST | flags,1).body:
            if (isinstance(n,ast.FunctionDef) and (filename!='es_ai.rpy' or n.name in ('es_ai_resolve_sprite','es_ai_has_party_dress','es_ai_fallback_emotion'))) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('ES_AI_') and (filename!='es_ai.rpy' or t.id in ('ES_AI_EMOTIONS','ES_AI_EMOTION_RU','ES_AI_DRESSES')) for t in n.targets)):
                nodes.append(n)
    exec compile(ast.Module(body=nodes),filename,'exec',flags,1) in e
s=io.open(os.path.join(sys.argv[1],'es_ai_chat.rpy'),encoding='utf-8').read().lstrip(u'\\ufeff')
pick=re.search(r'    def es_ai_pick_id\\(cid\\):\\n(?:        .*\\n)+',s).group()
exec compile(textwrap.dedent(pick),'<pick>','exec') in e
e['ES_AI_CHARS']=[('mz','mz',''),('sl','sl','')]
e['ES_AI_SHOWN'][:]=[dict(id='mz',emo='normal')]
e['ES_AI_LOC_CUR'][0]='library'
e['ES_AI_DRESS'][0]='swim'
e['es_ai_read_cameo_settings']=lambda:dict(cameo_max_extra=6)
e['es_ai_pick_id']('sl')
assert e['ES_AI_DRESS'][0] is None
assert e['ES_AI_SHOWN'][0]['tag']=='sl normal pioneer'
assert e['ES_AI_LOC_LAST_CHAR'][0]=='sl'
assert e['es_ai_char_id']=='sl'
assert e['es_ai_who_name']=='sl'
e['renpy'].scene=lambda:None
for text in [u'нет',u'слыхал',u'Ладно, Юля иди в лагерь',u'он сказал: пошли на пляж',u'пойдём на пляж?']:
    assert e['es_ai_location_from_dialog'](text,u'Не пойдём через старый корпус. Я пойду по тропе') is None
assert e['es_ai_location_from_dialog'](u'нет, пойдём лучше на пляж',u'Старый корпус')=='beach'
assert e['es_ai_location_from_dialog'](u'пошли на пляж',u'Тропа')=='beach'
e['renpy'].with_statement=lambda *a:None
e['dissolve']=None
e['ES_AI_ROMANCEABLE']=set()
e['ES_AI_SHOWN'][:]=[dict(id='mz',emo='normal'),dict(id='sl',emo='normal',cameo=True)]
e['ES_AI_LOC_LAST_CHAR'][0]='mz'
e['ES_AI_LOC_CUR'][0]='library'
e['es_ai_read_cameo_settings']=lambda:dict(cameo_max_extra=6,scene_auto_primary=True)
e['es_ai_apply_actions'](dict(switch_primary='sl',goto='beach',travel_all=True,
    travel_with=[],cameo_aside=['mz']),u'Go to beach')
assert e['es_ai_char_id']=='sl'
assert e['ES_AI_LOC_LAST_CHAR'][0]=='sl'
assert e['ES_AI_LOC_CUR'][0]=='beach'
assert [g['id'] for g in e['ES_AI_SHOWN']]==['sl']
assert 'mz' in [g['id'] for g in e['ES_AI_CAMEO_NEARBY']['library']]
e['ES_AI_CHARS'].append(('el','el',''))
e['renpy'].has_image=lambda tag,exact=False: tag in ['mz normal pioneer','el normal pioneer']
e['ES_AI_CAMEO_NEARBY'].clear()
e['ES_AI_SHOWN'][:]=[dict(id='mz',emo='normal'),dict(id='el',emo='normal',cameo=True)]
e['ES_AI_LOC_LAST_CHAR'][0]='mz'
e['ES_AI_LOC_CUR'][0]='old_building'
response=json.loads(json.dumps(dict(id='el',switch_primary='el',travel_with=['mz'],travel_party=['el','mz'],cameo_aside=[])))
e['es_ai_apply_actions'](response,u'Go with us')
assert set(g['id'] for g in e['ES_AI_SHOWN'])==set(['mz','el'])
for dest in ['old_building_inside','mine']:
    response=json.loads(json.dumps(dict(id='el',goto=dest,travel_with=['mz'],travel_party=['el','mz'])))
    e['es_ai_apply_actions'](response,u'Continue together')
    assert e['ES_AI_LOC_CUR'][0]==dest
    assert set(g['id'] for g in e['ES_AI_SHOWN'])==set(['mz','el'])
    assert next(g for g in e['ES_AI_SHOWN'] if g['id']=='mz')['travel_party'] is True
e['es_ai_cameo_park']('mz',announce=False)
assert not any(g.get('travel_party') for g in e['ES_AI_SHOWN'])
assert not e['ES_AI_CAMEO_NEARBY']['mine'][0].get('travel_party')
e['ES_AI_SHOWN'][:]=[dict(id='el',emo='normal'),dict(id='mz',emo='normal',cameo=True,travel_party=True)]
e['ES_AI_LOC_LAST_CHAR'][0]='el'
e['ES_AI_LOC_CUR'][0]='old_building'
e['ES_AI_CAMEO_NEARBY'].clear()
response=json.loads(json.dumps(dict(id='el',privacy=True,goto='beach',scene_depart=['mz'],travel_party=[],travel_with=[],travel_all=False)))
e['es_ai_apply_actions'](response,u'Go to beach privately with you')
assert e['ES_AI_LOC_CUR'][0]=='beach'
assert e['ES_AI_LOC_LAST_CHAR'][0]=='el'
assert [g['id'] for g in e['ES_AI_SHOWN']]==['el']
assert not any(g.get('travel_party') for g in e['ES_AI_SHOWN'])
assert not e['ES_AI_CAMEO_NEARBY'].get('old_building')
assert not e['ES_AI_CAMEO_NEARBY'].get('beach')
assert 'mz' in e['ES_AI_SCENE_ABSENT']['old_building']
e['renpy'].has_image=lambda tag,exact=False: exact and tag in ['sl normal dress','sl normal pioneer','un normal dress','un normal pioneer','us normal dress','us normal pioneer','mt normal dress','mt normal pioneer']
e['ES_AI_CHARS']=[(c,c,'') for c in ('sl','un','us','mt')]
e['ES_AI_SHOWN'][:]=[dict(id='sl',emo='normal')]+[dict(id=c,emo='normal',cameo=True) for c in ('un','us','mt')]
e['ES_AI_LOC_LAST_CHAR'][0]='sl'
e['ES_AI_LOC_CUR'][0]='stage_big'
e['ES_AI_DRESS'][0]=None
e['es_ai_apply_actions'](__builtin__.dict(reply='Yes'),u'\u0438\u0434\u0451\u043c \u043d\u0430 \u043a\u043e\u043d\u0446\u0435\u0440\u0442')
assert e['ES_AI_PARTY'][0] is True
assert e['ES_AI_DRESS'][0]=='dress'
assert all(g['tag']==g['id']+' normal dress' for g in e['ES_AI_SHOWN'])
e['ES_AI_PARTY'][0]=False
e['ES_AI_DRESS'][0]=None
e['es_ai_apply_actions'](__builtin__.dict(reply='Yes'),u'\u0442\u0430\u043c \u043a\u043e\u043d\u0446\u0435\u0440\u0442, \u0434\u0430\u0432\u0430\u0439 \u043f\u0435\u0440\u0435\u043e\u0434\u0435\u043d\u0435\u043c\u0441\u044f \u0438 \u0432\u0441\u0442\u0440\u0435\u0442\u0438\u043c\u0441\u044f \u0443 \u0431\u043e\u043b\u044c\u0448\u043e\u0439 \u0441\u0446\u0435\u043d\u044b')
assert e['ES_AI_PARTY'][0] is True
assert e['ES_AI_DRESS'][0]=='dress'
e['es_ai_girl_enter']('sl','normal')
assert e['ES_AI_DRESS'][0]=='dress'
assert all(g['tag']==g['id']+' normal dress' for g in e['ES_AI_SHOWN'])
e['ES_AI_PARTY'][0]=False
e['ES_AI_DRESS'][0]=None
e['es_ai_apply_actions'](__builtin__.dict(dress='dress'),u'оденься в платье, там на концерте все собрались')
assert e['ES_AI_DRESS'][0]=='dress'
assert e['ES_AI_SHOWN'][0]['tag']=='sl normal dress'
e['es_ai_apply_actions'](__builtin__.dict(),u'Спокойной ночи')
assert e['ES_AI_DRESS'][0]=='dress'
e['ES_AI_CHARS'].append(('mi','mi',''))
e['ES_AI_SHOWN'].append(__builtin__.dict(id='mi',emo='normal',cameo=True))
e['es_ai_apply_actions'](__builtin__.dict(switch_primary='mi',cameo_aside=['sl']),u'Славя оставь нас. Мику, пойдём прогуляемся')
assert e['es_ai_char_id']=='mi'
assert e['ES_AI_LOC_CUR'][0]=='stage_big'
assert 'sl' in [g['id'] for g in e['ES_AI_CAMEO_NEARBY']['stage_big']]
e['es_ai_apply_actions'](__builtin__.dict(),u'Привет')
assert e['ES_AI_LOC_LAST_CHAR'][0]=='mi'
e['ES_AI_CHARS'].append(('el','el',''))
for text in [u'Славя, оставь нас',u'я дальше пойду с Электроником',u'Электроник, оставим Женю.',u'Электроник, пошли к тебе.',u'пошли, Электроник!']:
    active='mz' if text.startswith((u'Электроник',u'пошли,')) else 'sl'
    e['ES_AI_SHOWN'][:]=[dict(id=active,emo='normal'),dict(id='el',emo='normal',cameo=True)]
    e['ES_AI_LOC_LAST_CHAR'][0]=active
    e['ES_AI_LOC_CUR'][0]='club_room'
    response=json.loads(json.dumps(dict(id='el',switch_primary='el',cameo_aside=[active],reply=u'Пойдём на пляж',travel_with=[])))
    e['es_ai_apply_actions'](response,text)
    assert e['es_ai_char_id']=='el'
    assert e['es_ai_who_name']=='el'
    assert e['ES_AI_LOC_LAST_CHAR'][0]=='el'
    assert e['ES_AI_LOC_CUR'][0]=='club_room'
    assert [g['id'] for g in e['ES_AI_SHOWN']]==['el']
for active in ('sl','mi'):
    e['ES_AI_SHOWN'][:]=[dict(id=active,emo='normal')]+[dict(id=c,emo='normal',cameo=True) for c in ('sl','mi','un') if c!=active]
    e['ES_AI_CAMEO_NEARBY'].clear()
    e['ES_AI_LOC_LAST_CHAR'][0]=active
    e['ES_AI_LOC_CUR'][0]='un_room'
    e['ES_AI_DRESS'][0]=None
    response=json.loads(json.dumps(dict(id='mi',privacy=True,scene_depart=['sl','un'],reply=u'Пойдём на пляж')))
    if active!='mi': response['switch_primary']='mi'
    e['es_ai_apply_actions'](response,u'Славя, я хочу побыть наедине с Мику' if active=='sl' else u'Мику, хочу побыть наедине с тобой')
    assert e['ES_AI_LOC_LAST_CHAR'][0]=='mi'
    assert e['ES_AI_LOC_CUR'][0]=='un_room'
    assert [g['id'] for g in e['ES_AI_SHOWN']]==['mi']
    assert e['ES_AI_CAMEO_NEARBY']['un_room']==[]
    assert set(e['ES_AI_SCENE_ABSENT']['un_room'])==set(['sl','un'])
    assert e['ES_AI_DRESS'][0] is None
    e['es_ai_apply_actions'](json.loads('{}'),u'Пока')
    assert e['ES_AI_LOC_LAST_CHAR'][0]=='mi'
e['ES_AI_ROMANCEABLE']=['sl','mi']
e['ES_AI_TIME'][0]='night'
e['ES_AI_CLOCK'].update(enabled=True,minutes=59)
e['ES_AI_PARTY'][0]=False
for active in ('sl','mi'):
    e['ES_AI_LOC_LAST_CHAR'][0]=active
    e['es_ai_char_id']=active
    e['ES_AI_DRESS'][0]=None
    for text in (u'давай останемся наедине',u'хочу побыть наедине с Мику',u'Славя я хочу побыть наедине с Мику',u'поцелуй меня',u'обнимемся'):
        assert e['es_ai_dress_from_context'](text,u'Да',e['ES_AI_LOCATION_INDEX']['un_room']) is None
assert e['es_ai_location_from_dialog'](u'не идём на пляж',u'идём на пляж') is None
e['ES_AI_SHOWN'][:]=[dict(id='mz',emo='normal')]
e['ES_AI_CAMEO_NEARBY'].clear()
e['ES_AI_LOC_LAST_CHAR'][0]='mz'
e['ES_AI_LOC_CUR'][0]='library'
e['renpy'].has_image=lambda tag,exact=False: tag in ['mz normal pioneer','el normal pioneer']
e['es_ai_cameo_on']=lambda:True
e['ES_AI_FREE_SCENE'][0]=True
response=json.loads(json.dumps(dict(id='el',goto='club_room',visit_primary=dict(id='el',location_id='club_room'))))
e['es_ai_apply_actions'](response,u'оставайся а я к Электронику пойду')
assert e['ES_AI_LOC_CUR'][0]=='club_room'
assert e['es_ai_char_id']=='el'
assert [g['id'] for g in e['ES_AI_SHOWN']]==['el']
assert [g['id'] for g in e['ES_AI_CAMEO_NEARBY']['library']]==['mz']
e['ES_AI_ACTIVITY_PENDING']={'sl':{}}
e['ES_AI_STORY_INPUT']={'pending':u'old input','choice':{}}
e['es_ai_apply_actions'](json.loads('{"end_conversation":true,"goto":"beach"}'),u'\u041f\u043e\u043a\u0430')
e['es_ai_detach_primary']()
assert e['ES_AI_LOC_LAST_CHAR'][0] is None
assert e['es_ai_char_id'] is None
assert e['ES_AI_LOC_CUR'][0]=='club_room'
assert not e['ES_AI_SHOWN'] and not e['ES_AI_CAMEO_ACTIVE']
assert not e['ES_AI_ACTIVITY_PENDING']
assert e['ES_AI_STORY_INPUT']=={'pending':None,'choice':None}
e['es_ai_pick_id']('el')
assert e['ES_AI_LOC_LAST_CHAR'][0]=='el'
print('Python 2 primary handoff and detach passed flags=%s' % flags)
'''
        for root in ROOTS:
            for flags in (0, 1):
                subprocess.check_call([exe, "-B", "-c", code.encode("ascii", "backslashreplace").decode("ascii"), root, str(flags)])


if __name__ == "__main__":
    unittest.main()
