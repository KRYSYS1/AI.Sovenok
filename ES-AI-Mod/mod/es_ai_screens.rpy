# -*- coding: utf-8 -*-
# AI Совёнок — экраны: статус сервера, «думает», TTS-плеер и большое окно
# настроек в духе SmartLolisSettingsWindow (провайдеры, ключи, тесты).

################################################################################
## Плеер очереди TTS: тик из главного потока
################################################################################

screen es_ai_tts_player:
    timer 0.25 repeat True action Function(es_ai_tts_pump)

################################################################################
## Статус сервера (правый верхний угол)
################################################################################

screen es_ai_status_badge:
    zorder 100
    frame:
        xpos 1560
        ypos 8
        padding (10, 6)
        background Frame("#000000aa", 4, 4)
        hbox:
            spacing 8
            if es_ai_server_state == "ready":
                text "●" size 20 color "#7CFC00" yalign 0.5
                text "AI: онлайн" size 18 color "#eeeeee" yalign 0.5
            elif es_ai_server_state in ("starting", "checking"):
                text "●" size 20 color "#FFD700" yalign 0.5
                text "AI: запуск..." size 18 color "#eeeeee" yalign 0.5
            else:
                text "●" size 20 color "#FF4040" yalign 0.5
                text "AI: офлайн" size 18 color "#eeeeee" yalign 0.5

################################################################################
## «Думает»
################################################################################

screen es_ai_thinking:
    zorder 100
    frame:
        xalign 0.5
        ypos 90
        padding (16, 8)
        background Frame("#000000aa", 4, 4)
        text "..." at es_ai_think_pulse

transform es_ai_think_pulse:
    alpha 0.5
    block:
        linear 0.5 alpha 1.0
        linear 0.5 alpha 0.5
        repeat

################################################################################
## Окно настроек (открывается через label es_ai_settings_loop — правка полей
## в отдельных диалогах renpy.input, всё остальное — прямо здесь)
################################################################################

