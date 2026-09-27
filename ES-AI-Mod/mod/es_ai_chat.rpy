# -*- coding: utf-8 -*-
# AI Совёнок — сцена чата с героиней (вход из меню модов Бесконечного лета).

################################################################################
## Персонажи-говоруны мода
################################################################################

init 10 python:
    es_ai_speakers = {}
    for _cid, _name, _color in ES_AI_CHARS:
        es_ai_speakers[_cid] = Character(
            _name, color=_color, who_color=_color)

    def es_ai_pick_id(cid):
        """Выбор героини из меню (используется действием экрана)."""
        global es_ai_char_id
        es_ai_char_id = cid

# Приветственные реплики (fallback, если сервер недоступен)
init 10 python:
    ES_AI_INTROS = {
        "sl": u"Семён! Рада тебя видеть. Как ты устроился в лагере?",
        "dv": u"О, чел. И что ты здесь забыл?",
        "un": u"С-семён... Привет. Я как раз думала о тебе.",
        "us": u"Сеня! Я где-то спрятала компот, но забыла где! Поможешь искать?",
        "mi": u"А-а, Семён-сан! Сугой встреча, да?",
        "mz": u"Ну? Я книгу читаю. Если ты за книгой — говори. Если просто так — тоже говори, только быстро.",
        "mt": u"Семён. Хорошо, что встретила — у меня к тебе поручение.",
        "uv": u"...Ты меня видишь? Тс-с. Не шуми. У тебя, случайно, нет ничего вкусненького?",
        "el": u"О, привет! Ты вовремя — мы с Шуриком тут кое-что грандиозное затеваем. Хочешь послушать?",
        "sh": u"А?.. А, это ты. Я думал, опять кто-то в тоннелях... Ладно. Чего хотел?",
        "cs": u"Слушаю тебя. Только по делу, пожалуйста — у меня приём.",
    }

################################################################################
## Вход из меню модов
################################################################################

label es_ai:
    $ es_ai_chat_active[0] = True
    $ es_ai_menu_hide()
    $ day_time()
    $ persistent.sprite_time = "day"
    play ambience ambience_camp_center_day
    play music music_list["my_daily_life"] fadein 1
    show screen es_ai_tts_player
    show screen es_ai_status_badge
    $ es_ai_set_location("square")
    $ es_ai_loc_set("square")

    "AI Совёнок. Проверяю связь с сервером...{nw}"

    # Ждём сервер (стартует вместе с игрой в фоновом потоке)
    $ _waited = 0
    while es_ai_server_state in ("starting", "checking") and _waited < 60:
        $ renpy.pause(0.25)
        $_waited += 1

    if es_ai_server_state != "ready":
        "AI-сервер не отвечает: [es_ai_server_info!q]"
        "Попробуй запустить сервер вручную: двойной клик по start_server.pyw в папке [ES_AI_SERVER_DIR!q]"
        menu:
            "Что делать?"
            "Проверить связь ещё раз":
                $ es_ai_server_state = "checking"
                $ es_ai_start_server_async()
                jump es_ai
            "Выйти из мода":
                jump es_ai_leave

    # Мастер первого запуска: выбор провайдера и ключа (нативное окно, фолбэк — экран)
    if persistent.es_ai_setup_done is None:
        "AI-сервер подключён. Сейчас открою окно настроек: выбери нейросеть и вставь ключ."
        if not es_ai_open_settings_window():
            call es_ai_settings_loop
        $ persistent.es_ai_setup_done = True

    $ es_ai_girls_reset()   # новая прогулка: чистая сцена

label es_ai_pick:
    menu:
        "С кем хочешь поговорить?"
        "Славя":
            $ es_ai_pick_id("sl")
        "Алиса":
            $ es_ai_pick_id("dv")
        "Лена":
            $ es_ai_pick_id("un")
        "Ульяна":
            $ es_ai_char_id = "us"
        "Мику":
            $ es_ai_pick_id("mi")
        "Женя":
            $ es_ai_pick_id("mz")
        "Ольга Дмитриевна":
            $ es_ai_pick_id("mt")
        "Юля":
            $ es_ai_pick_id("uv")
        "Электроник":
            $ es_ai_pick_id("el")
        "Шурик":
            $ es_ai_pick_id("sh")
        "Виола":
            $ es_ai_pick_id("cs")

    $ persistent.es_ai_last_char = es_ai_char_id
    $ es_ai_who_name = es_ai_char_name(es_ai_char_id)
    $ es_ai_voice_text = ""

    "Я увидел [es_ai_who_name] и подошёл ближе.{nw}"

    show screen es_ai_thinking
    $ _greet = es_ai_initiative_girl(es_ai_char_id)
    hide screen es_ai_thinking

    if _greet is not None and _greet.get("reply"):
        $ es_ai_say_girl(es_ai_char_id, _greet.get("reply"), _greet.get("emotion"))
    else:
        $ es_ai_say_girl(es_ai_char_id, ES_AI_INTROS.get(es_ai_char_id, u"Привет, Семён."), "normal", False)

    jump es_ai_chat_input

################################################################################
## Окно настроек: цикл экрана + правка полей через renpy.input
################################################################################

