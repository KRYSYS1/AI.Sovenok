"""Night beach policy in both installations, without API or userdata writes."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import unittest
import os
import subprocess
from unittest.mock import patch

from test_cameo_clothing import ROOTS
import test_clothing_long_session as long_session


class NightBeachTests(unittest.TestCase):
    def environment(self, root):
        env = long_session.ClothingLongSessionTests().environment(root)
        env["ES_AI_LOC_CUR"][0] = "beach"
        env["ES_AI_TIME"][0] = "night"
        env["ES_AI_CLOCK"].update(enabled=False, minutes=None)
        env["ES_AI_ROMANCEABLE"] = ["sl", "un", "mi", "dv", "mt"]
        env["es_ai_cameo_adult_home_ids"] = lambda: {"sl", "mt"}
        return env

    def test_defaults_boundaries_and_clock_fallback(self):
        for root in ROOTS:
            env = self.environment(root)
            for minutes, expected in ((1319, "swim"), (1320, None), (0, None), (359, None), (360, "swim")):
                env["ES_AI_CLOCK"].update(enabled=True, minutes=minutes)
                self.assertEqual(env["es_ai_current_dress"](), expected)
                self.assertEqual(env["es_ai_cameo_dress"](), expected)
            for invalid in (None, "22:00", -1, 1440, True):
                env["ES_AI_CLOCK"]["minutes"] = invalid
                self.assertIsNone(env["es_ai_default_dress"]())
            env["ES_AI_LOC_CUR"][0] = "island"
            self.assertEqual(env["es_ai_default_dress"](), "swim")
            env["ES_AI_LOC_CUR"][0] = "sl_room"
            self.assertIsNone(env["es_ai_default_dress"]())
            self.assertEqual(env["es_ai_cameo_home_reason"]("sl"), "night_home")

    def test_refresh_transition_and_authorized_outfits(self):
        for root in ROOTS:
            env = self.environment(root)
            env["ES_AI_TIME"][0] = "day"
            env["es_ai_apply_actions"]({"dress": "swim"}, "сидим болтаем")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            env["ES_AI_SHOWN"][1].update(dress="swim", dress_reason="location", dress_location="beach")
            env["ES_AI_SHOWN"][2].update(dress="swim", dress_reason="player", dress_location="beach")
            env["es_ai_refresh_girls"]()
            layout = env["ES_AI_GIRL_LAYOUT"][1].copy()
            env["ES_AI_TIME"][0] = "night"
            with patch.object(env["_es_random"], "random", side_effect=AssertionError("reroll")):
                for _ in range(4):
                    env["es_ai_refresh_girls"]()
            self.assertEqual(env["ES_AI_GIRL_LAYOUT"][1], layout)
            self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal pioneer")
            self.assertIsNone(env["ES_AI_SHOWN"][1]["dress"])
            self.assertEqual(env["ES_AI_SHOWN"][2]["dress"], "swim")
            env["es_ai_set_dress"]("swim")
            env["es_ai_refresh_girls"]()
            self.assertEqual(env["ES_AI_SHOWN"][0]["tag"], "sl normal swim")
            env["ES_AI_TIME"][0] = "day"
            env["es_ai_refresh_girls"]()
            self.assertEqual(env["ES_AI_SHOWN"][1]["dress"], "swim")

    def test_negative_swimming_and_targeted_request(self):
        for root in ROOTS:
            for text in ("купаться не будем", "не будем купаться", "не хочу купаться", "купатьсянебудем", "небудемкупаться", "нехочукупаться"):
                env = self.environment(root)
                env["es_ai_set_dress"]("swim")
                env["es_ai_apply_actions"]({"dress": "swim"}, text)
                self.assertEqual(env["ES_AI_DRESS"][0], "cover")
            env = self.environment(root)
            env["es_ai_apply_actions"]({"dress": "swim"}, "Лена, надень купальник, купаться не будем")
            self.assertIsNone(env["ES_AI_DRESS"][0])
            self.assertEqual(env["ES_AI_SHOWN"][1]["dress"], "swim")

    def test_romance_requires_current_intent_reply_clothing_and_adult(self):
        for root in ROOTS:
            for player, answer, expected in (
                ("сидим болтаем", "Да, надену купальник", None),
                ("обнимемся", "Да, обнимемся", None),
                ("романтика", "Да, надену купальник", None),
                ("обнимемся", "Нет, не хочу", None),
                 ("обнимемся", "Да, хочу, надену купальник", "swim")):
                env = self.environment(root)
                env["ES_AI_SHOWN"][:] = [dict(id="sl", emo="normal")]
                env["es_ai_apply_actions"]({"dress": "swim", "reply": answer}, player)
                self.assertEqual(env["ES_AI_DRESS"][0], expected)
            for cid in ("us", "uv", "sl"):
                env = self.environment(root)
                env["ES_AI_LOC_LAST_CHAR"][0] = cid
                env["es_ai_cameo_adult_home_ids"] = lambda: set()
                self.assertFalse(env["es_ai_beach_romantic_clothing"]("обнимемся", "Да, хочу, надену купальник"))

    def test_privacy_and_affection_never_infer_an_outfit(self):
        for root in ROOTS:
            for location in ("un_room", "library", "square", "beach"):
                for phase in ("day", "sunset", "night"):
                    for text in ("давай останемся наедине", "хочу побыть наедине с Мику",
                                 "Славя я хочу побыть наедине с Мику", "поцелуй меня",
                                 "обнимемся", "люблю тебя", "романтика", "только мы вдвоём"):
                        with self.subTest(root=root, location=location, phase=phase, text=text):
                            env = self.environment(root)
                            env["ES_AI_LOC_CUR"][0] = location
                            env["ES_AI_TIME"][0] = phase
                            loc = env["es_ai_location"]()
                            if "наедине" in text:
                                self.assertFalse(env["es_ai_is_romantic_moment"]("sl", text, "Да"))
                            self.assertIsNone(env["es_ai_dress_from_context"](text, "Да, поцелую", loc))
                            env["es_ai_apply_actions"]({"dress": None, "reply": "Да, поцелую"}, text)
                            self.assertIsNone(env["ES_AI_DRESS"][0])
                            env["es_ai_apply_actions"]({"dress": "swim"}, text)
                            self.assertIsNone(env["ES_AI_DRESS"][0])

    def test_explicit_addressed_outfits_still_override_context(self):
        for root in ROOTS:
            for text, expected in (("Славя, надень форму", "cover"),
                                   ("Славя, надень платье", "dress"),
                                   ("Славя, надень купальник", "swim")):
                env = self.environment(root)
                env["ES_AI_LOC_CUR"][0] = "un_room"
                self.assertEqual(env["es_ai_dress_from_context"](text, "", env["es_ai_location"]()), expected)
                env["es_ai_apply_actions"]({}, text)
                self.assertEqual(env["ES_AI_DRESS"][0], expected)
            env = self.environment(root)
            env["es_ai_apply_actions"]({"dress": "sport"}, "Славя, надень спортивную одежду")
            self.assertEqual(env["ES_AI_DRESS"][0], "sport")

    def test_python2_future_flag_executes_policy(self):
        exe = os.path.join(GAME_ROOT, "lib/windows-i686/python.exe")
        if not os.path.isfile(exe):
            self.skipTest("Bundled Python 2 unavailable")
        code = r'''import ast,io,re,textwrap,sys,os,__builtin__,__future__
flags=__future__.unicode_literals.compiler_flag
e={'_es_ai_cameo_builtins':__builtin__}
names=('es_ai_default_dress','es_ai_clothing_night','es_ai_no_swimming','es_ai_beach_romantic_clothing','es_ai_current_dress','es_ai_cameo_dress','es_ai_cameo_clothing_request','es_ai_cameo_home_reason','es_ai_cameo_adult_home_ids','es_ai_clothing_refused')
for filename in ('es_ai_locations.rpy','es_ai_cameo.rpy'):
    with io.open(os.path.join(sys.argv[1],filename),encoding='utf-8') as stream:
        source=stream.read().lstrip(u'\ufeff')
    for block in re.split(r'^init [^\n]*python:\s*\n',source,flags=re.M)[1:]:
        block='\n'.join(line for line in block.splitlines() if not line.strip() or line.startswith((' ','\t')))
        tree=compile(textwrap.dedent(block),filename,'exec',ast.PyCF_ONLY_AST|flags,True)
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        exec compile(ast.Module(body=nodes),filename,'exec',flags,True) in e
e.update(ES_AI_CLOCK={'enabled':True,'minutes':1320},ES_AI_TIME=['day'],ES_AI_LOC_CUR=['beach'],ES_AI_DRESS=[None],ES_AI_PARTY=[False],ES_AI_CAMEO_PLAYER_TEXT=[''],ES_AI_LOC_LAST_CHAR=['sl'],ES_AI_ROMANCEABLE=['sl'],ES_AI_CAMEO_HOMES={})
e['es_ai_location']=lambda: {'id':'beach','dress':'swim','romantic':True}
e['ES_AI_SERVER_DIR']=os.path.join(os.path.dirname(sys.argv[1]) if os.path.basename(sys.argv[1])=='mod' else sys.argv[1],'server')
e['ES_AI_CAMEO_HOMES']={'sl':'sl_room','us':'dv_room','uv':'unknown'}
e['ES_AI_SHOWN']=[{'id':'sl'}]
assert e['es_ai_cameo_clothing_request']('sl',u'\u0432 \u0431\u0438\u043a\u0438\u043d\u0438 \u043f\u0435\u0440\u0435\u043e\u0434\u0435\u043d\u044c\u0441\u044f',True)=='swim'
assert e['es_ai_cameo_clothing_request']('sl',u'\u0432 \u043a\u0443\u043f\u0430\u043b\u044c\u043d\u0438\u043a \u043d\u0435 \u043f\u0435\u0440\u0435\u043e\u0434\u0435\u0432\u0430\u0439\u0441\u044f',True) is None
assert 'sl' in e['es_ai_cameo_adult_home_ids']()
assert not set(['us','uv']) & e['es_ai_cameo_adult_home_ids']()
assert e['es_ai_current_dress']() is None
record={'id':'sl','dress_reason':'location','dress_location':'beach'}
assert e['es_ai_cameo_dress'](None,'swim',record) is None
record['dress_reason']='player'
assert e['es_ai_cameo_dress'](None,'swim',record)=='swim'
assert e['es_ai_no_swimming'](u'\u043d\u0435 \u0431\u0443\u0434\u0435\u043c \u043a\u0443\u043f\u0430\u0442\u044c\u0441\u044f')
assert e['es_ai_beach_romantic_clothing'](u'\u043e\u0431\u043d\u0438\u043c\u0435\u043c\u0441\u044f',u'\u0434\u0430, \u0445\u043e\u0447\u0443, \u043d\u0430\u0434\u0435\u043d\u0443 \u043a\u0443\u043f\u0430\u043b\u044c\u043d\u0438\u043a')
e['ES_AI_CLOCK']['minutes']=360
assert e['es_ai_current_dress']()=='swim'
print('Python 2 unicode_literals clothing policy passed')
'''
        for root in ROOTS:
            result = subprocess.run([exe, "-B", "-c", code, root], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