screen es_ai_settings:
    modal True
    zorder 200
    key "game_menu" action Return("close")
    on "show" action Function(es_ai_sync_cameo_from_file)

    frame:
        xalign 0.5
        yalign 0.5
        xsize 1080
        ysize 860
        padding (30, 22)
        background Frame("#0d1117f2", 10, 10)

        vbox:
            spacing 12

            hbox:
                spacing 12
                text "AI Совёнок — настройки" size 32 color "#ffffff" yalign 0.5
                if es_ai_ui["busy"]:
                    text "… проверка …" size 22 color "#ffd700" yalign 0.5

            if es_ai_ui["result"]:
                frame:
                    padding (12, 8)
                    background Frame("#1d2630f0", 6, 6)
                    xfill True
                    text es_ai_sanitize_text(es_ai_ui["result"]) size 20 color "#9fe89f"

            viewport:
                ysize 600
                scrollbars "vertical"
                mousewheel True
                vbox:
                    spacing 16

                    ################################################## LLM ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 8
                            text "Нейросеть (LLM)" size 26 color "#7ec8ff"
                            text "Провайдер:" size 20 color "#bbbbbb"

                            hbox:
                                spacing 8
                                for _pid in ES_AI_LLM_PROVIDER_IDS:
                                    if es_ai_cfg.get("llm", {}).get("provider", "groq") == _pid:
                                        textbutton "● " + _pid + " " action Function(es_ai_pick_llm_provider, _pid)
                                    else:
                                        textbutton _pid action Function(es_ai_pick_llm_provider, _pid)

                            hbox:
                                spacing 8
                                text "URL:" size 20 color "#bbbbbb" yalign 0.5 min_width 90
                                text (es_ai_cfg.get("llm", {}).get("api_url") or u"(не задан)")[:64] size 18 color "#e8e8e8" yalign 0.5
                                textbutton "изменить" action Return(("edit", "api_url"))

                            hbox:
                                spacing 8
                                text "Модель:" size 20 color "#bbbbbb" yalign 0.5 min_width 90
                                text (es_ai_cfg.get("llm", {}).get("model") or u"(не задана)")[:40] size 18 color "#e8e8e8" yalign 0.5
                                textbutton "изменить" action Return(("edit", "model"))

                            hbox:
                                spacing 8
                                text "Ключ:" size 20 color "#bbbbbb" yalign 0.5 min_width 90
                                $ _cur_preset = ES_AI_LLM_PRESETS.get(es_ai_cfg.get("llm", {}).get("provider", "groq"))
                                if _cur_preset is not None and _cur_preset[3]:
                                    text es_ai_key_display(_cur_preset[3]) size 18 color "#e8e8e8" yalign 0.5
                                    textbutton "вставить ключ" action Return(("edit", "key:" + _cur_preset[3]))
                                else:
                                    text u"(ключ не нужен)" size 18 color "#888888" yalign 0.5

                            textbutton "▶ Проверить LLM" action Function(es_ai_ui_test, "llm") sensitive (not es_ai_ui["busy"])

                    ############################################### Ключи ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 6
                            text "Ключи API" size 26 color "#7ec8ff"
                            for _kname, _ktitle in ES_AI_KEY_ROWS:
                                hbox:
                                    spacing 8
                                    text _ktitle size 20 color "#bbbbbb" min_width 210
                                    text es_ai_key_display(_kname) size 18 color "#e8e8e8" yalign 0.5
                                    textbutton "изменить" action Return(("edit", "key:" + _kname))

                    ################################################# TTS ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 8
                            text "Голос (TTS)" size 26 color "#7ec8ff"
                            hbox:
                                spacing 8
                                for _pid, _ptitle in ES_AI_TTS_PROVIDERS:
                                    if es_ai_cfg.get("tts", {}).get("provider", "auto") == _pid:
                                        textbutton "● " + _ptitle + " " action Function(es_ai_cfg_set, "tts", "provider", _pid)
                                    else:
                                        textbutton _ptitle action Function(es_ai_cfg_set, "tts", "provider", _pid)
                            text es_ai_tts_summary() size 18 color "#bbbbbb"
                            textbutton "▶ Проверить голос (произнесёт фразу)" action Function(es_ai_ui_test, "tts") sensitive (not es_ai_ui["busy"])

                    ################################################# STT ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 8
                            text "Микрофон (STT)" size 26 color "#7ec8ff"
                            hbox:
                                spacing 8
                                for _pid, _ptitle in ES_AI_STT_PROVIDERS:
                                    if es_ai_cfg.get("stt", {}).get("provider", "auto") == _pid:
                                        textbutton "● " + _ptitle + " " action Function(es_ai_cfg_set, "stt", "provider", _pid)
                                    else:
                                        textbutton _ptitle action Function(es_ai_cfg_set, "stt", "provider", _pid)
                            textbutton "▶ Проверить микрофон (3 сек записи)" action Function(es_ai_ui_test, "stt") sensitive (not es_ai_ui["busy"])

                    ############################################## Сцена ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 8
                            text "Сцена" size 26 color "#7ec8ff"
                            textbutton (("[X] " if persistent.es_ai_cameo else "[  ] ") + "Случайные появления других персонажей") action Function(es_ai_toggle_cameo)
                            text "Иногда в сцену заходит другой персонаж (как в сюжете): вероятнее в романтический момент и в «своей» комнате." size 16 color "#8a97a6"
                            textbutton "🗺 Карта лагеря — кто где бывает" action Show("es_ai_map")

                    ######################################### Компоненты ##
                    frame:
                        padding (14, 12)
                        background Frame("#161d26f0", 6, 6)
                        xfill True
                        vbox:
                            spacing 8
                            text "Компоненты и данные" size 26 color "#7ec8ff"
                            textbutton "Установить/обновить TTS- и STT-компоненты (edge-tts, микрофон)" action Function(es_ai_ui_test, "deps") sensitive (not es_ai_ui["busy"])
                            textbutton "Очистить историю диалогов" action Function(es_ai_clear_all_history)

            hbox:
                spacing 20
                xalign 0.5
                textbutton "Готово" action Return("close")
                text "Esc — закрыть" size 18 color "#777777" yalign 0.5

################################################################################
## Хелперы окна настроек
################################################################################

init 11 python:
    ES_AI_KEY_ROWS = [
        ("groq_api_key", u"Groq"),
        ("mistral_api_key", u"Mistral"),
        ("llm_api_key", u"OpenRouter"),
        ("custom_llm_api_key", u"Свой LLM"),
        ("openai_api_key", u"OpenAI"),
        ("elevenlabs_api_key", u"ElevenLabs (голос)"),
    ]

    def es_ai_tts_summary():
        parts = []
        if es_ai_tts_avail.get("edge"):
            parts.append(u"edge-tts ✓")
        if es_ai_tts_avail.get("elevenlabs"):
            parts.append(u"ElevenLabs ✓")
        if es_ai_tts_avail.get("sapi"):
            parts.append(u"SAPI ✓")
        if not parts:
            parts.append(u"ничего не установлено — нажми «Установить компоненты»")
        mic = u"микрофон ✓" if es_ai_stt_avail.get("record") else u"микрофон ✗"
        return u", ".join(parts) + u"  |  " + mic

    def es_ai_clear_all_history():
        try:
            es_ai_http("/history/clear", {}, timeout=ES_AI_TIMEOUT_SHORT)
            renpy.notify(u"История диалогов очищена")
        except Exception as e:
            renpy.notify(u"Ошибка: %s" % e)
