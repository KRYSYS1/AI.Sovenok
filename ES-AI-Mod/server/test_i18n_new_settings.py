"""Offline translation checks; never import settings or access user configs/APIs."""
from test_paths import WORKSHOP_ROOT, GAME_ROOT, TEMP as TEST_TEMP, existing_paths
import ast
import itertools
from pathlib import Path
import re
import types
import unittest
from unittest.mock import Mock, mock_open


SERVERS = (Path(__file__).resolve().parent,) + existing_paths((Path(WORKSHOP_ROOT) / "server",))
CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def tree(path):
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def extract(nodes, env):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "offline-i18n", "exec"), env)


class SettingsI18nTests(unittest.TestCase):
    def environment(self, server):
        translations = tree(server / "ui_i18n.py")
        i18n = {}
        extract([n for n in translations.body if isinstance(n, ast.FunctionDef) or
                 isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EN"
                                                   for t in n.targets)], i18n)
        settings = tree(server / "settings_window.py")
        env = dict(ui_i18n=types.SimpleNamespace(**i18n), ui_lang=["ru"])
        extract([n for n in settings.body if isinstance(n, ast.FunctionDef) and n.name == "tr"], env)
        return settings, env, i18n

    def test_immersion_literal_coverage(self):
        for server in SERVERS:
            settings, env, i18n = self.environment(server)
            start = next(n.lineno for n in ast.walk(settings) if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "chars_path" for t in n.targets))
            end = next(n.lineno for n in ast.walk(settings) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "hist_targets" for t in n.targets))
            texts = {"\u041f\u043e\u0433\u0440\u0443\u0436\u0435\u043d\u0438\u0435"}
            for call in ast.walk(settings):
                if (isinstance(call, ast.Call) and start <= call.lineno < end and
                        isinstance(call.func, ast.Name) and
                        call.func.id in ("Txt", "Chip", "label", "ValueError", "set_status", "show_result", "tr")):
                    texts.update(n.value for arg in call.args for n in ast.walk(arg)
                                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                                 and CYRILLIC.search(n.value))
            for text in texts:
                with self.subTest(server=server, text=text):
                    self.assertIn(text, i18n["EN"])
                    self.assertEqual(i18n["tr"](text, "ru"), text)
                    self.assertNotRegex(i18n["tr"](text, "en"), CYRILLIC)
            self.assertEqual(i18n["tr"]("\u041f\u043e\u0433\u0440\u0443\u0436\u0435\u043d\u0438\u0435", "en"), "Immersion")
            self.assertEqual(i18n["tr"]("Показывать время", "en"), "Show time")
            self.assertEqual(i18n["tr"]("Показывать время", "ru"), "Показывать время")

    def test_constructors_dynamic_values_and_language_switch(self):
        for server in SERVERS:
            settings, env, i18n = self.environment(server)
            canvas = Mock()
            ids = itertools.count(1)
            for name in ("create_text", "create_image", "create_oval"):
                getattr(canvas, name).side_effect = lambda *a, **kw: next(ids)
            env.update(canvas=canvas, CREAM="cream", OUTLINE="outline", F="font",
                       OUT8=(), MANAGED=[], I18N_WIDGETS=[], _seq=[0],
                       measure=lambda text, font: len(text), pill=lambda *a, **kw: (None, 0),
                       CHIP_STYLES={"normal": (None, None, "ink", False)})
            extract([n for n in ast.walk(settings) if isinstance(n, ast.ClassDef)
                     and n.name in ("Managed", "Txt", "Chip")], env)
            texts = [key for key in i18n["EN"] if key in {
                "Погружение", "Появление других персонажей в локациях", "ГГ", "ЧАСТОТА ПОЯВЛЕНИЙ",
                "ФРАЗ ДО УХОДА", "ШАНС РЕПЛИКИ В РАЗГОВОРЕ", "РЕПЛИКИ В ТЕМУ (ПО КОНТЕКСТУ)",
                "Игровые часы", "Показывать время", "НАЧАЛО (ЧЧ:ММ)", "МИНУТ ЗА РЕПЛИКУ (0-120)",
                "Сюжетные события", "Редко", "Умеренно", "Активно",
                "Небольшие истории по контексту. Можно отказаться; без обязательных переходов.",
                "Установить время", "ИМЯ ГЛАВНОГО ГЕРОЯ", "ПЕРСОНАЖИ", "ХАРАКТЕР · PERSONA"}]
            for initial in ("ru", "en"):
                for kind in ("Txt", "Chip"):
                    for text in texts + ["-", "+", "25%", "2", "Лена"]:
                        with self.subTest(server=server, initial=initial, kind=kind, text=text):
                            env["ui_lang"][0] = initial
                            widget = env[kind](text)
                            self.assertEqual(canvas.create_text.call_args.kwargs["text"],
                                             i18n["tr"](text, initial))
                            for lang in ("en", "ru", "en"):
                                env["ui_lang"][0] = lang
                                widget.retranslate()
                                self.assertEqual(canvas.itemconfig.call_args.kwargs["text"],
                                                 i18n["tr"](text, lang))
                # The player chip stays independent of the separately editable name.
                append = next(n for n in ast.walk(settings) if isinstance(n, ast.Call)
                              and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
                              and isinstance(n.func.value, ast.Name) and n.func.value.id == "pr_chips")
                env.update(i=0, is_player=True, name="Алексей", prompt_targets=[("player", "Алексей", True)])
                source = eval(compile(ast.Expression(append.args[0].args[0]), "player-chip", "eval"), env)
                widget = env["Chip"](source)
                for lang, text in (("ru", "ГГ"), ("en", "MC")):
                    env["ui_lang"][0] = lang
                    widget.retranslate()
                    self.assertEqual(widget.text, text)
                env["prompt_targets"][0] = ("player", "Новое имя", True)
                widget.retranslate()
                self.assertEqual(widget.text, "MC")

    def test_existing_language_switch_retranslates_widgets(self):
        for server in SERVERS:
            settings, env, _ = self.environment(server)
            env.update(root=Mock(), I18N_WIDGETS=[Mock(), Mock()], CLIP_MENUS=[],
                       refresh_server_status=Mock(), layout=Mock())
            extract([n for n in ast.walk(settings) if isinstance(n, ast.FunctionDef)
                     and n.name == "apply_language"], env)
            for lang in ("en", "ru"):
                env["ui_lang"][0] = lang
                env["apply_language"]()
            for widget in env["I18N_WIDGETS"]:
                self.assertEqual(widget.retranslate.call_count, 2)

    def clock_environment(self, server, lang):
        settings, env, _ = self.environment(server)
        env["ui_lang"][0] = lang
        env.update(clock_time_var=Mock(), clock_step_var=Mock(), clock_on=[True],
                   clock_config_path=lambda: "offline-config.json", cfg={},
                   saved_state=[{}], refresh_save_btn=Mock(), _post=Mock(),
                   json=__import__("json"), open=mock_open(), status={},
                   canvas=Mock(), badge_txt=1, badge_dot=2, DOT_OK="ok", DOT_ERR="err",
                   DOT_IDLE="idle", layout_badge=Mock(), WIN_W=960)
        env["canvas"].winfo_width.return_value = 960
        extract([n for n in ast.walk(settings) if isinstance(n, ast.FunctionDef)
                 and n.name in ("clock_values", "clock_step", "save_all", "set_status")], env)
        env["clock_read_config"] = Mock(return_value={})
        env["clock_show_time"] = [True]
        env["clock_time_var"].get.return_value = "08:00"
        env["clock_step_var"].get.return_value = "5"
        return env
    def test_clock_validation_and_steps_bilingual(self):
        for server in SERVERS:
            for lang in ("ru", "en"):
                env = self.clock_environment(server, lang)
                for time, step, valid in (("00:00", "0", True), ("23:59", "120", True),
                        ("24:00", "5", False), ("08:60", "5", False), ("0800", "5", False),
                        ("08:00", "", False), ("08:00", "121", False), ("08:00", "1.5", False)):
                    with self.subTest(server=server, lang=lang, time=time, step=step):
                        env["clock_time_var"].get.return_value = time
                        env["clock_step_var"].get.return_value = step
                        self.assertEqual(env["clock_values"]() is not None, valid)
                        if not valid:
                            self.assertEqual(bool(CYRILLIC.search(env["status"]["msg"])), lang == "ru")
                for step, delta, expected in (("0", -1, "0"), ("120", 1, "120"), ("5", -1, "4")):
                    env["clock_step_var"].get.return_value = step
                    env["clock_step"](delta)
                    env["clock_step_var"].set.assert_called_with(expected)
                env["open"].assert_not_called()
                env["_post"].assert_not_called()

    def test_clock_literal_and_button_removed_bilingual(self):
        #_LABEL «Установить время» убрано: виджета с такой надписью больше нет,
        # остальные i18n-литералы часов продолжают переводиться.
        for server in SERVERS:
            settings, env, i18n = self.environment(server)
            literals = set()
            for call in ast.walk(settings):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and \
                        call.func.id in ("Txt", "Chip"):
                    for arg in call.args:
                        for n in ast.walk(arg):
                            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                                literals.add(n.value)
            self.assertNotIn(u"Установить время", literals)
            for text in ("Игровые часы", "НАЧАЛО (ЧЧ:ММ)", "МИНУТ ЗА РЕПЛИКУ (0-120)"):
                self.assertIn(text, i18n["EN"])
                self.assertNotRegex(i18n["tr"](text, "en"), CYRILLIC)

    def test_clock_phase_strings_still_translated(self):
        # Statuses of the removed apply_clock are gone; the remaining clock
        # literals keep their translations. Guards against re-adding the button
        # without i18n entries.
        for server in SERVERS:
            _, env, i18n = self.environment(server)
            for text in (u"Время установлено, сервер перечитал конфиг",
                         u"Не удалось установить время: %s"):
                self.assertNotIn(text, i18n["EN"])

    def test_clock_config_object_error_is_translated(self):
        for server in SERVERS:
            settings, env, _ = self.environment(server)
            env.update(clock_config_path=lambda: "offline-config.json", open=mock_open(read_data="[]"),
                       os=types.SimpleNamespace(path=types.SimpleNamespace(exists=lambda p: True)),
                       json=__import__("json"))
            extract([n for n in ast.walk(settings) if isinstance(n, ast.FunctionDef)
                     and n.name == "clock_read_config"], env)
            with self.assertRaises(ValueError) as error:
                env["clock_read_config"]()
            env["ui_lang"][0] = "en"
            self.assertEqual(env["tr"](str(error.exception)), "config.json must contain an object")


if __name__ == "__main__":
    unittest.main()
