# -*- coding: utf-8 -*-
# AI Совёнок — локации для прогулок по лагерю.
# Каждая локация: фон (с фолбэками), предпочтительная одежда спрайта
# (у реки/пляжа — купальник) и описание для контекста нейросети.

init -10 python:
    ES_AI_LOCATIONS = [
        {"id": "square", "name": u"Площадь лагеря",
         "bgs": ["bg ext_square_day"], "dress": None,
         "desc": u"вы гуляете по центральной площади лагеря «Совёнок», вокруг домики и флаги"},
        {"id": "beach", "name": u"Пляж у реки", "romantic": True,
         "bgs": ["bg ext_beach_day"], "dress": "swim",
         "desc": u"вы на пляже у реки: вода, песок, солнце; купаться тут в самый раз"},
        {"id": "island", "name": u"Остров", "romantic": True,
         "bgs": ["bg ext_island_day"], "dress": "swim",
         "desc": u"вы на острове посреди реки; вокруг пляж и шум птиц, самое место искупаться"},
        {"id": "polyana", "name": u"Поляна", "romantic": True,
         "bgs": ["bg ext_polyana_day"], "dress": None,
         "desc": u"вы на лесной поляне за лагерем, тихо, поют птицы"},
        {"id": "path", "name": u"Тропа в лесу",
         "bgs": ["bg ext_path_day", "bg ext_path2_day"], "dress": None,
         "desc": u"вы гуляете по тропе среди деревьев"},
        {"id": "playground", "name": u"Спортплощадка",
         "bgs": ["bg ext_playground_day"], "dress": "sport",
         "desc": u"вы на спортплощадке лагеря: волейбольная сетка, свежий воздух"},
        {"id": "musclub", "name": u"Музыкальный клуб",
         "bgs": ["bg ext_musclub_day"], "dress": None,
         "desc": u"вы у музыкального клуба, из окон доносятся аккорды"},
        {"id": "stage", "name": u"Сцена",
         "bgs": ["bg ext_stage_normal_day"], "dress": None,
         "desc": u"вы у сцены лагеря, где готовят концерт"},
        {"id": "dining", "name": u"Столовая",
         "bgs": ["bg int_dining_hall_day"], "dress": None,
         "desc": u"вы в столовой лагеря: пахнет компотом, котлеты и какао"},
        {"id": "library", "name": u"Библиотека", "romantic": True,
         "bgs": ["bg int_library_day"], "dress": None,
         "desc": u"вы в библиотеке лагеря: стеллажи книг и тишина"},
        {"id": "camp_gate", "name": u"Ворота лагеря", "context_only": True,
         "bgs": ["bg ext_camp_entrance_day"],
         "time_bgs": {"day": ["bg ext_camp_entrance_day"],
                      "sunset": ["bg ext_camp_entrance_day"],
                      "night": ["bg ext_camp_entrance_night"]}, "dress": None,
         "desc": u"вы у главных ворот и входа в пионерлагерь «Совёнок»"},
        {"id": "bus_gate", "name": u"Автобус у ворот", "context_only": True,
         "bgs": ["bg ext_bus"],
         "time_bgs": {"day": ["bg ext_bus"], "sunset": ["bg ext_bus"],
                      "night": ["bg ext_bus_night"]}, "dress": None,
         "desc": u"вы у ворот лагеря рядом с приехавшим автобусом Икарус"},
        {"id": "bus_inside", "name": u"Внутри автобуса", "context_only": True, "romantic": True,
         "bgs": ["bg int_bus"],
         "time_bgs": {"day": ["bg int_bus"], "sunset": ["bg int_bus"],
                      "night": ["bg int_bus_night"]}, "dress": None,
         "desc": u"вы внутри старого автобуса Икарус у ворот лагеря"},
        {"id": "mt_room", "name": u"Комната вожатой", "context_only": True, "romantic": True,
         "bgs": ["bg int_house_of_mt_day"],
         "time_bgs": {"day": ["bg int_house_of_mt_day"],
                      "sunset": ["bg int_house_of_mt_sunset"],
                      "night": ["bg int_house_of_mt_night", "bg int_house_of_mt_night2"]},
         "dress": None, "desc": u"вы в комнате домика вожатой Ольги Дмитриевны"},
        {"id": "houses", "name": u"Аллея домиков", "context_only": True,
         "bgs": ["bg ext_houses_day"],
         "time_bgs": {"day": ["bg ext_houses_day"],
                      "sunset": ["bg ext_houses_sunset"],
                      "night": ["bg ext_houses_sunset"]}, "dress": None,
         "desc": u"вы идёте по аллее между жилыми домиками пионеров"},
        {"id": "clubs", "name": u"Клубы", "context_only": True,
         "bgs": ["bg ext_clubs_day"],
         "time_bgs": {"day": ["bg ext_clubs_day"], "sunset": ["bg ext_clubs_day"],
                      "night": ["bg ext_clubs_night"]}, "dress": None,
         "desc": u"вы у здания кружков и клуба кибернетиков"},
        {"id": "club_room", "name": u"Клуб кибернетиков внутри", "context_only": True, "romantic": True,
         "bgs": ["bg int_clubs_male_day"],
         "time_bgs": {"day": ["bg int_clubs_male_day"],
                      "sunset": ["bg int_clubs_male_sunset"],
                      "night": ["bg int_clubs_male2_night"]}, "dress": None,
         "desc": u"вы внутри клуба кибернетиков среди столов, деталей и приборов"},
        {"id": "aidpost", "name": u"Медпункт", "context_only": True,
         "bgs": ["bg ext_aidpost_day"],
         "time_bgs": {"day": ["bg ext_aidpost_day"], "sunset": ["bg ext_aidpost_day"],
                      "night": ["bg ext_aidpost_night"]}, "dress": None,
         "desc": u"вы возле лагерного медпункта"},
        {"id": "aidpost_inside", "name": u"Внутри медпункта", "context_only": True, "romantic": True,
         "bgs": ["bg int_aidpost_day"],
         "time_bgs": {"day": ["bg int_aidpost_day"], "sunset": ["bg int_aidpost_day"],
                      "night": ["bg int_aidpost_night"]}, "dress": None,
         "desc": u"вы внутри медпункта, рядом кушетка и медицинские шкафы"},
        {"id": "boathouse", "name": u"Лодочная станция", "context_only": True, "romantic": True,
         "bgs": ["bg ext_boathouse_day"],
         "time_bgs": {"day": ["bg ext_boathouse_day"], "sunset": ["bg ext_boathouse_day"],
                      "night": ["bg ext_boathouse_night"]}, "dress": None,
         "desc": u"вы у лодочной станции и причала на реке"},
        {"id": "washstand", "name": u"Умывальники", "context_only": True,
         "bgs": ["bg ext_washstand_day", "bg ext_washstand2_day"], "dress": None,
         "desc": u"вы возле лагерных умывальников"},
        {"id": "road", "name": u"Дорога к лагерю", "context_only": True,
         "bgs": ["bg ext_road_day"],
         "time_bgs": {"day": ["bg ext_road_day"], "sunset": ["bg ext_road_sunset"],
                      "night": ["bg ext_road_night", "bg ext_road_night2"]}, "dress": None,
         "desc": u"вы на дороге неподалёку от лагеря, вокруг лес"},
        {"id": "dv_room", "name": u"Домик Алисы и Ульяны", "context_only": True, "romantic": True,
         "bgs": ["bg int_house_of_dv_day"],
         "time_bgs": {"day": ["bg int_house_of_dv_day"], "sunset": ["bg int_house_of_dv_day"],
                      "night": ["bg int_house_of_dv_night"]}, "dress": None,
         "desc": u"вы внутри домика Алисы и Ульяны"},
        {"id": "sl_room", "name": u"Домик Слави и Жени", "context_only": True, "romantic": True,
         "bgs": ["bg int_house_of_sl_day"], "dress": None,
         "desc": u"вы внутри домика Слави и Жени"},
        {"id": "un_room", "name": u"Домик Лены и Мику", "context_only": True, "romantic": True,
         "bgs": ["bg int_house_of_un_day"],
         "time_bgs": {"day": ["bg int_house_of_un_day"], "sunset": ["bg int_house_of_un_day"],
                      "night": ["bg int_house_of_un_night"]}, "dress": None,
         "desc": u"вы внутри домика Лены и Мику"},
        {"id": "old_building", "name": u"Старый корпус", "context_only": True,
         "bgs": ["bg ext_old_building_night"], "dress": None,
         "desc": u"вы у заброшенного старого корпуса лагеря; вокруг темно и тревожно"},
        {"id": "catacombs", "name": u"Катакомбы", "context_only": True,
         "bgs": ["bg int_catacombs_entrance"], "dress": None,
         "desc": u"вы в подземных катакомбах под старым корпусом"},
        {"id": "bunker", "name": u"Бомбоубежище", "context_only": True,
         "bgs": ["bg int_catacombs_living"], "dress": None,
         "desc": u"вы в жилом помещении бомбоубежища под старым корпусом; выход ведёт в катакомбы"},
        {"id": "mine", "name": u"Шахта", "context_only": True,
         "bgs": ["bg int_mine"], "dress": None,
         "desc": u"вы в коридоре заброшенной шахты под лагерем"},
        {"id": "old_building_inside", "name": u"Старый корпус внутри", "context_only": True,
         "bgs": ["bg int_old_building_night"], "dress": None,
         "desc": u"вы внутри заброшенного старого корпуса; отсюда можно выйти наружу или пройти в катакомбы"},
        {"id": "library_ext", "name": u"У библиотеки", "context_only": True,
         "bgs": ["bg ext_library_day"],
         "time_bgs": {"day": ["bg ext_library_day"], "sunset": ["bg ext_library_day"],
                      "night": ["bg ext_library_night"]}, "dress": None,
         "desc": u"вы на улице перед библиотекой лагеря, рядом вход и дорожка к площади"},
        {"id": "mine_descent", "name": u"Спуск в шахту", "context_only": True,
         "bgs": ["bg int_catacombs_hole"], "dress": None,
         "desc": u"вы у подземного спуска из катакомб в шахту"},
        {"id": "mine_room", "name": u"Комната в шахте", "context_only": True,
         "bgs": ["bg int_mine_room"], "dress": None,
         "desc": u"вы в отдельной комнате заброшенной шахты; проход ведёт к развилке"},
        {"id": "mine_exit", "name": u"Выход из шахты", "context_only": True,
         "bgs": ["bg int_mine_exit_night_light", "bg int_mine_exit_night_nolight",
                 "bg int_mine_exit_night_torch"], "dress": None,
         "desc": u"вы у подземного выхода из шахты на площадь лагеря; обратно можно пройти к развилке"},
        {"id": "mine_crossroad", "name": u"Развилка шахты", "context_only": True,
         "bgs": ["bg int_mine_crossroad"], "dress": None,
         "desc": u"вы на развилке шахты: проходы ведут в коридор, комнату, забой, привал и к выходу"},
        {"id": "mine_coalface", "name": u"Забой шахты", "context_only": True,
         "bgs": ["bg int_mine_coalface"], "dress": None,
         "desc": u"вы у забоя заброшенной шахты; обратный проход ведёт к развилке"},
        {"id": "mine_halt", "name": u"Привал в шахте", "context_only": True,
         "bgs": ["bg int_mine_halt"], "dress": None,
         "desc": u"вы на площадке для привала в шахте; обратно можно пройти к развилке"},
        {"id": "bus_410", "name": u"Автобус 410", "context_only": True,
         "bgs": ["bg int_liaz"], "dress": None,
         "desc": u"вы в салоне ЛиАЗа маршрута 410 вне лагеря, в контексте истории о мире «Совёнка»; выход ведёт к автобусной остановке, поездка необязательна и не означает возвращение в реальный мир"},
        # --- продолжение раздела 28: оставшиеся контекстные локации и подлокации ES 1.6 ---
        {"id": "semen_room", "name": u"Комната Семёна", "context_only": True, "romantic": True,
         "bgs": ["bg semen_room_window", "bg semen_room"],
         "time_bgs": {"day": ["bg semen_room_window", "bg semen_room"],
                      "sunset": ["bg semen_room_window", "bg semen_room"],
                      "night": ["bg semen_room_window", "bg semen_room"]}, "dress": None,
         "desc": u"вы в комнате Семёна: кровать, стол у окна, вещи главного героя"},
        {"id": "bathhouse", "name": u"Баня", "context_only": True, "romantic": True,
         "bgs": ["bg ext_bathhouse_night"], "dress": "swim",
         "time_bgs": {"day": ["bg ext_bathhouse_night"],
                      "sunset": ["bg ext_bathhouse_night"],
                      "night": ["bg ext_bathhouse_night"]},
         "desc": u"вы у лагерной бани вечером, рядом дрова и запах пара"},
        {"id": "musclub_inside", "name": u"Музыкальный клуб внутри", "context_only": True,
         "bgs": ["bg int_musclub_day"],
         "time_bgs": {"day": ["bg int_musclub_day"],
                      "sunset": ["bg int_musclub_day"],
                      "night": ["bg int_musclub_day"]}, "dress": None,
         "desc": u"вы внутри музыкального клуба среди инструментов и нотных листов"},
        {"id": "bus_stop", "name": u"Автобусная остановка", "context_only": True,
         "bgs": ["bg bus_stop"],
         "time_bgs": {"day": ["bg bus_stop"], "sunset": ["bg bus_stop"],
                      "night": ["bg bus_stop"]}, "dress": None,
         "desc": u"вы на автобусной остановке у трассы за пределами лагеря"},
        {"id": "dining_ext", "name": u"Площадка у столовой", "context_only": True,
         "bgs": ["bg ext_dining_hall_near_day", "bg ext_dining_hall_away_day"], "dress": None,
         "desc": u"вы на площадке перед столовой лагеря, на улице"},
        {"id": "stage_big", "name": u"Большая сцена (концерт)", "context_only": True,
         "bgs": ["bg ext_stage_big_night"],
         # Big Stage has no daytime asset; reuse the ordinary stage without moving.
         "time_bgs": {"day": ["bg ext_stage_normal_day"],
                      "sunset": ["bg ext_stage_normal_sunset", "bg ext_stage_normal_day"],
                      "night": ["bg ext_stage_big_night"]}, "dress": None,
         "desc": u"вы у большой концертной сцены лагеря, готовится вечернее выступление"},
        {"id": "gate_no_bus", "name": u"Ворота (автобус уехал)", "context_only": True,
         "bgs": ["bg ext_no_bus"],
         "time_bgs": {"day": ["bg ext_no_bus"], "sunset": ["bg ext_no_bus_sunset"],
                      "night": ["bg ext_no_bus_night"]}, "dress": None,
         "desc": u"вы у ворот лагеря; автобуса уже нет, дорога пуста"},
        {"id": "dv_house_ext", "name": u"Домик Алисы и Ульяны снаружи", "context_only": True,
         "bgs": ["bg ext_house_of_dv_day"],
         "time_bgs": {"day": ["bg ext_house_of_dv_day"],
                      "sunset": ["bg ext_house_of_dv_day"],
                      "night": ["bg ext_house_of_dv_night"]}, "dress": None,
         "desc": u"вы у входа в домик Алисы и Ульяны"},
        {"id": "mt_house_ext", "name": u"Домик вожатой снаружи", "context_only": True,
         "bgs": ["bg ext_house_of_mt_day"],
         "time_bgs": {"day": ["bg ext_house_of_mt_day"],
                      "sunset": ["bg ext_house_of_mt_sunset"],
                      "night": ["bg ext_house_of_mt_night"]}, "dress": None,
         "desc": u"вы у домика вожатой Ольги Дмитриевны снаружи"},
        {"id": "sl_house_ext", "name": u"Домик Слави и Жени снаружи", "context_only": True,
         "bgs": ["bg ext_house_of_sl_day"], "dress": None,
         "desc": u"вы у входа в домик Слави и Жени"},
        {"id": "un_house_ext", "name": u"Домик Лены и Мику снаружи", "context_only": True,
         "bgs": ["bg ext_house_of_un_day"], "dress": None,
         "desc": u"вы у входа в домик Лены и Мику"},
    ]
    ES_AI_LOCATION_INDEX = {loc["id"]: loc for loc in ES_AI_LOCATIONS}

    ES_AI_LOC_CUR = ["square"]
    ES_AI_LOC_LAST_CHAR = [None]
    ES_AI_LOC_LAST_EMO = ["normal"]
    ES_AI_LOC_HAS_GIRL = [False]
    ES_AI_TIME = ["day"]   # morning | day | sunset | night
    ES_AI_CLOCK = dict(minutes=None, revision=None, enabled=False, show_time=True, lines=0, generation=0)

    def es_ai_clock_config_path():
        """config.json пользователя (%LOCALAPPDATA%\AI.Sovenok) с самостоятельным
        фолбэком. Нельзя вызывать es_ai_user_config_path() из cameo.rpy через
        try/except NameError: порядок init-блоков Ren'Py с равным приоритетом не
        гарантирован, и при загрузке locations РАНЬШЕ cameo это тихо падало в
        NameError и читало серверный config.json без game_clock — часы выключались
        (диагностика 14:30:52: phase=day, enabled=False при включённом тумблере)."""
        import os
        base = os.environ.get("LOCALAPPDATA")
        if base:
            candidate = os.path.join(base, "AI.Sovenok", "config.json")
            if os.path.exists(candidate):
                return candidate
        return os.path.join(ES_AI_SERVER_DIR, "config.json")

    def es_ai_clock_settings():
        import __builtin__ as clock_builtins
        import io
        import os
        import json
        st = dict(enabled=False, show_time=True, start_time="08:00", minutes_per_exchange=5, revision=0)
        try:
            path = es_ai_clock_config_path()
        except NameError:
            path = os.path.join(ES_AI_SERVER_DIR, "config.json")
        try:
            # The game's bundled Python 2 lacks the utf-8-sig codec.
            with io.open(path, "r", encoding="utf-8") as stream:
                data = json.loads(stream.read().lstrip(u"\ufeff"))
            raw = data.get("game_clock") if isinstance(data, clock_builtins.dict) else None
            if isinstance(raw, clock_builtins.dict):
                st.update((k, raw[k]) for k in st if k in raw)
        except Exception:
            pass
        st["enabled"] = st["enabled"] is True
        if not isinstance(st["show_time"], clock_builtins.bool):
            st["show_time"] = True
        try:
            parts = st["start_time"].strip().split(":")
            hour, minute = (int(p) for p in parts)
            if len(parts[0]) not in (1, 2) or len(parts[1]) != 2 or not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("HH:MM")
            st["start_time"] = "%02d:%02d" % (hour, minute)
        except Exception:
            st["start_time"] = "08:00"
        for key, default, upper in (("minutes_per_exchange", 5, 120), ("revision", 0, None)):
            try:
                value = st[key]
                if isinstance(value, clock_builtins.bool):
                    raise ValueError(key)
                value = int(value)
                st[key] = clock_builtins.max(0, value)
                if upper is not None:
                    st[key] = clock_builtins.min(upper, st[key])
            except Exception:
                st[key] = default
        return st

    def es_ai_clock_phase(minutes):
        hour = (minutes % 1440) // 60
        if 6 <= hour < 10:
            return "morning"
        if 10 <= hour < 18:
            return "day"
        if 18 <= hour < 22:
            return "sunset"
        return "night"

    def es_ai_apply_time_phase(phase, redraw=True, force=False):
        changed = ES_AI_TIME[0] != phase
        ES_AI_TIME[0] = phase
        visual = "day" if phase == "morning" else phase
        if changed or force:
            persistent.sprite_time = visual
            fn = globals().get(visual + "_time")
            if callable(fn):
                fn()
            es_ai_log("clock phase -> %s (minutes=%s enabled=%s rev=%s)" %
                      (phase, ES_AI_CLOCK["minutes"], ES_AI_CLOCK["enabled"],
                       ES_AI_CLOCK["revision"]))
        if changed and redraw:
            # No movement, NPC lifecycle, context reset, or layout reroll.
            bg = es_ai_loc_bg(es_ai_location())
            es_ai_log("clock bg -> %s (loc=%s)" % (bg, ES_AI_LOC_CUR[0]))
            renpy.scene()
            renpy.show(bg)
            es_ai_refresh_girls()
            renpy.with_statement(dissolve)

    def es_ai_clock_sync(redraw=True, force=False):
        st = es_ai_clock_settings()
        was_enabled = ES_AI_CLOCK["enabled"]
        ES_AI_CLOCK["enabled"] = st["enabled"]
        ES_AI_CLOCK["show_time"] = st["show_time"]
        if was_enabled != st["enabled"]:
            ES_AI_CLOCK["generation"] += 1
        if st["enabled"]:
            if ES_AI_CLOCK["minutes"] is None or ES_AI_CLOCK["revision"] != st["revision"]:
                hour, minute = (int(p) for p in st["start_time"].split(":"))
                ES_AI_CLOCK["minutes"] = hour * 60 + minute
                ES_AI_CLOCK["revision"] = st["revision"]
                ES_AI_CLOCK["generation"] += 1
            es_ai_apply_time_phase(es_ai_clock_phase(ES_AI_CLOCK["minutes"]), redraw,
                                   force or not was_enabled)
        return st

    def es_ai_clock_snapshot():
        minutes = ES_AI_CLOCK["minutes"]
        return dict(enabled=ES_AI_CLOCK["enabled"],
                    time="%02d:%02d" % (minutes // 60, minutes % 60) if minutes is not None else "08:00",
                    phase=ES_AI_TIME[0])

    def es_ai_clock_text():
        return (es_ai_clock_snapshot()["time"]
                if ES_AI_CLOCK["enabled"] and ES_AI_CLOCK.get("show_time", True) else "")

    def es_ai_clock_begin(redraw=True):
        es_ai_clock_sync(redraw=redraw)
        return (ES_AI_CLOCK["revision"], ES_AI_CLOCK["enabled"], ES_AI_CLOCK["generation"])

    def es_ai_clock_complete(lines_before, token):
        st = es_ai_clock_sync()
        current = (ES_AI_CLOCK["revision"], ES_AI_CLOCK["enabled"], ES_AI_CLOCK["generation"])
        if token == current and st["enabled"] and ES_AI_CLOCK["lines"] > lines_before:
            ES_AI_CLOCK["minutes"] = (ES_AI_CLOCK["minutes"] + st["minutes_per_exchange"]) % 1440
            es_ai_apply_time_phase(es_ai_clock_phase(ES_AI_CLOCK["minutes"]))
    ES_AI_SHOWN = []       # All current participants; list order does not set positions.
    ES_AI_FREE_SCENE = [False]  # Overlay chat is private, even while chat_active is true.
    ES_AI_GIRL_LAYOUT = [None, {}]  # Last (location, sorted IDs, primary ID) and slots.
    ES_AI_DRESS = [None]   # контекстный наряд В ПРЕДЕЛАХ локации: None|"swim"|"cover"|"sport"
    ES_AI_PARTY = [False]  # Current public event, reset on travel/session reset.

    # --- Карта лагеря (соседство локаций): переходы должны быть логичны ---
    # Не жёсткое ограничение — используется, чтобы подсказать нейросети, куда
    # логично пройти отсюда (список соседей уходит в контекст /chat и /initiative).
    ES_AI_MAP = {
        "square": ["houses", "dining_ext", "clubs", "musclub", "library_ext", "stage",
                   "playground", "aidpost", "path", "camp_gate", "semen_room", "mine_exit"],
        "camp_gate": ["square", "bus_gate", "gate_no_bus", "road"],
        "bus_gate": ["camp_gate", "gate_no_bus", "bus_inside"],
        "gate_no_bus": ["camp_gate", "bus_gate", "road"],
        "bus_inside": ["bus_gate"],
        "bus_stop": ["road", "bus_410"], "bus_410": ["bus_stop"],
        "road": ["camp_gate", "gate_no_bus", "bus_stop"],
        "houses": ["square", "dv_house_ext", "sl_house_ext", "un_house_ext",
                   "mt_house_ext", "semen_room", "playground", "aidpost"],
        "dv_house_ext": ["houses", "dv_room"], "dv_room": ["dv_house_ext"],
        "sl_house_ext": ["houses", "sl_room"], "sl_room": ["sl_house_ext"],
        "un_house_ext": ["houses", "un_room"], "un_room": ["un_house_ext"],
        "mt_house_ext": ["houses", "square", "mt_room"], "mt_room": ["mt_house_ext"],
        "semen_room": ["houses", "square"],
        "dining_ext": ["square", "dining"], "dining": ["dining_ext"],
        "clubs": ["square", "club_room", "musclub"], "club_room": ["clubs"],
        "musclub": ["square", "clubs", "musclub_inside"], "musclub_inside": ["musclub"],
        "library_ext": ["square", "library"], "library": ["library_ext"],
        "stage": ["square", "stage_big"], "stage_big": ["stage", "square"],
        "playground": ["square", "houses"],
        "aidpost": ["square", "houses", "aidpost_inside"], "aidpost_inside": ["aidpost"],
        "path": ["square", "polyana", "beach", "washstand", "old_building"],
        "polyana": ["path", "old_building", "beach"],
        "washstand": ["path", "beach"],
        "beach": ["path", "island", "boathouse", "bathhouse", "washstand"],
        "island": ["beach", "boathouse"],
        "boathouse": ["beach", "island"],
        "bathhouse": ["beach", "washstand"],
        "old_building": ["polyana", "path", "old_building_inside"],
        "old_building_inside": ["old_building", "catacombs"],
        "catacombs": ["old_building_inside", "bunker", "mine_descent"],
        "bunker": ["catacombs"], "mine_descent": ["catacombs", "mine"],
        "mine": ["mine_descent", "mine_crossroad"],
        "mine_crossroad": ["mine", "mine_room", "mine_coalface", "mine_halt", "mine_exit"],
        "mine_room": ["mine_crossroad"], "mine_coalface": ["mine_crossroad"],
        "mine_halt": ["mine_crossroad"], "mine_exit": ["mine_crossroad", "square"],
    }

    # Слова-подсказки для контекстного подбора наряда (реплики Семёна + героини).
    # Явное желание искупаться/загорать -> купальник (даже вне воды).
    ES_AI_DRESS_SWIM_WORDS = (u"купаться", u"искупаться", u"искупаемся", u"поплавать",
        u"поплаваем", u"купальник", u"в купальнике", u"загорать", u"позагорать",
        u"окунуться", u"поныряем", u"нырять", u"в воду залез")
    # Похолодало / серьёзный разговор / просьба одеться -> вернуть форму.
    ES_AI_DRESS_COVER_WORDS = (u"замёрзл", u"замерзл", u"холодно", u"зябко", u"оденься",
        u"переоденься обратно", u"надень форму", u"в форму", u"прикройся", u"простуд",
        u"стесняюсь", u"неудобно так", u"серьёзный разговор", u"по-серьёзному")
    # Романтический/интимный настрой -> купальник, но только в романтических локациях
    # (комнаты, у воды) или вечером/ночью.
    ES_AI_DRESS_ROMANTIC_WORDS = (u"поцелу", u"обним", u"люблю тебя", u"романти", u"наедине",
        u"прижал", u"прижа", u"свидание", u"только мы вдвоём", u"нежно", u"ласков", u"страст")


    def es_ai_scene_begin(free_scene):
        es_ai_girls_reset()
        ES_AI_FREE_SCENE[0] = bool(free_scene)

    def es_ai_scene_end():
        ES_AI_FREE_SCENE[0] = False
        es_ai_girls_reset()

    def es_ai_girls_reset():
        globals().get("ES_AI_ACTIVITY_PENDING", {}).clear()
        ES_AI_DRESS[0] = None
        ES_AI_LOC_LAST_CHAR[0] = None
        ES_AI_LOC_LAST_EMO[0] = "normal"
        ES_AI_PARTY[0] = False
        ES_AI_SHOWN[:] = []
        ES_AI_GIRL_LAYOUT[:] = [None, {}]
        # Состояние «остающихся» камео и хвост реплик — тоже с нуля.
        try:
            ES_AI_CAMEO_ACTIVE[:] = []
            ES_AI_CAMEO_NEARBY.clear()
        except Exception:
            pass
        try:
            del ES_AI_RECENT_LINES[:]
        except Exception:
            pass
        try:
            ES_AI_CAMEO_CD[0] = 0
        except Exception:
            pass

    def es_ai_refresh_girls():
        """Show every participant in stable, screen-wide, overlapping rows."""
        ids = sorted(g["id"] for g in ES_AI_SHOWN)
        main = next((g["id"] for g in ES_AI_SHOWN if not g.get("cameo")), None)
        key = (ES_AI_LOC_CUR[0], tuple(ids), main)
        if ES_AI_GIRL_LAYOUT[0] != key:
            n = len(ids)
            if n == 0:
                positions = []
            elif n == 1:
                positions = [0.5]
            elif n in (2, 3):
                clustered = _es_random.random() < 0.30
                positions = ([0.35, 0.65] if clustered else [0.18, 0.82]) if n == 2 else (
                    [0.30, 0.50, 0.70] if clustered else [0.13, 0.50, 0.87])
                positions = [x + _es_random.uniform(-0.015, 0.015) for x in positions]
            elif n == 4:
                positions = [0.13, 0.36, 0.64, 0.87]
            else:
                positions = [0.13, 0.38, 0.64, 0.87]
            front = [(x, 0.88 if n > 4 else 1.0, 0, 1000) for x in positions]
            rear_count = n - len(front)
            rear_positions = {1: [0.50], 2: [0.24, 0.76], 3: [0.08, 0.50, 0.92]}
            rear = [(x, 0.75, -25, 0) for x in rear_positions.get(rear_count, [])]
            slots = front + rear
            layout = {}
            if main is not None:
                # Reserve the nearest-to-center foreground slot for the heroine.
                center = _es_ai_cameo_builtins.min(range(len(front)),
                    key=lambda i: abs(front[i][0] - 0.5))
                layout[main] = slots.pop(center)
            others = [cid for cid in ids if cid != main]
            _es_random.shuffle(others)
            layout.update(zip(others, slots))
            ES_AI_GIRL_LAYOUT[:] = [key, layout]
        for g in ES_AI_SHOWN:
            x, zoom, yoffset, row_z = ES_AI_GIRL_LAYOUT[1][g["id"]]
            if g.get("cameo") and ES_AI_LOC_CUR[0] == "beach":
                if g.get("dress_reason", "location") == "location" and g.get("dress") in (None, "swim"):
                    g["dress"] = es_ai_default_dress()
                else:
                    g["dress"] = es_ai_cameo_dress(None, g.get("dress"), g)
            # Cameos keep per-NPC clothing, including water-location swim defaults,
            # independently of the active heroine's contextual dress.
            dp = g["dress"] if ("dress" in g) else es_ai_loc_dress_pref()
            tag = es_ai_resolve_sprite(g["id"], g["emo"], dress_pref=dp)
            g["tag"] = tag
            z = row_z + 300 - ES_AI_HEIGHTS.get(g["id"], 160)
            z += 2000 if g.get("focused") else (50 if not g.get("cameo") else 0)
            requested = "%s %s%s" % (g["id"], g["emo"], " " + dp if dp else "")
            matches = tuple(t for t in (requested + " close", requested, requested + " far")
                            if renpy.has_image(t, exact=True))
            diagnostic = (g["emo"], dp, tag, matches, x, zoom, yoffset, z)
            if g.get("_sprite_diag") != diagnostic:
                g["_sprite_diag"] = diagnostic
                es_ai_log("sprite id=%s emo=%s dress=%r tag=%r exact_matches=%r xpos=%.4f zoom=%.2f yoffset=%s zorder=%s" %
                          ((g["id"],) + diagnostic))
            if tag:
                # Focus clears every row without changing the speaker's slot.
                try:
                    renpy.show(tag, at_list=[Transform(xpos=float(x), xanchor=0.5,
                        yalign=1.0, zoom=zoom, yoffset=yoffset)], zorder=z)
                except Exception as e:
                    es_ai_log("girl show error: %s" % e)
            else:
                renpy.hide(g["id"])

    def es_ai_girl_enter(char_id, emotion):
        """Показать выбранную героиню и убрать предыдущую.

        У разных героинь разные image-теги (un, dv, sl...), поэтому обычный
        renpy.show() не заменяет прошлый спрайт автоматически.
        """
        global es_ai_char_id, es_ai_who_name
        es_ai_char_id = char_id
        es_ai_who_name = next((c[1] for c in ES_AI_CHARS if c[0] == char_id), char_id)
        if not ES_AI_FREE_SCENE[0]:
            es_ai_girls_reset()
        previous = next((g for g in ES_AI_SHOWN if not g.get("cameo")), None)
        selected = next((g for g in ES_AI_SHOWN if g["id"] == char_id), None)
        saved = es_ai_cameo_take_nearby(char_id)
        switching = previous is None or previous["id"] != char_id
        if switching:
            # Clothing and recent romantic context belong to the former primary.
            ES_AI_CAMEO_PLAYER_TEXT[0] = u""
            ES_AI_RECENT_LINES[:] = []
            if previous is not None:
                previous.update(cameo=True, dress=es_ai_current_dress(),
                    dress_reason="player" if ES_AI_DRESS[0] else "location",
                    dress_location=ES_AI_LOC_CUR[0])
                if ES_AI_DRESS[0] == "cover":
                    previous["dress"] = "pioneer"
                if previous.get("tag") and previous.get("dress") not in previous["tag"].split():
                    previous["dress"] = None
                es_ai_cameo_register(previous["id"], 0)
            selected = selected or saved
            ES_AI_DRESS[0] = None
            if selected is not None:
                own_dress = es_ai_cameo_dress(None, selected.get("dress"), selected)
                if selected.get("tag") and own_dress and own_dress not in selected["tag"].split():
                    own_dress = None
                if not (ES_AI_LOC_CUR[0] == "beach" and own_dress == "swim" and selected.get("dress_reason") == "location"):
                    ES_AI_DRESS[0] = "cover" if own_dress == "pioneer" else own_dress
            elif ES_AI_PARTY[0] and es_ai_has_party_dress(char_id):
                ES_AI_DRESS[0] = "dress"
        selected = selected if selected is not None else {"id": char_id}
        current_emo = emotion or selected.get("emo") or "normal"
        selected.update(emo=current_emo)
        for field in ("cameo", "dress", "dress_reason", "dress_location", "dwell"):
            selected.pop(field, None)
        keep = [g for g in ES_AI_SHOWN if g["id"] != char_id]
        es_ai_cameo_unregister(char_id)
        staying = set(g["id"] for g in keep)
        for cid, _name, _color in ES_AI_CHARS:
            if cid != char_id and cid not in staying:
                try:
                    renpy.hide(cid)
                except Exception:
                    pass
        ES_AI_SHOWN[:] = [selected] + keep
        capacity = es_ai_cameo_capacity()
        for g in keep[capacity:]:
            es_ai_cameo_park(g["id"], announce=False)
        for g in ES_AI_SHOWN:
            g.pop("focused", None)
        ES_AI_LOC_HAS_GIRL[0] = True
        ES_AI_LOC_LAST_CHAR[0] = char_id
        ES_AI_LOC_LAST_EMO[0] = current_emo
        es_ai_refresh_girls()

    def es_ai_set_time(t):
        if ES_AI_CLOCK["enabled"]:
            return
        t = unicode(t or "").strip().lower()
        phase = {"morning": "morning", u"утро": "morning", "day": "day", u"день": "day",
                 "sunset": "sunset", "evening": "sunset", u"вечер": "sunset", u"закат": "sunset",
                 "night": "night", u"ночь": "night"}.get(t)
        if phase:
            es_ai_apply_time_phase(phase)

    # Список, а не dict: порядок важен для пересекающихся фраз
    # («автобус у ворот» должен определиться раньше просто «ворот»).
    ES_AI_LOC_ALIASES = [
        ("old_building_inside", (u"внутри старого корпуса", u"внутрь старого корпуса", u"старый корпус внутри",
                                 u"в старом корпусе", u"в старый корпус", u"внутри старого здания", u"old building interior", u"inside the old building")),
        ("library_ext", (u"на улице у библиотеки", u"улица библиотеки", u"у библиотеки", u"к библиотеке",
                         u"возле библиотеки", u"перед библиотекой", u"снаружи библиотеки", u"library exterior", u"outside the library")),
        ("mine_descent", (u"спуск в шахту", u"спуску в шахту", u"спуска в шахту", u"спуске в шахту", u"mine descent")),
        ("mine_room", (u"комната в шахте", u"комнату в шахте", u"комнате в шахте", u"комнаты в шахте", u"mine room")),
        ("mine_exit", (u"выход из шахты", u"выходу из шахты", u"выхода из шахты", u"выходе из шахты", u"mine exit")),
        ("mine_crossroad", (u"развилка шахты", u"развилку шахты", u"развилке шахты", u"развилки шахты", u"развилк в шахте", u"mine crossroad", u"mine junction")),
        ("mine_coalface", (u"забой шахты", u"забою шахты", u"забоя шахты", u"забое шахты", u"забой в шахте", u"mine coalface")),
        ("mine_halt", (u"привал в шахте", u"привалу в шахте", u"привала в шахте", u"привале в шахте", u"mine halt", u"mine rest stop")),
        ("bus_410", (u"автобус 410", u"автобуса 410", u"автобусу 410", u"автобусе 410", u"лиаз", u"лиазе", u"bus 410", u"liaz")),
        # раздел 28 (продолжение): контекстные подлокации — специфичные фразы идут
        # РАНЬШЕ общих, чтобы «у столовой» не спуталось со «столовой» и т.п.
        ("semen_room", (u"комната семёна", u"комнату семёна", u"комнате семёна",
                        u"в свою комнату", u"к себе в комнату", u"в мою комнату")),
        ("bus_stop", (u"автобусная остановка", u"остановка автобуса", u"на остановк", u"к остановке")),
        ("bathhouse", (u"в баню", u"из бани", u"в бане", u"баня")),
        ("musclub_inside", (u"внутрь музклуба", u"внутри музклуба", u"внутрь музыкального клуба",
                            u"внутри музыкального клуба")),
        ("dining_ext", (u"у столовой", u"возле столовой", u"около столовой",
                        u"перед столовой", u"снаружи столовой")),
        ("stage_big", (u"большая сцена", u"большой сцене", u"к большой сцене",
                       u"на концерт", u"концертная сцена")),
        ("gate_no_bus", (u"автобус уехал", u"автобуса уже нет", u"ворота без автобуса")),
        ("dv_house_ext", (u"у домика алисы", u"возле домика алисы", u"перед домиком алисы",
                          u"у домика ульяны", u"возле домика ульяны")),
        ("mt_house_ext", (u"у домика вожатой", u"возле домика вожатой",
                          u"перед домиком вожатой", u"снаружи домика вожатой")),
        ("sl_house_ext", (u"у домика слави", u"возле домика слави",
                          u"у домика жени", u"перед домиком слави")),
        ("un_house_ext", (u"у домика лены", u"возле домика лены",
                          u"у домика мику", u"перед домиком лены")),
        ("bus_gate", (u"автобус у ворот", u"к автобусу", u"возле автобуса")),
        ("bus_inside", (u"в автобус", u"внутрь автобуса", u"салон автобуса")),
        ("mt_room", (u"комната вожатой", u"комнату вожатой", u"домик вожатой", u"к ольге дмитриевне")),
        ("aidpost_inside", (u"внутрь медпункта", u"в медпункт", u"кабинет виолы")),
        ("club_room", (u"в клуб кибернетиков", u"внутрь клуба", u"к кибернетикам")),
        ("dv_room", (u"домик алисы", u"комната алисы", u"домик ульяны", u"комната ульяны")),
        ("sl_room", (u"домик слави", u"комната слави", u"домик жени", u"комната жени")),
        ("un_room", (u"домик лены", u"комната лены", u"домик мику", u"комната мику")),
        ("camp_gate", (u"ворота лагеря", u"к воротам", u"вход в лагерь")),
        ("bunker", (u"бомбоубежище", u"бомбоубежища", u"бомбоубежищу", u"бомбоубежищем",
                    u"убежище", u"убежища", u"убежищу", u"убежищем",
                    u"бункер", u"бункера", u"бункеру", u"бункере", u"бункером",
                    u"bunker", u"bomb shelter")),
        ("old_building", (u"старый корпус", u"старого корпуса", u"старое здание", u"заброшенный корпус", u"old building")),
        ("catacombs", (u"катакомб", u"подземель")),
        ("mine", (u"в шахту", u"в шахте", u"заброшенная шахта", u"в рудник", u"mine corridor")),
        ("boathouse", (u"лодочная станция", u"к лодкам", u"на причал")),
        ("washstand", (u"умывальник", u"умыться")),
        ("road", (u"дорога к лагерю", u"на дорогу", u"по дороге")),
        ("houses", (u"аллея домиков", u"жилые домики", u"между домиками")),
        ("aidpost", (u"к медпункту", u"возле медпункта")),
        ("clubs", (u"к клубам", u"возле клубов", u"здание кружков")),
        ("beach", (u"пляж", u"купаться", u"искупаться", u"плавать", u"к реке", u"на реку")),
        ("island", (u"остров",)),
        ("polyana", (u"полян",)),
        ("path", (u"троп", u"в лес", u"по лесу")),
        ("playground", (u"спортплощад", u"волейбол", u"заняться спортом")),
        ("musclub", (u"музклуб", u"музыкальн")),
        ("stage", (u"на сцен", u"к сцен")),
        ("dining", (u"столов", u"поесть", u"пообедать", u"поужинать")),
        ("library", (u"библиотек", u"почитать книг")),
        ("square", (u"на площад", u"к площад", u"по лагерю")),
    ]
    ES_AI_MOVE_WORDS = (u"пошл", u"пойд", u"идём", u"идем", u"давай", u"сходим",
                        u"сходить", u"отправ", u"перейд", u"перемест", u"гулять")

    def es_ai_location_id(value):
        """ID или русское название локации -> канонический ID."""
        import re
        if value is None:
            return None
        try:
            text = unicode(value).strip().lower()
        except Exception:
            text = str(value).strip().lower()
        if text in ES_AI_LOCATION_INDEX:
            return text
        for loc_id, aliases in ES_AI_LOC_ALIASES:
            for alias in aliases:
                if alias in text and (loc_id != "bunker" or re.search(
                        r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.UNICODE)):
                    return loc_id
        return None

    def es_ai_location_from_dialog(player_text, reply):
        """Локальный фолбэк: распознать переход даже если сервер не вернул goto."""
        import re
        try:
            player = unicode(player_text or u"").lower()
            answer = unicode(reply or u"").lower()
        except Exception:
            return None
        combined = player + u" " + answer
        # Questions and refusals must not become travel through a model reply.
        if re.search(u"\\b(?:не|нет|not|no|don't|where|где|зачем)\\b|[?]", player):
            return None
        if not any(word in combined for word in ES_AI_MOVE_WORDS):
            return None
        for loc_id, aliases in ES_AI_LOC_ALIASES:
            for alias in aliases:
                if alias in combined and (loc_id != "bunker" or re.search(
                        r"(?<!\w)" + re.escape(alias) + r"(?!\w)", combined, re.UNICODE)):
                    return loc_id
        return None

    def es_ai_apply_actions(res, player_text=None):
        """Применить goto/time; при отсутствии goto понять переход из диалога."""
        global es_ai_char_id
        if not hasattr(res, "get"):
            es_ai_log("location action skipped: response has no get()")
            return
        es_ai_log("live-chain-20261011 apply before=%s request=%r current=%r response=%r" %
                  (ES_AI_LOC_LAST_CHAR[0], res.get("_request_trace"),
                   es_ai_request_trace(ES_AI_LOC_LAST_CHAR[0], player_text) if player_text is not None else None,
                   [(key, res.get(key)) for key in ("id", "switch_primary", "goto", "dress", "movement_blocked", "travel_all", "travel_with", "cameo_aside")]))
        goto_raw = res.get("goto")
        switch = res.get("switch_primary")
        if switch:
            local = set(g["id"] for g in ES_AI_SHOWN) | set(
                g["id"] for g in ES_AI_CAMEO_NEARBY.get(ES_AI_LOC_CUR[0], []))
            eligible = set(c[0] for c in ES_AI_CHARS)
            if (not isinstance(switch, basestring) or switch not in local or switch not in eligible
                    or switch == ES_AI_LOC_LAST_CHAR[0] or (goto_raw is not None and not es_ai_location_id(goto_raw))
                    or res.get("movement_blocked") or not player_text
                    or es_ai_read_cameo_settings().get("scene_auto_primary") is not True):
                res["movement_blocked"] = True
                res["suppress_main_reply"] = True
                res["cameo"] = []
                res["cameo_requested"] = True
                es_ai_log("automatic primary rejected: invalid local transition")
                return
            previous = ES_AI_LOC_LAST_CHAR[0]
            origin = ES_AI_LOC_CUR[0]
            es_ai_girl_enter(switch, "normal")
            es_ai_char_id = switch
            es_ai_cameo_park(previous, announce=False)
            es_ai_log("live-bind-20261011 primary before=%s after=%s origin=%s shown=%r parked=%r" %
                      (previous, ES_AI_LOC_LAST_CHAR[0], origin,
                       [g["id"] for g in ES_AI_SHOWN][:16],
                       [g["id"] for g in ES_AI_CAMEO_NEARBY.get(origin, [])][:16]))
        aside = res.get("cameo_aside", [])
        if isinstance(aside, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)):
            for cid in aside:
                es_ai_cameo_park(cid, announce=False)
        loc_id = es_ai_location_id(goto_raw)
        if not loc_id and not res.get("movement_blocked"):
            loc_id = es_ai_location_from_dialog(player_text, res.get("reply", ""))
        if res.get("movement_blocked"):
            loc_id = None
        es_ai_log("location action: goto=%r fallback=%r current=%s" %
                  (goto_raw, loc_id, ES_AI_LOC_CUR[0]))
        if loc_id and loc_id != ES_AI_LOC_CUR[0]:
            requested = res.get("cameo", [])
            eligible = set(c[0] for c in ES_AI_CHARS) - {ES_AI_LOC_LAST_CHAR[0]}
            explicit_arrival = (isinstance(requested, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple))
                                and any(isinstance(c, basestring) and c in eligible for c in requested)
                                and es_ai_cameo_on())
            leaving = res.get("cameo_leave", [])
            farewell = isinstance(leaving, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)) and bool(leaving)
            es_ai_set_location(loc_id, ES_AI_LOC_LAST_CHAR[0],
                               ES_AI_LOC_LAST_EMO[0], cameo_arrive=not (explicit_arrival or farewell or switch),
                                travel_all=res.get("travel_all") is True,
                                travel_with=res.get("travel_with"))
            es_ai_log("location changed: %s" % loc_id)
        tm = res.get("time")
        if tm and not ES_AI_CLOCK["enabled"]:
            es_ai_set_time(tm)
        # Наряд по контексту: сначала явный тег сервера [action:dress:...],
        # иначе — клиентский разбор реплик и настроения. Делается ПОСЛЕ смены
        # локации, чтобы учитывать базовый наряд уже нового места.
        if not player_text and not res.get("reply") and not res.get("dress"):
            return
        es_ai_apply_party_context(player_text, res.get("reply", ""))
        active = ES_AI_LOC_LAST_CHAR[0]
        request = es_ai_cameo_clothing_request(active, player_text, unnamed=True)
        other_request = any(es_ai_cameo_clothing_request(cid, player_text) for cid, _, _ in ES_AI_CHARS if cid != active)
        dress_sig = request or (None if other_request else res.get("dress"))
        night_beach = es_ai_location().get("id") == "beach" and es_ai_clothing_night()
        romantic_swim = night_beach and es_ai_beach_romantic_clothing(player_text, res.get("reply", ""))
        if night_beach and not request and not other_request and not romantic_swim and es_ai_no_swimming(player_text):
            dress_sig = "cover"
        if dress_sig in ("swim", u"купальник", u"купаться") and not (
                request == "swim" or es_ai_current_dress() == "swim" or
                romantic_swim or
                es_ai_dress_from_context(player_text, "", es_ai_location()) == "swim"):
            dress_sig = None
        if dress_sig in ("dress", "party", u"платье") and not (request == "dress" or ES_AI_PARTY[0]):
            dress_sig = None
        if not dress_sig:
            dress_sig = None if other_request else es_ai_dress_from_context(player_text, res.get("reply", ""),
                                                  es_ai_location())
        if dress_sig in ("swim", u"купальник", u"купаться") and ES_AI_LOC_CUR[0] == "beach" and ES_AI_DRESS[0] is None and es_ai_default_dress() == "swim" and not request and es_ai_dress_from_context(player_text, "", es_ai_location()) != "swim":
            dress_sig = None  # A model echo of the location default is not player authorization.
        if dress_sig:
            es_ai_set_dress(dress_sig)
            es_ai_log("dress -> %s (%s)" % (ES_AI_DRESS[0], dress_sig))
        es_ai_log("live-chain-20261011 applied active=%s location=%s party=%s dress=%r shown=%r" %
                  (ES_AI_LOC_LAST_CHAR[0], ES_AI_LOC_CUR[0], ES_AI_PARTY[0], ES_AI_DRESS[0],
                   [(g["id"], g.get("dress"), g.get("tag")) for g in ES_AI_SHOWN][:16]))

    def es_ai_location():
        return ES_AI_LOCATION_INDEX.get(ES_AI_LOC_CUR[0], ES_AI_LOCATION_INDEX["square"])

    def es_ai_loc_bg(loc):
        suffix = {"morning": "day", "day": "day", "sunset": "sunset", "night": "night"}[ES_AI_TIME[0]]
        # Для фонов без суффикса _day (например ext_bus) задаём варианты явно.
        explicit = loc.get("time_bgs", {}).get(suffix, [])
        out = list(explicit)
        if suffix == "sunset":
            # Daytime sunset placeholders must not hide available night assets.
            out = [bg for bg in explicit if "_sunset" in bg]
            for bg in loc["bgs"]:
                if "_day" in bg:
                    out.append(bg.replace("_day", "_sunset"))
                elif "_sunset" in bg:
                    out.append(bg)
            out.extend(loc.get("time_bgs", {}).get("night", []))
            for bg in loc["bgs"]:
                if "_day" in bg:
                    out.append(bg.replace("_day", "_night"))
                elif "_night" in bg:
                    out.append(bg)
            out.extend(explicit)
        for bg in loc["bgs"]:
            if suffix != "day" and "_day" in bg:
                out.append(bg.replace("_day", "_" + suffix))
            out.append(bg)
        for bg in out:
            if renpy.has_image(bg):
                return bg
        return loc["bgs"][0]

    def es_ai_clothing_night():
        minutes = ES_AI_CLOCK.get("minutes")
        if ES_AI_CLOCK.get("enabled") and isinstance(minutes, (_es_ai_cameo_builtins.int, _es_ai_cameo_builtins.float)) and not isinstance(minutes, _es_ai_cameo_builtins.bool) and 0 <= minutes < 1440:
            return minutes >= 1320 or minutes < 360
        return ES_AI_TIME[0] == "night"

    def es_ai_default_dress(loc=None):
        loc = es_ai_location() if loc is None else loc
        if loc.get("id") == "beach" and es_ai_clothing_night():
            return None
        return loc.get("dress")

    def es_ai_no_swimming(text):
        import re
        return bool(re.search(u"\\b(?:купаться\\s*(?:ночью\\s*)?не\\s*будем|не\\s*будем\\s*купаться|не\\s*хочу\\s*купаться)\\b", unicode(text or u"").lower(), re.UNICODE))

    def es_ai_beach_romantic_clothing(player_text, reply):
        import re
        cid = ES_AI_LOC_LAST_CHAR[0]
        player = unicode(player_text or u"").lower()
        answer = unicode(reply or u"").lower()
        # Affection alone is not an outfit request; require a voluntary clothing reply.
        return (cid in ES_AI_ROMANCEABLE and cid not in ("us", "uv")
                and cid in es_ai_cameo_adult_home_ids()
                and bool(es_ai_location().get("romantic"))
                and bool(re.search(u"\\b(?:поцелу\\w*|обним\\w*|люблю тебя|свидание)\\b", player, re.UNICODE))
                and not bool(re.search(u"\\b(?:не|нет|not)\\b|[?]", player + u" " + answer, re.UNICODE))
                and bool(re.search(u"\\b(?:да|хочу|согласна|давай)\\b", answer, re.UNICODE))
                and bool(re.search(u"\\b(?:надену|переоденусь)\\s+(?:в\\s+)?(?:купальник|бикини)\\b", answer, re.UNICODE)))

    def es_ai_current_dress():
        """Актуальный предпочтительный наряд с учётом контекста.

        Базовый наряд локации (у воды — купальник) действует по умолчанию,
        а контекст разговора/настроения может его переопределить:
        cover -> вернуть форму, swim -> купальник, sport -> спортивная.
        """
        loc = es_ai_location()
        base = es_ai_default_dress(loc)
        ov = ES_AI_DRESS[0]
        if ov == "swim":
            return "swim"
        if ov in ("sport", "dress"):
            return ov
        if ov == "cover":
            return None
        return base

    def es_ai_loc_dress_pref():
        return es_ai_current_dress()

    def es_ai_set_dress(sig):
        """Установить контекстный наряд и сразу переодеть героиню на сцене."""
        try:
            sig = unicode(sig or u"").strip().lower()
        except Exception:
            sig = str(sig or "").strip().lower()
        table = {u"swim": "swim", u"купальник": "swim", u"купаться": "swim",
                 u"dress": "dress", u"party": "dress", u"платье": "dress",
                 u"sport": "sport", u"спорт": "sport", u"спортивн": "sport",
                 u"cover": "cover", u"форма": "cover", u"форму": "cover",
                 u"pioneer": "cover", u"одеть": "cover", u"normal": "cover"}
        val = table.get(sig)
        if not val:
            return
        if val == "dress" and not es_ai_has_party_dress(ES_AI_LOC_LAST_CHAR[0]):
            return
        if ES_AI_DRESS[0] != val:
            ES_AI_DRESS[0] = val
            if ES_AI_SHOWN:
                es_ai_refresh_girls()

    def es_ai_apply_party_context(player_text, reply):
        ES_AI_CAMEO_PLAYER_TEXT[0] = player_text or u""
        active = ES_AI_LOC_LAST_CHAR[0]
        requests = {cid: es_ai_cameo_clothing_request(cid, player_text, unnamed=(cid == active))
                    for cid, _, _ in ES_AI_CHARS}
        event = es_ai_party_context(player_text)
        es_ai_log("live-bind-20261011 party active=%s event=%r previous=%s requests=%r" %
                  (active, event, ES_AI_PARTY[0],
                   [(cid, request) for cid, request in requests.items() if request][:16]))
        # A question/rejection cannot be turned into intent by the model reply.
        import re
        if event is None and not any(requests.values()) and not re.search(
                u"\\b(?:где|когда|зачем|не|нет|where|when|why|not)\\b|[?]", unicode(player_text or u"").lower()):
            public_reply = unicode(reply or u"").lower()
            if re.search(u"\\b(?:готовимся|готовим|танцуем|начался|началась|ид[её]т)\\b", public_reply):
                event = es_ai_party_context(public_reply)
        if not any(requests.values()) and event is not None:
            ES_AI_PARTY[0] = event
        for g in ES_AI_SHOWN:
            cid = g["id"]
            request = requests.get(cid)
            if g.get("cameo"):
                g["dress"] = es_ai_cameo_dress(request, g.get("dress"), g)
            elif request:
                es_ai_set_dress(request)
            elif ES_AI_PARTY[0] and ES_AI_DRESS[0] not in ("cover", "swim", "sport"):
                es_ai_set_dress("dress")
            elif event is False and ES_AI_DRESS[0] == "dress":
                ES_AI_DRESS[0] = None
        if ES_AI_SHOWN:
            es_ai_refresh_girls()

    def es_ai_dress_from_context(player_text, reply, loc):
        """Определить наряд по репликам и настроению (клиентский фолбэк).

        Возвращает 'swim' / 'cover' / None (None — оставить как есть).
        У воды купальник и так базовый, поэтому здесь важнее обратный случай:
        похолодало/серьёзный разговор -> вернуть форму; а в романтических
        локациях или вечером интимный настрой -> купальник.
        """
        request = es_ai_cameo_clothing_request(ES_AI_LOC_LAST_CHAR[0], player_text, unnamed=True)
        if request:
            return request
        if loc.get("id") == "beach" and es_ai_clothing_night() and es_ai_no_swimming(player_text):
            return "cover"
        import re
        if re.search(u"\\bне\\s+(?:надень|надевай|переоденься|оденься|прикройся)\\b", unicode(player_text or u"").lower()):
            return None
        if ES_AI_PARTY[0] and ES_AI_DRESS[0] not in ("cover", "swim", "sport"):
            return "dress"
        try:
            combined = unicode(player_text or u"").lower()
        except Exception:
            return None
        if any(w in combined for w in ES_AI_DRESS_SWIM_WORDS):
            return "swim"
        if any(w in combined for w in ES_AI_DRESS_COVER_WORDS):
            return "cover"
        # Романтическое переодевание — только для романсибельных (совершеннолетних)
        # героинь. Для Ульяны (ребёнок) романтический переход в купальник запрещён.
        romantic_place = bool(loc.get("romantic")) or ES_AI_TIME[0] in ("sunset", "night")
        if loc.get("id") == "beach" and es_ai_clothing_night():
            return None
        if (romantic_place and es_ai_char_id in ES_AI_ROMANCEABLE
                and any(w in combined for w in ES_AI_DRESS_ROMANTIC_WORDS)):
            return "swim"
        return None

    def es_ai_neighbors_text():
        """Человекочитаемые имена соседних локаций (для подсказки нейросети)."""
        names = []
        for nid in ES_AI_MAP.get(ES_AI_LOC_CUR[0], []):
            n = ES_AI_LOCATION_INDEX.get(nid)
            if n:
                names.append(n["name"])
        return u", ".join(names)

    def es_ai_location_context():
        """Описание текущего места + логичные соседи — уходит в контекст LLM."""
        loc = es_ai_location()
        desc = loc.get("desc", u"")
        if loc.get("id") == "beach" and es_ai_clothing_night():
            desc = u"вы на ночном пляже у реки: песок, шум воды и звёзды; обычная одежда по умолчанию, купание не подразумевается"
        nb = es_ai_neighbors_text()
        if nb:
            desc = desc + u". Отсюда рядом и логично пройти к: " + nb
        return desc