label es_ai_settings_loop:
    $ es_ai_cfg_refresh()
    call screen es_ai_settings
    $ _act = _return

    if _act == "close":
        $ persistent.es_ai_setup_done = True
        return

    python:
        if type(_act) is tuple and _act[0] == "edit":
            _what = _act[1]
            if _what == "api_url":
                _cur = es_ai_cfg.get("llm", {}).get("api_url", "")
                _v = renpy.input(u"URL LLM-API:", default=_cur, length=200).strip()
                if _v:
                    es_ai_cfg_set("llm", "api_url", _v)
            elif _what == "model":
                _cur = es_ai_cfg.get("llm", {}).get("model", "")
                _v = renpy.input(u"Название модели:", default=_cur, length=120).strip()
                if _v:
                    es_ai_cfg_set("llm", "model", _v)
            elif _what.startswith("key:"):
                _kname = _what[4:]
                _titles = {"groq_api_key": u"Groq",
                           "llm_api_key": u"OpenRouter / свой LLM",
                           "openai_api_key": u"OpenAI",
                           "elevenlabs_api_key": u"ElevenLabs"}
                _v = renpy.input(u"Ключ %s (вставь и нажми Enter):" % _titles.get(_kname, _kname),
                                 default=u"", mask=u"•", length=300).strip()
                if _v:
                    es_ai_keys_set(_kname, _v)

    jump es_ai_settings_loop

################################################################################
## Основной цикл чата: после ответа — сразу ввод; пустой Enter — меню действий
################################################################################

label es_ai_chat_loop:
    menu:
        "Что будешь делать?"
        "Сказать что-нибудь":
            $ es_ai_voice_text = ""
            jump es_ai_chat_input
        "Сказать голосом":
            jump es_ai_chat_stt
        "Пусть заговорит сама":
            jump es_ai_chat_initiative
        "Сменить локацию":
            call es_ai_loc_menu
            jump es_ai_chat_loop
        "Сменить персонажа":
            jump es_ai_pick
        "Настройки AI":
            if es_ai_open_settings_window():
                "Открыл окно настроек поверх игры. Настроишь — продолжим."
            else:
                call es_ai_settings_loop
            jump es_ai_chat_loop
        "Озвучка: вкл/выкл":
            $ persistent.es_ai_tts = not persistent.es_ai_tts
            if persistent.es_ai_tts:
                "Озвучка включена."
            else:
                $ es_ai_tts_stop()
                "Озвучка выключена."
            jump es_ai_chat_loop
        "Закончить встречу":
            jump es_ai_leave

label es_ai_chat_input:
    $ _inp = renpy.input(u"Что скажешь %s? (пустой Enter — меню)" % es_ai_who_name,
                          default=es_ai_voice_text, length=200).strip()
    $ es_ai_voice_text = ""

    if _inp == "":
        jump es_ai_chat_loop

    show screen es_ai_thinking
    $ _res = es_ai_ask_girl(es_ai_char_id, _inp)
    hide screen es_ai_thinking

    if _res is None:
        "Сервер не ответил: [es_ai_last_error!q]"
        jump es_ai_chat_input

    $ es_ai_apply_actions(_res, _inp)
    $ es_ai_say_girl(es_ai_char_id, _res.get("reply", ""), _res.get("emotion"))
    $ es_ai_try_cameo(es_ai_char_id, _inp, _res)
    jump es_ai_chat_input

################################################################################
## Голосовой ввод (STT)
################################################################################

label es_ai_chat_stt:
    $ es_ai_tts_stop()
    $ es_ai_cfg_refresh()
    if (es_ai_cfg.get("stt") or {}).get("provider") == "winh":
        "Говори — откроется диктовка Windows (Win+H). Когда замолчишь, текст пойдёт в чат.{nw}"
    else:
        "Говори — я слушаю... (до 8 секунд){nw}"
    show screen es_ai_thinking
    $ _heard = es_ai_stt_girl(8)
    hide screen es_ai_thinking

    if _heard is None:
        "Голосовой ввод не сработал: [es_ai_last_error!q]"
        jump es_ai_chat_input

    if _heard == "":
        "Я не расслышал ничего.{nw}"
        jump es_ai_chat_input

    $ es_ai_voice_text = _heard
    jump es_ai_chat_input

################################################################################
## Инициатива героини
################################################################################

label es_ai_chat_initiative:
    show screen es_ai_thinking
    $ _ini = es_ai_initiative_girl(es_ai_char_id)
    hide screen es_ai_thinking

    if _ini is None:
        "Сервер не ответил: [es_ai_last_error!q]"
    else:
        $ es_ai_apply_actions(_ini)
        $ es_ai_say_girl(es_ai_char_id, _ini.get("reply", ""), _ini.get("emotion"))
        $ es_ai_try_cameo(es_ai_char_id, "", _ini)

    jump es_ai_chat_input

################################################################################
## Смена локации (прогулки по лагерю)
################################################################################

label es_ai_loc_menu:
    menu:
        "Куда пойдём?"
        "Площадь лагеря":
            $ es_ai_loc_set("square")
        "Пляж у реки":
            $ es_ai_loc_set("beach")
        "Остров":
            $ es_ai_loc_set("island")
        "Поляна":
            $ es_ai_loc_set("polyana")
        "Тропа в лесу":
            $ es_ai_loc_set("path")
        "Спортплощадка":
            $ es_ai_loc_set("playground")
        "Музыкальный клуб":
            $ es_ai_loc_set("musclub")
        "Сцена":
            $ es_ai_loc_set("stage")
        "Столовая":
            $ es_ai_loc_set("dining")
        "Библиотека":
            $ es_ai_loc_set("library")
        "Остаться здесь":
            pass
    jump es_ai_chat_input

################################################################################
## Выходы
################################################################################

label es_ai_leave_chat:
    $ es_ai_tts_stop()
    $ es_ai_menu_restore()
    $ es_ai_chat_active[0] = False
    hide screen es_ai_thinking
    hide screen es_ai_status_badge
    hide screen es_ai_tts_player
    jump es_ai

label es_ai_leave:
    $ es_ai_tts_stop()
    $ es_ai_menu_restore()
    $ es_ai_chat_active[0] = False
    hide screen es_ai_thinking
    hide screen es_ai_status_badge
    hide screen es_ai_tts_player
    return
