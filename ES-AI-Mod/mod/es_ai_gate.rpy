# -*- coding: utf-8 -*-
# AI Совёнок — интерактивная «калитка» в главном меню.
#
# Две PNG: обычная (gate_idle.png) и при наведении курсора (gate_hover.png).
# Наведение — по альфа-каналу PNG (focus_mask): прозрачные места не реагируют.
# Клик — запуск AI-мода. Свои картинки кладите в game/mods/es_ai/gate/.
#
# Позиция/масштаб: ES_GATE_XALIGN / YALIGN / ZOOM ниже.
#
# Механика: меню ES 1.6 — игровой контекст с циклом в script.rpy
# (строки ~49590-49602), оверлеи там подавлены, поэтому экран калитки
# показываем сами из interact-колбэка на слое "screens" (перепоказ каждый
# интеракт держит калитку поверх экрана меню).

init -10 python:
    ES_GATE_IDLE = "mods/es_ai/gate/gate_idle.png"
    ES_GATE_HOVER = "mods/es_ai/gate/gate_hover.png"
    ES_GATE_XALIGN = 0.50    # картинка 1920x1080 — по центру, совпадает с фоном меню
    ES_GATE_YALIGN = 0.50
    ES_GATE_ZOOM = 1.0
    ES_GATE_HOVER_OPENS = "es_ai"
    ES_GATE_MENU_FILE = "script.rpy"
    ES_GATE_MENU_LINES = (49590, 49602)   # цикл главного меню ES 1.6

init 10 python:
    ES_GATE_MENU_WAS_SHOWN = [False]

    def es_ai_menu_hide():
        """Вход в мод из главного меню: убрать экран меню, чтобы не закрывал мод."""
        try:
            if renpy.get_screen("main_menu") is not None:
                renpy.hide_screen("main_menu")
                ES_GATE_MENU_WAS_SHOWN[0] = True
        except Exception:
            pass

    def es_ai_menu_restore():
        try:
            if ES_GATE_MENU_WAS_SHOWN[0]:
                renpy.show_screen("main_menu")
                ES_GATE_MENU_WAS_SHOWN[0] = False
        except Exception:
            pass

init 10 python:
    ES_GATE_AVAILABLE = (renpy.loadable(ES_GATE_IDLE)
                         and renpy.loadable(ES_GATE_HOVER))
    if ES_GATE_AVAILABLE:
        es_ai_log("menu gate enabled")

    def _es_gate_monitor():
        """Калитка видна, пока на экране главное меню игры."""
        try:
            want = ES_GATE_AVAILABLE and (renpy.get_screen("main_menu") is not None)
            shown = renpy.get_screen("es_ai_gate") is not None
            if want and not shown:
                renpy.show_screen("es_ai_gate", _layer="screens")
            elif not want and shown:
                renpy.hide_screen("es_ai_gate")
        except Exception:
            pass

    config.interact_callbacks.append(_es_gate_monitor)

screen es_ai_gate():
    if ES_GATE_AVAILABLE:
        imagebutton:
            idle Transform(ES_GATE_IDLE, zoom=ES_GATE_ZOOM)
            hover Transform(ES_GATE_HOVER, zoom=ES_GATE_ZOOM)
            focus_mask True
            hover_sound "mods/es_ai/gate/sov.mp3"
            action Jump(ES_GATE_HOVER_OPENS)
            xalign ES_GATE_XALIGN
            yalign ES_GATE_YALIGN