init 10 python:
    def es_ai_loc_set(loc_id):
        """Смена локации из меню чата: фон, героиня, контекст для нейросети."""
        es_ai_set_location(loc_id, char_id=ES_AI_LOC_LAST_CHAR[0],
                           emotion=ES_AI_LOC_LAST_EMO[0])

    def es_ai_set_location(loc_id, char_id=None, emotion=None, cameo_arrive=True, travel_all=False, travel_with=None):
        """Сменить локацию: фон + вернуть героиню в подходящей одежде."""
        loc = ES_AI_LOCATION_INDEX.get(loc_id)
        if not loc:
            return
        changed = loc["id"] != ES_AI_LOC_CUR[0]
        # Новая локация -> вернуть базовый наряд (у воды это купальник).
        # При простом обновлении фона (смена времени суток) наряд не сбрасываем.
        if changed:
            globals().get("ES_AI_ACTIVITY_PENDING", {}).clear()
            ES_AI_PARTY[0] = False
            selected = (set(cid for cid in travel_with if isinstance(cid, basestring))
                        if isinstance(travel_with, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple))
                        else set(g["id"] for g in ES_AI_SHOWN if g.get("cameo")) if travel_all else set())
            local = set(g["id"] for g in ES_AI_SHOWN) | set(g["id"] for g in ES_AI_CAMEO_NEARBY.get(ES_AI_LOC_CUR[0], []))
            for cid in selected & local:
                if not any(g["id"] == cid for g in ES_AI_SHOWN):
                    es_ai_cameo_enter(cid, "normal", stay=True)
            for g in _es_ai_cameo_builtins.list(ES_AI_SHOWN):
                if g.get("cameo") and g["id"] not in selected:
                    es_ai_cameo_park(g["id"], announce=False)
            for g in ES_AI_SHOWN:
                es_ai_cameo_take_nearby(g["id"])
            ES_AI_DRESS[0] = None
            try:
                ES_AI_RECENT_LINES[:] = []
            except Exception:
                pass
        ES_AI_LOC_CUR[0] = loc["id"]
        if changed:
            for g in ES_AI_SHOWN:
                if g.get("cameo"):
                    g["dress"] = es_ai_cameo_dress()
                    g["dress_reason"] = "location"
                    g["dress_location"] = loc["id"]
            if ES_AI_SHOWN:
                es_ai_recent_push("Narrator", "The company moved together to %s: %s." %
                    (loc["id"], ", ".join(es_ai_cameo_name(g["id"]) for g in ES_AI_SHOWN)))
            for record in ES_AI_CAMEO_NEARBY.get(loc["id"], []):
                es_ai_recent_push("Narrator", u"%s: остаётся неподалёку, вне разговора. %s" %
                    (es_ai_cameo_name(record["id"]), record.get("activity", u"")))
        try:
            es_ai_report_loc(loc["id"])
        except Exception:
            pass
        renpy.scene()
        _bg = es_ai_loc_bg(loc)
        es_ai_log("location bg -> %s (loc=%s phase=%s)" %
                  (_bg, loc["id"], ES_AI_TIME[0]))
        renpy.show(_bg)  # es_ai_loc_bg учитывает время суток
        if ES_AI_SHOWN:
            es_ai_refresh_girls()
        renpy.with_statement(dissolve)
        if changed and cameo_arrive:
            # При входе в локацию кто-то может уже быть на месте.
            try:
                es_ai_cameo_on_arrive()
            except Exception:
                pass
