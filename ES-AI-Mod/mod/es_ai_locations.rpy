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
         "bgs": ["bg int_library_day", "bg ext_library_day"], "dress": None,
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
         "bgs": ["bg ext_old_building_night", "bg int_old_building_night"], "dress": None,
         "desc": u"вы у заброшенного старого корпуса лагеря; вокруг темно и тревожно"},
        {"id": "catacombs", "name": u"Катакомбы", "context_only": True,
         "bgs": ["bg int_catacombs_entrance", "bg int_catacombs_living"], "dress": None,
         "desc": u"вы в подземных катакомбах под старым корпусом"},
        {"id": "mine", "name": u"Шахта", "context_only": True,
         "bgs": ["bg int_mine", "bg int_mine_crossroad", "bg int_mine_room",
                 "bg int_mine_coalface", "bg int_mine_halt"], "dress": None,
         "desc": u"вы в тёмной заброшенной шахте под лагерем"},
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
    ES_AI_CLOCK = dict(minutes=None, revision=None, enabled=False, lines=0, generation=0)

    def es_ai_clock_settings():
        import io
        import os
        import json
        st = dict(enabled=False, start_time="08:00", minutes_per_exchange=5, revision=0)
        try:
            path = es_ai_user_config_path()
        except NameError:
            path = os.path.join(ES_AI_SERVER_DIR, "config.json")
        try:
            with io.open(path, "r", encoding="utf-8-sig") as stream:
                data = json.load(stream)
            raw = data.get("game_clock") if isinstance(data, _es_ai_cameo_builtins.dict) else None
            if isinstance(raw, _es_ai_cameo_builtins.dict):
                st.update((k, raw[k]) for k in st if k in raw)
        except Exception:
            pass
        st["enabled"] = st["enabled"] is True
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
                if isinstance(value, _es_ai_cameo_builtins.bool):
                    raise ValueError(key)
                value = int(value)
                st[key] = _es_ai_cameo_builtins.max(0, value)
                if upper is not None:
                    st[key] = _es_ai_cameo_builtins.min(upper, st[key])
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
        if changed and redraw:
            # No movement, NPC lifecycle, context reset, or layout reroll.
            renpy.scene()
            renpy.show(es_ai_loc_bg(es_ai_location()))
            es_ai_refresh_girls()
            renpy.with_statement(dissolve)

    def es_ai_clock_sync(redraw=True, force=False):
        st = es_ai_clock_settings()
        was_enabled = ES_AI_CLOCK["enabled"]
        ES_AI_CLOCK["enabled"] = st["enabled"]
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
        return es_ai_clock_snapshot()["time"] if ES_AI_CLOCK["enabled"] else ""

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
    ES_AI_GIRL_LAYOUT = [None, {}]  # Last (location, sorted IDs, primary ID) and slots.
    ES_AI_DRESS = [None]   # контекстный наряд В ПРЕДЕЛАХ локации: None|"swim"|"cover"|"sport"

    # --- Карта лагеря (соседство локаций): переходы должны быть логичны ---
    # Не жёсткое ограничение — используется, чтобы подсказать нейросети, куда
    # логично пройти отсюда (список соседей уходит в контекст /chat и /initiative).
    ES_AI_MAP = {
        "square": ["houses", "dining_ext", "clubs", "musclub", "library", "stage",
                   "playground", "aidpost", "path", "camp_gate", "semen_room"],
        "camp_gate": ["square", "bus_gate", "gate_no_bus", "road"],
        "bus_gate": ["camp_gate", "gate_no_bus", "bus_inside"],
        "gate_no_bus": ["camp_gate", "bus_gate", "road"],
        "bus_inside": ["bus_gate"],
        "bus_stop": ["road"],
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
        "library": ["square"],
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
        "old_building": ["polyana", "path", "catacombs"],
        "catacombs": ["old_building", "mine"], "mine": ["catacombs"],
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


    def es_ai_girls_reset():
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
            # Cameos keep per-NPC clothing, including water-location swim defaults,
            # independently of the active heroine's contextual dress.
            dp = g["dress"] if ("dress" in g) else es_ai_loc_dress_pref()
            tag = es_ai_resolve_sprite(g["id"], g["emo"], dress_pref=dp)
            g["tag"] = tag
            if tag:
                # Focus clears every row without changing the speaker's slot.
                z = row_z + 300 - ES_AI_HEIGHTS.get(g["id"], 160)
                z += 2000 if g.get("focused") else (50 if not g.get("cameo") else 0)
                try:
                    renpy.show(tag, at_list=[Transform(xpos=float(x), xanchor=0.5,
                        yalign=1.0, zoom=zoom, yoffset=yoffset)], zorder=z)
                except Exception as e:
                    es_ai_log("girl show error: %s" % e)

    def es_ai_girl_enter(char_id, emotion):
        """Показать выбранную героиню и убрать предыдущую.

        У разных героинь разные image-теги (un, dv, sl...), поэтому обычный
        renpy.show() не заменяет прошлый спрайт автоматически.
        """
        current_emo = emotion or "normal"
        if any(not g.get("cameo") and g["id"] != char_id for g in ES_AI_SHOWN):
            es_ai_cameo_clear()
        for g in ES_AI_SHOWN:
            if g.get("id") == char_id and not emotion:
                current_emo = g.get("emo") or "normal"

        # Оставшиеся в сцене камео не уходят, когда говорит героиня: их записи
        # и спрайты сохраняем, прячем только «чужие» теги.
        keep = [g for g in ES_AI_SHOWN if g.get("cameo") and g["id"] != char_id]
        es_ai_cameo_unregister(char_id)
        es_ai_cameo_take_nearby(char_id)
        staying = set(g["id"] for g in keep)
        for cid, _name, _color in ES_AI_CHARS:
            if cid != char_id and cid not in staying:
                try:
                    renpy.hide(cid)
                except Exception:
                    pass
        ES_AI_SHOWN[:] = [{"id": char_id, "emo": current_emo}] + keep
        for g in ES_AI_SHOWN:
            g.pop("focused", None)
        ES_AI_LOC_HAS_GIRL[0] = True
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
        ("old_building", (u"старый корпус", u"старое здание", u"заброшенный корпус")),
        ("catacombs", (u"катакомб", u"подземель")),
        ("mine", (u"в шахту", u"заброшенная шахта", u"в рудник")),
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
                if alias in text:
                    return loc_id
        return None

    def es_ai_location_from_dialog(player_text, reply):
        """Локальный фолбэк: распознать переход даже если сервер не вернул goto."""
        try:
            player = unicode(player_text or u"").lower()
            answer = unicode(reply or u"").lower()
        except Exception:
            return None
        combined = player + u" " + answer
        if not any(word in combined for word in ES_AI_MOVE_WORDS):
            return None
        for loc_id, aliases in ES_AI_LOC_ALIASES:
            for alias in aliases:
                if alias in combined:
                    return loc_id
        return None

    def es_ai_apply_actions(res, player_text=None):
        """Применить goto/time; при отсутствии goto понять переход из диалога."""
        if not hasattr(res, "get"):
            es_ai_log("location action skipped: response has no get()")
            return
        goto_raw = res.get("goto")
        loc_id = es_ai_location_id(goto_raw)
        if not loc_id:
            loc_id = es_ai_location_from_dialog(player_text, res.get("reply", ""))
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
                               ES_AI_LOC_LAST_EMO[0], cameo_arrive=not (explicit_arrival or farewell),
                               travel_all=res.get("travel_all") is True)
            es_ai_log("location changed: %s" % loc_id)
        tm = res.get("time")
        if tm and not ES_AI_CLOCK["enabled"]:
            es_ai_set_time(tm)
        # Наряд по контексту: сначала явный тег сервера [action:dress:...],
        # иначе — клиентский разбор реплик и настроения. Делается ПОСЛЕ смены
        # локации, чтобы учитывать базовый наряд уже нового места.
        dress_sig = res.get("dress")
        if not dress_sig:
            dress_sig = es_ai_dress_from_context(player_text, res.get("reply", ""),
                                                 es_ai_location())
        if dress_sig:
            es_ai_set_dress(dress_sig)
            es_ai_log("dress -> %s (%s)" % (ES_AI_DRESS[0], dress_sig))

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

    def es_ai_current_dress():
        """Актуальный предпочтительный наряд с учётом контекста.

        Базовый наряд локации (у воды — купальник) действует по умолчанию,
        а контекст разговора/настроения может его переопределить:
        cover -> вернуть форму, swim -> купальник, sport -> спортивная.
        """
        loc = es_ai_location()
        base = loc.get("dress")
        ov = ES_AI_DRESS[0]
        if ov == "swim":
            return "swim"
        if ov == "sport":
            return "sport"
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
                 u"sport": "sport", u"спорт": "sport", u"спортивн": "sport",
                 u"cover": "cover", u"форма": "cover", u"форму": "cover",
                 u"pioneer": "cover", u"одеть": "cover", u"normal": "cover"}
        val = table.get(sig)
        if not val:
            return
        if ES_AI_DRESS[0] != val:
            ES_AI_DRESS[0] = val
            if ES_AI_SHOWN:
                es_ai_refresh_girls()

    def es_ai_dress_from_context(player_text, reply, loc):
        """Определить наряд по репликам и настроению (клиентский фолбэк).

        Возвращает 'swim' / 'cover' / None (None — оставить как есть).
        У воды купальник и так базовый, поэтому здесь важнее обратный случай:
        похолодало/серьёзный разговор -> вернуть форму; а в романтических
        локациях или вечером интимный настрой -> купальник.
        """
        try:
            combined = (unicode(player_text or u"") + u" " + unicode(reply or u"")).lower()
        except Exception:
            return None
        if any(w in combined for w in ES_AI_DRESS_SWIM_WORDS):
            return "swim"
        if any(w in combined for w in ES_AI_DRESS_COVER_WORDS):
            return "cover"
        # Романтическое переодевание — только для романсибельных (совершеннолетних)
        # героинь. Для Ульяны (ребёнок) романтический переход в купальник запрещён.
        romantic_place = bool(loc.get("romantic")) or ES_AI_TIME[0] in ("sunset", "night")
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
        nb = es_ai_neighbors_text()
        if nb:
            desc = desc + u". Отсюда рядом и логично пройти к: " + nb
        return desc

