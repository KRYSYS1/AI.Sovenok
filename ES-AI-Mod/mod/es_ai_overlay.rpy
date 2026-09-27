# -*- coding: utf-8 -*-
# AI Совёнок — интеграция с новеллой:
#   * перехват всех реплик романа (контекст для AI + опциональная озвучка)
#   * горячая клавиша (по умолчанию "A"): поговорить с героиней прямо в сцене
#
# Перехват сделан по образцу глобального хука SayProcess из Smart Lolis:
# оборачиваем ADVCharacter.__call__, свои реплики пропускаем через флаг.

init 999 python:
    import re as _es_re

    _es_ai_tag_re = _es_re.compile(r"\{[^}]*\}")

    def _es_ai_strip_tags(text):
        try:
            return _es_ai_tag_re.sub("", text or "")
        except Exception:
            return text or ""

    # ------------------------------------------------- хук реплик романа ----

    import renpy.character as _es_rchar

    _es_ai_orig_character_call = _es_rchar.ADVCharacter.__call__

    def _es_ai_patched_character_call(self, what, *args, **kwargs):
        try:
            if not es_ai_internal_speaking[0]:
                es_ai_on_game_say(getattr(self, "name", None), _es_ai_strip_tags(what))
        except Exception:
            pass
        return _es_ai_orig_character_call(self, what, *args, **kwargs)

    _es_rchar.ADVCharacter.__call__ = _es_ai_patched_character_call

    # --------------------------------------------------- горячая клавиша ----

    def es_ai_open_overlay():
        if es_ai_chat_active[0]:
            return  # уже в сцене чата мода
        if es_ai_server_state != "ready":
            renpy.notify(u"AI-сервер не запущен")
            return
        renpy.call_in_new_context("es_ai_overlay_chat")

    def _es_ai_underlay():
        key = persistent.es_ai_overlay_key or "a"
        km = renpy.display.behavior.Keymap(**{key: es_ai_open_overlay})
        return [km]

    config.underlay = config.underlay + _es_ai_underlay()

################################################################################
## AI-чат поверх новеллы (новый контекст — сцена на паузе, как в игровом меню)
################################################################################

label es_ai_overlay_chat:
    python:
        es_ai_chat_active[0] = True
        es_ai_internal_speaking[0] = True   # реплики мода не озвучиваются как "роман"
        # Кто сейчас говорил в романе? Последняя узнанная героиня.
        es_ai_overlay_char = persistent.es_ai_last_char or "un"
        for _item in reversed(es_ai_novel_context):
            _cid = ES_AI_NAME_TO_ID.get(_item.get("who") or "")
            if _cid:
                es_ai_overlay_char = _cid
                break
        persistent.es_ai_last_char = es_ai_overlay_char
        es_ai_overlay_name = es_ai_char_name(es_ai_overlay_char)

    show screen es_ai_tts_player

    $ es_ai_say_girl(es_ai_overlay_char, u"Да, Семён?", "normal", False)

    jump es_ai_overlay_loop

label es_ai_overlay_loop:
    $ _inp = renpy.input(u"%s: (пустая строка — закончить)" % es_ai_overlay_name,
                         default="", length=200).strip()

    if _inp == "":
        jump es_ai_overlay_close

    show screen es_ai_thinking
    $ _res = es_ai_ask_girl(es_ai_overlay_char, _inp)
    hide screen es_ai_thinking

    if _res is None:
        "AI-сервер не ответил: [es_ai_last_error!q]"
        jump es_ai_overlay_loop

    $ persistent.es_ai_last_char = es_ai_overlay_char
    $ es_ai_say_girl(es_ai_overlay_char, _res.get("reply", ""), _res.get("emotion"))
    jump es_ai_overlay_loop

label es_ai_overlay_close:
    $ es_ai_tts_stop()
    hide screen es_ai_tts_player
    $ es_ai_internal_speaking[0] = False
    $ es_ai_chat_active[0] = False
    return