init 10 python:
    def es_ai_loc_set(loc_id):
        """Смена локации из меню чата: фон, героиня, контекст для нейросети."""
        es_ai_set_location(loc_id, char_id=ES_AI_LOC_LAST_CHAR[0],
                           emotion=ES_AI_LOC_LAST_EMO[0])

    def es_ai_set_location(loc_id, char_id=None, emotion=None, cameo_arrive=True, travel_all=False):
        """Сменить локацию: фон + вернуть героиню в подходящей одежде."""
        loc = ES_AI_LOCATION_INDEX.get(loc_id)
        if not loc:
            return
        changed = loc["id"] != ES_AI_LOC_CUR[0]
        # Новая локация -> вернуть базовый наряд (у воды это купальник).
        # При простом обновлении фона (смена времени суток) наряд не сбрасываем.
        if changed:
            if not travel_all:
                for g in _es_ai_cameo_builtins.list(ES_AI_SHOWN):
                    if g.get("cameo"):
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
        renpy.show(es_ai_loc_bg(loc))  # es_ai_loc_bg учитывает время суток
        if ES_AI_SHOWN:
            es_ai_refresh_girls()
        renpy.with_statement(dissolve)
        if changed and cameo_arrive:
            # При входе в локацию кто-то может уже быть на месте.
            try:
                es_ai_cameo_on_arrive()
            except Exception:
                pass
