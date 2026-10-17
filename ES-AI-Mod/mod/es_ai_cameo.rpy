# -*- coding: utf-8 -*-
# AI Совёнок — камео: с некоторой вероятностью в сцену заходит другой персонаж
# (как в сюжете). Вероятность выше в романтический момент, максимальна — если это
# комната «хозяина» локации (например вожатая застаёт вас у неё в комнате).
#
# Поведение настраивается (окно настроек, вкладка «Промпты» / кнопки в игре):
#   * частота — базовый шанс появления за один обмен (не слишком часто/редко);
#   * зашедшие — случайные персонажи, случайное количество (обычно 1, иногда 2);
#   * «остаются в сцене» — зашедший не уходит после одной фразы, а продолжает
#     рандомно вклиниваться в разговор (в тему по контексту или без контекста),
#     до собственного aside или явного прощания игрока;
#   * при входе в локацию кто-то может уже быть на месте.

init -10 python:
    import random as _es_random
    # Ren'Py store shadows builtins, including container types used by JSON.
    import __builtin__ as _es_ai_cameo_builtins

    if getattr(persistent, "es_ai_cameo", None) is None:
        persistent.es_ai_cameo = True      # включены ли внезапные появления

    # Кто может зайти в данную локацию (id персонажей). Первые в списке —
    # наиболее вероятные (обычно «хозяева» места).
    ES_AI_CAMEO_BY_LOC = {
        "mt_room": ["mt"], "mt_house_ext": ["mt"],
        "dv_room": ["dv", "us"], "dv_house_ext": ["dv", "us"],
        "sl_room": ["sl", "mz"], "sl_house_ext": ["sl", "mz"],
        "un_room": ["un", "mi"], "un_house_ext": ["un", "mi"],
        "semen_room": ["mt", "us"],
        "aidpost_inside": ["cs", "el"], "aidpost": ["cs", "el", "mt"],
        "library": ["mz", "us", "sh"],
        "club_room": ["el", "sh"], "clubs": ["el", "sh", "us"],
        "musclub": ["mi", "un"], "musclub_inside": ["mi", "un"],
        "dining": ["mt", "us", "sl", "el"], "dining_ext": ["mt", "us", "uv"],
        "beach": ["us", "mi", "dv", "sl", "un", "el", "sh", "mz", "mt", "cs"],
        "island": ["us", "dv"], "boathouse": ["us", "uv"],
        "bathhouse": ["us", "mi", "dv", "sl", "un", "el", "sh", "mz", "mt", "cs"],
        "playground": ["us", "sl"], "washstand": ["us", "mi"],
        "square": ["mt", "us", "sl", "dv", "el", "cs"], "houses": ["mt", "us", "sl"],
        "path": ["mz", "mi", "uv", "cs"], "polyana": ["mz", "un", "sl", "uv"],
        "stage": ["mi", "sl", "uv"], "stage_big": ["mi", "sl", "uv"],
        "camp_gate": ["mt"], "gate_no_bus": ["mt"], "road": ["mt"],
        "bus_gate": ["mt"], "bus_inside": ["us", "dv"],
        "old_building": ["uv", "sh", "el"], "catacombs": ["uv", "cs", "sh"],
        "bunker": ["uv", "cs", "sh"], "mine": ["uv", "sh"],
        "old_building_inside": ["uv", "sh", "el"], "library_ext": ["mz", "us", "sh"],
        "mine_descent": ["uv", "cs", "sh"], "mine_room": ["uv", "sh"],
        "mine_exit": ["uv", "sh"], "mine_crossroad": ["uv", "sh"],
        "mine_coalface": ["uv", "sh"], "mine_halt": ["uv", "sh"],
        "bus_410": ["mt"],
    }

    # «Хозяева» локаций — они застают вас с повышенной вероятностью.
    ES_AI_LOC_OWNERS = {
        "mt_room": ["mt"], "mt_house_ext": ["mt"],
        "dv_room": ["dv", "us"], "dv_house_ext": ["dv", "us"],
        "sl_room": ["sl", "mz"], "sl_house_ext": ["sl", "mz"],
        "un_room": ["un", "mi"], "un_house_ext": ["un", "mi"],
        "aidpost_inside": ["cs"], "aidpost": ["cs"],
        "semen_room": ["mt"], "library": ["mz"],
        "club_room": ["el", "sh"], "clubs": ["el", "sh"], "musclub_inside": ["mi"],
        "old_building": ["uv"], "catacombs": ["uv"], "mine": ["uv"],
    }

    # Базовые вероятности для романтических моментов (масштабируются частотой).
    ES_AI_CAMEO_P_OWNER = 0.55     # хозяин(ка) застаёт в свой комнате при романтике
    ES_AI_CAMEO_P_ROMANTIC = 0.22  # романтика в романтической локации
    ES_AI_CAMEO_P_ROMANTIC_OTHER = 0.12
    ES_AI_CAMEO_COOLDOWN = 5       # столько реплик тишины после камео
    ES_AI_CAMEO_CD = [0]
    ES_AI_CAMEO_P_COMPANION = 0.30 # шанс, что вместе зайдёт ещё один персонаж
    # «Неразлучные» пары — заходят вместе охотнее (по канону дружат).
    ES_AI_CAMEO_PAIRS = [("dv", "us"), ("dv", "un"), ("un", "mi"), ("sl", "us"),
                         ("mi", "sl"), ("mt", "us"), ("el", "sh"), ("el", "cs"),
                         ("uv", "cs")]

    # Запасные реплики, если сервер недоступен. «caught» — застали за романтикой.
    ES_AI_CAMEO_CAUGHT = {
        "mt": [u"(злость) Так-так! И что здесь происходит?",
               u"(серьёзность) Это лагерь, а не место для свиданий.",
               u"(шок) Кхм! Я, кажется, крайне не вовремя."],
        "dv": [u"(усмешка) Оба-на. Не помешала, голубки?",
               u"(злость) Эй! Вы вообще совесть имеете?"],
        "us": [u"(смех) Ага-а! Я всё-всё видела!",
               u"(удивление) Ой… а вы тут чем это занимаетесь?"],
        "sl": [u"(смущение) Ой… простите, я не хотела мешать!",
               u"(удивление) Ой! Я… я попозже зайду."],
        "sh": [u"(испуг) Э-это не то, что вы думаете! Я просто шёл мимо!",
               u"(смущение) Ой. Я... я лучше в клуб вернусь."],
        "mz": [u"(злость) Вы вообще видели табличку «тихо»? Библиотека, между прочим.",
               u"(недовольство) Ну и ну. Я это не читала, и вам не советую."],
        "cs": [u"(нормально) Дверь полагается закрывать. И не только дверь.",
               u"(улыбка) Пионер, в медпункте обычно лечатся, а не прячутся."],
        "mi": [u"(смех) Ня! А что это вы делаете?",
               u"(удивление) Ой-ой, я не вовремя, да?"],
        "un": [u"(смущение) Я… я лучше потом зайду!",
               u"(шок) Ой… п-простите."],
    }
    ES_AI_CAMEO_PASSBY = {
        "mt": [u"(нормально) Всё в порядке? Не задерживайтесь тут.",
               u"(нормально) Потом зайди ко мне."],
        "dv": [u"(усмешка) О, вы всё ещё тут?"],
        "us": [u"(смех) Приве-ет! А я тут мимо пробегала!"],
        "sl": [u"(улыбка) Ой, привет! Хорошо проводите время?"],
        "sh": [u"(нормально) Я в клуб. Если Электроник спросит — я уже иду."],
        "mz": [u"(нормально) Книгу на место. Сам знаешь, где стеллаж."],
        "cs": [u"(нормально) Если что-то болит — приходи в медпункт, а не терпи."],
        "mi": [u"(улыбка) Коннитива! Не буду мешать, ня."],
        "un": [u"(смущение) А, привет… я просто проходила мимо."],
    }

    # Настройки камео. Окно настроек и кнопки в игре пишут их в config.json
    # рядом с сервером; мод читает файл на каждом шаге — правки «на лету».
    ES_AI_CAMEO_DEFAULTS = {
        "cameo_enabled": True,
        "cameo_freq": 25,        # базовый шанс появления за обмен, %
        "cameo_stay": True,      # зашедшие остаются в сцене и продолжают говорить
        "cameo_stay_lines": 2,   # Legacy setting; no longer a departure budget.
        "cameo_interject": 35,   # шанс реплики остающегося камео за обмен, %
        "cameo_ctx": 70,         # доля реплик «в тему» (по контексту разговора), %
        "cameo_max_extra": 6,    # Six extras plus the active character: seven total.
        "scene_auto_primary": False,
        "npc_activity_enabled": True,
    }

    # Staying NPCs: id, dwell turns, optional skip_tick.
    ES_AI_CAMEO_ACTIVE = []
    ES_AI_CAMEO_NEARBY = {}  # Location -> parked per-NPC sprite/dwell records.
    ES_AI_SCENE_ABSENT = {}  # Location -> explicit departures with unknown destination.
    # Хвост последних реплик сцены для контекста LLM: [{"who", "what"}].
    ES_AI_RECENT_LINES = []
    ES_AI_PUBLIC_EVENTS = []
    ES_AI_PUBLIC_SESSION = [None, 0]
    ES_AI_CAMEO_PLAYER_TEXT = [u""]  # Only the current exchange, never history.

    # Фолбэк для режима «остался в сцене», если сервер недоступен.
    ES_AI_CAMEO_STAY_FALLBACK = [
        u"(нормально) А о чём вы тут разговариваете?",
        u"(смех) Можно и мне пару слов вставить?",
        u"(удивление) О, я вам, кажется, мешаю?",
        u"(улыбка) Расскажите и мне, интересно же!",
        u"(нормально) Эй, не забывайте про меня!",
    ]


init 10 python:
    def es_ai_cameo_name(cid):
        for c, n, _col in ES_AI_CHARS:
            if c == cid:
                return n
        return u"героиней"

    def es_ai_is_romantic_moment(active_id, player_text, reply):
        """Был ли последний обмен романтическим (для повышения шанса камео).
        С ребёнком (не-романсибельная активная героиня) романтики не бывает."""
        if active_id not in ES_AI_ROMANCEABLE:
            return False
        loc = es_ai_location()
        try:
            combined = (unicode(player_text or u"") + u" " + unicode(reply or u"")).lower()
        except Exception:
            return False
        rp = bool(loc.get("romantic")) or ES_AI_TIME[0] in ("sunset", "night")
        return rp and any(w in combined for w in ES_AI_DRESS_ROMANTIC_WORDS)

    # ---------------------------------------------------------- настройки --

    def es_ai_read_cameo_settings():
        """Настройки камео из config.json (с дефолтами и приведением типов)."""
        import os
        import json
        st = dict(ES_AI_CAMEO_DEFAULTS)
        try:
            import io
            path = os.path.join(ES_AI_SERVER_DIR, "config.json")
            f = io.open(path, "r", encoding="utf-8")
            try:
                data = json.load(f)
            finally:
                f.close()
            if isinstance(data, _es_ai_cameo_builtins.dict):
                for k in st:
                    if k in data:
                        st[k] = data[k]
        except Exception:
            pass
        st["scene_auto_primary"] = st["scene_auto_primary"] is True
        st["npc_activity_enabled"] = st["npc_activity_enabled"] is True
        if not st["npc_activity_enabled"]:
            globals().get("ES_AI_ACTIVITY_PENDING", {}).clear()
        st["cameo_enabled"] = bool(st["cameo_enabled"])
        st["cameo_stay"] = bool(st["cameo_stay"])
        for k in ("cameo_freq", "cameo_stay_lines", "cameo_interject",
                  "cameo_ctx", "cameo_max_extra"):
            try:
                st[k] = int(st[k])
            except Exception:
                st[k] = ES_AI_CAMEO_DEFAULTS[k]
        st["cameo_freq"] = _es_ai_cameo_builtins.max(0, _es_ai_cameo_builtins.min(100, st["cameo_freq"]))
        st["cameo_stay_lines"] = _es_ai_cameo_builtins.max(1, _es_ai_cameo_builtins.min(4, st["cameo_stay_lines"]))
        st["cameo_interject"] = _es_ai_cameo_builtins.max(0, _es_ai_cameo_builtins.min(100, st["cameo_interject"]))
        st["cameo_ctx"] = _es_ai_cameo_builtins.max(0, _es_ai_cameo_builtins.min(100, st["cameo_ctx"]))
        st["cameo_max_extra"] = _es_ai_cameo_builtins.max(1, _es_ai_cameo_builtins.min(6, st["cameo_max_extra"]))
        return st

    def es_ai_cameo_capacity(loc_id=None, st=None):
        """Total extra-participant limit, not the number of visible sprites."""
        if st is None:
            st = es_ai_read_cameo_settings()
        loc_id = loc_id or ES_AI_LOC_CUR[0]
        if loc_id in ("mt_room", "dv_room", "sl_room", "un_room", "semen_room"):
            cap = 2
        elif loc_id in ("beach", "square", "stage_big", "playground"):
            cap = 6
        elif loc_id in ("dining", "dining_ext", "stage", "bathhouse", "houses", "clubs"):
            cap = 5
        else:
            cap = 3
        return _es_ai_cameo_builtins.max(1, _es_ai_cameo_builtins.min(6, cap, st["cameo_max_extra"]))

    def es_ai_cameo_group_size(slots):
        """Truncate and renormalize weights instead of clipping a larger draw."""
        weights = (40, 30, 18, 9, 3)[:_es_ai_cameo_builtins.max(0, int(slots))]
        if not weights:
            return 0
        draw = _es_random.random() * sum(weights)
        for i, weight in enumerate(weights):
            draw -= weight
            if draw < 0:
                return i + 1
        return len(weights)

    def es_ai_write_cameo_setting(key, value):
        """Записать один ключ камео в config.json (остальные ключи не трогаем)."""
        import os
        import json
        path = os.path.join(ES_AI_SERVER_DIR, "config.json")
        try:
            import io
            f = io.open(path, "r", encoding="utf-8")
            try:
                data = json.load(f)
            finally:
                f.close()
            if not isinstance(data, _es_ai_cameo_builtins.dict):
                data = {}
            data[key] = value
            f = io.open(path, "w", encoding="utf-8")
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            finally:
                f.close()
        except Exception:
            pass

    def es_ai_read_cameo_flag():
        """Флаг из config.json, который пишет окно настроек. None — файла нет."""
        import os
        import json
        path = os.path.join(ES_AI_SERVER_DIR, "config.json")
        try:
            import io
            f = io.open(path, "r", encoding="utf-8")
            try:
                data = json.load(f)
            finally:
                f.close()
            if isinstance(data, _es_ai_cameo_builtins.dict) and "cameo_enabled" in data:
                return bool(data.get("cameo_enabled"))
        except Exception:
            pass
        return None

    def es_ai_write_cameo_flag(enabled):
        es_ai_write_cameo_setting("cameo_enabled", bool(enabled))

    def es_ai_cameo_on():
        flag = es_ai_read_cameo_flag()
        if flag is None:
            flag = bool(getattr(persistent, "es_ai_cameo", True))
        persistent.es_ai_cameo = bool(flag)
        if not flag:
            es_ai_cameo_clear()
        return bool(flag)

    def es_ai_toggle_cameo():
        cur = es_ai_cameo_on()
        persistent.es_ai_cameo = not cur
        es_ai_write_cameo_flag(not cur)
        if cur:
            es_ai_cameo_clear()

    def es_ai_toggle_cameo_stay():
        """Кнопка в игре: тумблер «остаются в сцене»."""
        st = es_ai_read_cameo_settings()
        es_ai_write_cameo_setting("cameo_stay", not bool(st["cameo_stay"]))
        if st["cameo_stay"]:
            es_ai_cameo_clear()
        try:
            renpy.restart_interaction()
        except Exception:
            pass

    def es_ai_cycle_cameo_freq():
        """Кнопка в игре: частота появлений по кругу 0-5-10-...-100%."""
        st = es_ai_read_cameo_settings()
        steps = [0, 5, 10, 15, 20, 25, 35, 50, 70, 100]
        cur = int(st["cameo_freq"])
        nxt = steps[0]
        for s in steps:
            if s > cur:
                nxt = s
                break
        es_ai_write_cameo_setting("cameo_freq", nxt)
        try:
            renpy.restart_interaction()
        except Exception:
            pass

    def es_ai_sync_cameo_from_file():
        es_ai_cameo_on()
        if not es_ai_read_cameo_settings()["cameo_stay"]:
            es_ai_cameo_clear(clear_pending=False)

    # ------------------------------------------------------- вероятности --

    def es_ai_cameo_chance(cameo_id, romantic, st):
        """Шанс появления конкретного персонажа.

        В обычной ситуации — базовая частота из настроек (поэтому локации не
        пустые, когда гуляешь с одним персонажем). В романтический момент шансы
        выше и масштабируются той же частотой (при 25% — как раньше)."""
        loc_id = ES_AI_LOC_CUR[0]
        base = st["cameo_freq"] / 100.0
        if base <= 0:
            return 0.0
        if romantic:
            scale = _es_ai_cameo_builtins.max(0.2, _es_ai_cameo_builtins.min(2.0, st["cameo_freq"] / 25.0))
            if cameo_id in ES_AI_LOC_OWNERS.get(loc_id, []):
                return _es_ai_cameo_builtins.max(base, ES_AI_CAMEO_P_OWNER * scale)
            if ES_AI_LOCATION_INDEX.get(loc_id, {}).get("romantic"):
                return _es_ai_cameo_builtins.max(base, ES_AI_CAMEO_P_ROMANTIC * scale)
            return _es_ai_cameo_builtins.max(base, ES_AI_CAMEO_P_ROMANTIC_OTHER * scale)
        return base

    def es_ai_maybe_cameo(active_id, romantic, chance=None):
        """Решить, кто зайдёт. Возвращает СПИСОК id (1..cameo_max_extra —
        «пришли вместе»), или [] если никто. chance — явная вероятность
        (для входа в локацию, где своего «обмена» ещё не было)."""
        st = es_ai_read_cameo_settings()
        if not es_ai_cameo_on() or st["cameo_freq"] <= 0:
            return []
        if ES_AI_CAMEO_CD[0] > 0:
            ES_AI_CAMEO_CD[0] -= 1
            return []
        loc_id = ES_AI_LOC_CUR[0]
        shown = set(g["id"] for g in ES_AI_SHOWN)
        slots = es_ai_cameo_capacity(loc_id, st) - len(shown - {active_id})
        if slots <= 0:
            return []
        cands = [c for c in ES_AI_CAMEO_BY_LOC.get(loc_id, [])
                 if c != active_id and c not in shown
                  and c not in [g["id"] for g in ES_AI_CAMEO_NEARBY.get(loc_id, [])]
                  and c not in globals().get("ES_AI_SCENE_ABSENT", {}).get(loc_id, [])]
        bias = globals().get("es_ai_activity_bias")
        if st.get("npc_activity_enabled", True) is True and callable(bias):
            cands = [c for c in cands if _es_random.random() < bias(c)]
        if not cands:
            return []
        owners = [c for c in cands if c in ES_AI_LOC_OWNERS.get(loc_id, [])]
        pool = owners if (romantic and owners) else cands
        cameo = _es_random.choice(pool)
        p = chance if chance is not None else es_ai_cameo_chance(cameo, romantic, st)
        if _es_random.random() >= p:
            return []
        result = [cameo]
        rest = [c for c in cands if c != cameo]
        # Иногда рядом оказывается «неразлучная» пара (Алиса+Ульяна, Лена+Алиса
        # и т.п.): с небольшим шансом заходит второй, потом — третий (но не
        # больше cameo_max_extra). Количество — случайное.
        group_size = es_ai_cameo_group_size(_es_ai_cameo_builtins.min(slots, len(cands)))
        while len(result) < group_size and rest:
            mates = [other for other in rest
                     if any(cameo in pair and other in pair for pair in ES_AI_CAMEO_PAIRS)]
            mate = _es_random.choice(mates or rest)
            result.append(mate)
            rest = [c for c in rest if c != mate]
        ES_AI_CAMEO_CD[0] = ES_AI_CAMEO_COOLDOWN
        return result

    # ------------------------------------------------------- контекст LLM --

    def es_ai_recent_push(who, what):
        """Добавить реплику в хвост сцены (уходит в /cameo как context)."""
        try:
            w = unicode(what or u"").strip()
        except Exception:
            w = u""
        if not w:
            return
        ES_AI_RECENT_LINES.append({"who": who or u"Игрок", "what": w})
        if len(ES_AI_RECENT_LINES) > 12:
            del ES_AI_RECENT_LINES[:len(ES_AI_RECENT_LINES) - 12]

    def es_ai_public_record(speaker_id, text):
        """Capture immutable actual speech with engaged, not nearby, witnesses."""
        if not ES_AI_FREE_SCENE[0]:
            return
        raw = unicode(text or u"").strip()
        witnesses = sorted(set(g["id"] for g in ES_AI_SHOWN))
        if not raw or len(witnesses) < 2 or (speaker_id != "player" and speaker_id not in witnesses):
            return
        if ES_AI_PUBLIC_SESSION[0] is None:
            import uuid
            ES_AI_PUBLIC_SESSION[0] = str(uuid.uuid4())
        ES_AI_PUBLIC_SESSION[1] += 1
        ES_AI_PUBLIC_EVENTS.append(dict(id="%s_%s" % tuple(ES_AI_PUBLIC_SESSION),
            location_id=ES_AI_LOC_CUR[0], clock=dict(es_ai_clock_snapshot()),
            witnesses=witnesses, speaker_id=speaker_id, text=raw[:600]))
        ES_AI_PUBLIC_EVENTS[:] = ES_AI_PUBLIC_EVENTS[-40:]

    def es_ai_public_snapshot():
        return [dict(e, witnesses=_es_ai_cameo_builtins.list(e["witnesses"]), clock=dict(e["clock"]))
                for e in ES_AI_PUBLIC_EVENTS]

    def es_ai_recent_snapshot(n=6):
        return [dict(x) for x in ES_AI_RECENT_LINES[-n:]]

    def es_ai_actual_outfits():
        outfits = {}
        for g in ES_AI_SHOWN:
            tag = g.get("tag")
            if not tag and callable(globals().get("es_ai_resolve_sprite")):
                dp = g.get("dress") if "dress" in g else es_ai_loc_dress_pref()
                tag = es_ai_resolve_sprite(g["id"], g.get("emo", "normal"), dress_pref=dp)
            words = (tag or "").split()
            outfits[g["id"]] = next((word for word in words if word in
                ("pioneer", "pioneer2", "swim", "sport", "dress", "panama")),
                "ordinary" if words else "unknown")
        return outfits

    def es_ai_scene_snapshot(active_id, st=None):
        """Current scene for model-selected actions, independent of random frequency."""
        if st is None:
            st = es_ai_read_cameo_settings()
        enabled = es_ai_cameo_on()
        present = set(g["id"] for g in ES_AI_SHOWN)
        absent = set(globals().get("ES_AI_SCENE_ABSENT", {}).get(ES_AI_LOC_CUR[0], [])) - present
        available = [c for c in ES_AI_CAMEO_BY_LOC.get(ES_AI_LOC_CUR[0], [])
                     if c != active_id and c not in present]
        invitable = [c[0] for c in ES_AI_CHARS if c[0] != active_id]
        available = [cid for cid in available if cid not in absent]
        invitable = [cid for cid in invitable if cid not in absent]
        # Vary model-facing order without changing eligibility or shared pools.
        _es_random.shuffle(available)
        _es_random.shuffle(invitable)
        capacity = _es_ai_cameo_builtins.max(0,
            es_ai_cameo_capacity(st=st) - len(present - {active_id}))
        traveling = sorted(present - {active_id})
        destination_capacity = {loc_id: es_ai_cameo_capacity(loc_id, st)
                                for loc_id in ES_AI_LOCATION_INDEX}
        snapshot = {"present": sorted(present), "available": available,
                "outfits": es_ai_actual_outfits(),
                "travel_party": sorted(set([active_id] + [g["id"] for g in ES_AI_SHOWN if g.get("travel_party")])) if any(g.get("travel_party") for g in ES_AI_SHOWN) else [],
                "traveling": traveling,
                "replacement_available": bool(traveling),
                "nearby": [g["id"] for g in ES_AI_CAMEO_NEARBY.get(ES_AI_LOC_CUR[0], [])],
                "destination_nearby": {loc_id: [g["id"] for g in records]
                                       for loc_id, records in ES_AI_CAMEO_NEARBY.items()},
                "invitable": invitable,
                "enabled": bool(enabled), "capacity": capacity,
                "location_id": ES_AI_LOC_CUR[0],
                "max_extra": _es_ai_cameo_builtins.max(1, _es_ai_cameo_builtins.min(6, st["cameo_max_extra"])),
                "group_size": es_ai_cameo_group_size(capacity),
                "destination_capacity": destination_capacity,
                "destination_group_sizes": {loc_id: es_ai_cameo_group_size(cap)
                                            for loc_id, cap in destination_capacity.items()},
                 "destinations": {loc_id: [c for c in _es_random.sample(ids, len(ids))
                                           if c != active_id and c not in present]
                                 for loc_id, ids in ES_AI_CAMEO_BY_LOC.items()},
                "context": es_ai_recent_snapshot(6)}
        activity = globals().get("es_ai_activity_snapshot")
        snapshot["absent"] = sorted(absent)
        for loc_id, ids in snapshot["destinations"].items():
            snapshot["destinations"][loc_id] = [cid for cid in ids if cid not in globals().get("ES_AI_SCENE_ABSENT", {}).get(loc_id, [])]
        snapshot["npc_activity_enabled"] = st.get("npc_activity_enabled", True) is True
        if enabled and globals().get("ES_AI_FREE_SCENE", [False])[0] and callable(activity):
            if snapshot["npc_activity_enabled"]:
                snapshot["activity"] = activity()
                snapshot["pending_calls"] = {cid: dict(call) for cid, call in ES_AI_ACTIVITY_PENDING.items()}
            else:
                ES_AI_ACTIVITY_PENDING.clear()
                snapshot["activity"] = {}
                snapshot["pending_calls"] = {}
        return snapshot

    def es_ai_cameo_split(raw):
        """'(эмоция) текст' -> (ключ_эмоции|None, текст). Для запасных реплик."""
        try:
            s = unicode(raw or u"").strip()
        except Exception:
            s = u""
        emo = None
        if s.startswith(u"("):
            end = s.find(u")")
            if end != -1:
                word = s[1:end].strip().lower()
                emo = ES_AI_EMOTION_RU.get(word, word)
                s = s[end + 1:].strip()
        return emo, s

    def es_ai_cameo_fallback(cameo_id, romantic):
        pool = (ES_AI_CAMEO_CAUGHT if romantic else ES_AI_CAMEO_PASSBY).get(cameo_id)
        if not pool:
            pool = ES_AI_CAMEO_CAUGHT.get(cameo_id) or [u"(удивление) Ой, вы тут?"]
        return _es_random.choice(pool)

    def es_ai_cameo_line(cameo_id, active_id, romantic, mode="enter",
                         on_topic=True, others=None, story_token=None):
        """Реплика камео от сервера (LLM). None — если сервер недоступен.

        mode: "enter" — зашёл и застал; "here» — уже на месте при входе игрока;
        "stay" — остался в сцене и вклинивается. on_topic — реплика по контексту
        последних реплик (иначе — нейтральная, по ситуации)."""
        es_ai_clock_sync(redraw=es_ai_chat_active[0])
        g = next((g for g in ES_AI_SHOWN if g["id"] == cameo_id), {})
        payload = {"character": cameo_id, "active": es_ai_cameo_name(active_id),
                   "public_events": es_ai_public_snapshot(),
                   "location_id": ES_AI_LOC_CUR[0],
                    "dress": ("pioneer" if g.get("dress") in ("swim", "dress") and g.get("tag")
                              and g["dress"] not in g["tag"].split() else g.get("dress") or "pioneer"),
                    "dress_reason": g.get("dress_reason", "location"),
                    "party": globals().get("ES_AI_PARTY", [False])[0],
                   "player_text": ES_AI_CAMEO_PLAYER_TEXT[0],
                   "clock": es_ai_clock_snapshot(),
                   "active_id": active_id,
                   "location": es_ai_location().get("desc", u""),
                   "romantic": bool(romantic), "mode": mode,
                   "on_topic": bool(on_topic),
                   "context": es_ai_recent_snapshot(6),
                   "others": list(others or [])}
        payload["story_acks"] = es_ai_story_ack_snapshot()
        payload["scene"] = es_ai_scene_snapshot(active_id)
        if story_token:
            payload["story_token"] = story_token

        def fn():
            r = es_ai_http("/cameo", payload)
            if not r.get("ok"):
                raise Exception(r.get("error", "cameo error"))
            return r

        job = es_ai_run_async("cameo", fn)
        waited = 0
        while not job.done and waited < 240:
            renpy.pause(0.05)
            waited += 1
        if job.error is not None or not job.result:
            return None
        return job.result

    # ------------------------------------------- остающиеся в сцене камео --

    def es_ai_cameo_register(cameo_id, max_lines):
        """Register dwell time; legacy speech budgets no longer force departures."""
        for a in ES_AI_CAMEO_ACTIVE:
            if a["id"] == cameo_id:
                return
        ES_AI_CAMEO_ACTIVE.append({"id": cameo_id, "turns": 0, "skip_tick": True})

    def es_ai_cameo_unregister(cameo_id):
        ES_AI_CAMEO_ACTIVE[:] = [a for a in ES_AI_CAMEO_ACTIVE if a["id"] != cameo_id]

    def es_ai_cameo_take_nearby(cameo_id):
        """Remove all saved locations for an NPC; return their local record only."""
        saved = next((g for g in ES_AI_CAMEO_NEARBY.get(ES_AI_LOC_CUR[0], [])
                      if g["id"] == cameo_id), None)
        for loc_id in _es_ai_cameo_builtins.list(ES_AI_CAMEO_NEARBY):
            records = [g for g in ES_AI_CAMEO_NEARBY[loc_id] if g["id"] != cameo_id]
            if records:
                ES_AI_CAMEO_NEARBY[loc_id] = records
            else:
                del ES_AI_CAMEO_NEARBY[loc_id]
        return saved

    def es_ai_cameo_park(cameo_id, activity=None, announce=True):
        """Stop participating without leaving this location."""
        shown = next((g for g in ES_AI_SHOWN if g["id"] == cameo_id and g.get("cameo")), None)
        if shown is None:
            return
        if shown.get("travel_party"):
            for g in ES_AI_SHOWN:
                g.pop("travel_party", None)
        record = dict(shown)
        record.pop("travel_party", None)
        record.pop("focused", None)
        record["dwell"] = next((dict(a) for a in ES_AI_CAMEO_ACTIVE if a["id"] == cameo_id), {})
        if activity:
            record["activity"] = activity
        es_ai_cameo_take_nearby(cameo_id)
        ES_AI_CAMEO_NEARBY.setdefault(ES_AI_LOC_CUR[0], []).append(record)
        es_ai_cameo_unregister(cameo_id)
        ES_AI_SHOWN[:] = [g for g in ES_AI_SHOWN if g["id"] != cameo_id]
        renpy.hide(cameo_id)
        es_ai_refresh_girls()
        if announce:
            text = u"%s: остаётся неподалёку, вне разговора." % es_ai_cameo_name(cameo_id)
            if activity:
                text += u" " + unicode(activity)
            es_ai_recent_push("Narrator", text)
            es_ai_internal_speaking[0] = True
            try:
                renpy.say(None, es_ai_sanitize_text(text))
            finally:
                es_ai_internal_speaking[0] = False

    def es_ai_cameo_clear(clear_pending=True):
        """Clear cameos on character change, reset or exit, not movement."""
        for g in ES_AI_SHOWN:
            g.pop("travel_party", None)
            if g.get("cameo"):
                try:
                    renpy.hide(g["id"])
                except Exception:
                    pass
        ES_AI_CAMEO_ACTIVE[:] = []
        ES_AI_CAMEO_NEARBY.clear()
        if clear_pending:
            globals().get("ES_AI_ACTIVITY_PENDING", {}).clear()
        ES_AI_SHOWN[:] = [g for g in ES_AI_SHOWN if not g.get("cameo")]
        try:
            es_ai_refresh_girls()
        except Exception:
            pass

    def es_ai_request_trace(active, text):
        import hashlib
        raw = unicode(text or u"")
        return {"active": active, "length": len(raw),
                "digest": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
                "party": es_ai_party_context(raw),
                "clothing": [(cid, request) for cid, request in
                    [(cid, es_ai_cameo_clothing_request(cid, raw, unnamed=(cid == active)))
                     for cid, _, _ in ES_AI_CHARS] if request][:16]}

    def es_ai_party_context(text):
        """Only current public intent or an ongoing event; never a location name."""
        import re
        event = u"(?:дискотек\\w*|концерт\\w*|концер|бал|вечеринк\\w*|праздник\\w*|disco|concert|party|celebration)"
        for clause in re.split(r"[.!?;\n]", unicode(text or u"").lower()):
            if not re.search(u"\\b" + event + u"\\b", clause, re.UNICODE):
                continue
            if re.search(u"\\b(?:не|нет|not|don't|отмен\\w*|законч\\w*)\\b", clause, re.UNICODE):
                return False
            if re.search(u"\\b(?:где|когда|зачем|where|when|why)\\b", clause, re.UNICODE):
                continue
            if re.search(u"\\b(?:пошли|пойд[её]м|ид[её]м|давай|готовимся|готовим|переоденься|танцуем|начался|началась|ид[её]т|go|going|prepare|dancing)\\b", clause, re.UNICODE):
                return True
        return None

    def es_ai_cameo_clothing_request(cid, text=None, unnamed=False):
        import re
        stems = {"sl": u"слав", "mz": u"жен", "un": u"лен", "mi": u"мику",
                 "dv": u"алис", "us": u"ульян", "mt": u"ольг", "cs": u"виол"}
        request = None
        for clause in re.split(r"[.!?;\n]", unicode((ES_AI_CAMEO_PLAYER_TEXT[0] if text is None else text) or u"").lower()):
            named = [key for key, stem in stems.items() if re.search(u"(?:^|\\W)(?:" + stem + u"\\w*|" + key + u")(?:$|\\W)", clause, re.UNICODE)]
            if cid not in named and not (unnamed and not named):
                continue
            # Negated alternatives and commands never authorize a garment.
            for command in re.split(u",|\\s+(?:а|и|but|and)\\s+", clause):
                targets = [key for key, stem in stems.items() if re.search(u"\\b(?:" + stem + u"\\w*|" + key + u")\\b", command, re.UNICODE)]
                if targets and cid not in targets:
                    continue
                if re.search(u"\\b(?:не|not|don't|do not|где|когда|зачем|where|when|why)\\b", command, re.UNICODE):
                    continue
                match = re.search(u"\\b(?:надень|надевай|оденься|приоденьс[яе]|переоденься|переоденешься|put on|change into)\\s*(?:(?:\\w+)\\s+){0,3}?(купальник\\w*|бикини|swimsuit|bikini|форм\\w*|uniform|плать\\w*|dress)\\b", command, re.UNICODE)
                if not match:
                    match = re.search(u"\\b(купальник\\w*|бикини|swimsuit|bikini|форм\\w*|uniform|плать\\w*|dress|спортивн\\w*|sport)\\s+(?:(?:\\w+)\\s+){0,2}?(?:переоденься|переодевайся|оденься|надень|надевай|change into|put on)\\b", command, re.UNICODE)
                if not match:
                    match = re.search(u"\\b(?:надень|надевай|переоденься)\\s+(?:в\\s+)?(спортивн\\w*|sport)\\b", command, re.UNICODE)
                if match:
                    request = "sport" if re.match(u"спортивн|sport", match.group(1)) else ("dress" if re.match(u"плать|dress", match.group(1)) else ("swim" if re.match(u"купальник|бикини|swimsuit|bikini", match.group(1)) else "cover"))
                elif re.search(u"\\bпереоденься\\b", command, re.UNICODE) and es_ai_party_context(command) is True:
                    request = "dress"
                elif re.search(u"\\b(?:оденься|прикройся|cover up)\\b|\\b(?:сними|take off)\\s*(?:купальник\\w*|бикини|swimsuit|bikini)\\b", command, re.UNICODE):
                    request = "cover"
        return request

    def es_ai_clothing_cover_choice(reply, cid):
        import re
        stems = {"sl": u"слав", "mz": u"жен", "un": u"лен", "mi": u"мику", "dv": u"алис", "us": u"ульян", "mt": u"ольг", "cs": u"виол", "uv": u"юл"}
        for clause in re.split(r"[.!?;\n]", unicode(reply or u"").lower()):
            if any(key != cid and re.search(u"\\b(?:" + stem + u"\\w*|" + key + u")\\b", clause, re.UNICODE) for key, stem in stems.items()):
                continue
            if re.search(u"\\b(?:останусь\\s+(?:в\\s+)?(?:форме|одежде)|(?:пойд[её]м|пойду|погуляем|побудем|у воды)\\s+(?:\\w+\\s+){0,3}без\\s*переодеваний)\\b", clause, re.UNICODE):
                return True
        return False

    def es_ai_clothing_refused(reply):
        import re
        return bool(re.search(u"\\b(?:не\\s+(?:хочу|буду|стану|собираюсь)\\s+(?:\\w+\\s+){0,2}(?:переодеваться|переоденусь|надевать|надену)|не\\s+(?:переоденусь|надену)|останусь\\s+(?:в\\s+)?(?:форме|одежде)|не\\s+надо\\s+переодеваться)\\b", unicode(reply or u"").lower(), re.UNICODE))

    def es_ai_cameo_adult_home_ids():
        """Read structured ages only; malformed metadata fails closed."""
        import os
        import io
        import json
        paths = (os.path.join(ES_AI_SERVER_DIR, "es_characters.json"),)
        for path in paths:
            try:
                with io.open(path, "r", encoding="utf-8") as stream:
                    raw = stream.read(1048577)
                if len(raw) > 1048576:
                    return set()
                data = json.loads(raw.lstrip(u"\ufeff"))
                if not isinstance(data, _es_ai_cameo_builtins.dict):
                    return set()
                characters = data.get("characters")
                if not isinstance(characters, _es_ai_cameo_builtins.list):
                    return set()
                return set(ch.get("id") for ch in characters
                           if isinstance(ch, _es_ai_cameo_builtins.dict)
                           and ch.get("id") in ES_AI_CAMEO_HOMES
                           and ch.get("id") not in ("us", "uv")
                           and type(ch.get("age")) in (_es_ai_cameo_builtins.int,
                               _es_ai_cameo_builtins.float, _es_ai_cameo_builtins.long
                               if hasattr(_es_ai_cameo_builtins, "long") else _es_ai_cameo_builtins.int)
                           and ch["age"] >= 18)
            except (IOError, OSError, ValueError):
                continue
        return set()

    ES_AI_CAMEO_HOMES = {"sl": "sl_room", "mz": "sl_room", "un": "un_room", "mi": "un_room",
                         "dv": "dv_room", "us": "dv_room", "mt": "mt_room", "cs": "aidpost_inside"}

    def es_ai_cameo_home_reason(cid):
        if ES_AI_CAMEO_HOMES.get(cid) != ES_AI_LOC_CUR[0]:
            return None
        night = ES_AI_TIME[0] == "night"
        if ES_AI_CLOCK.get("enabled") and ES_AI_CLOCK.get("minutes") is not None:
            hour = (ES_AI_CLOCK["minutes"] % 1440) // 60
            night = hour >= 22 or hour < 6
        if night:
            return "night_home"
        if (ES_AI_TIME[0] in ("morning", "day", "sunset") or
                (ES_AI_CLOCK.get("enabled") and ES_AI_CLOCK.get("minutes") is not None)) and cid not in ("us", "uv") and cid in es_ai_cameo_adult_home_ids():
            return "home_changing"
        return None

    def es_ai_cameo_dress(dress=None, current=None, record=None):
        # Per-NPC signals win; never inherit the active heroine's romantic dress.
        base = es_ai_default_dress()
        record = record if record is not None else {}
        if record.get("cover_choice") and dress not in ("swim", "dress", "sport"):
            record.update(dress_reason="cover_choice", dress_location=ES_AI_LOC_CUR[0])
            return "pioneer"
        if record.get("dress_location", ES_AI_LOC_CUR[0]) != ES_AI_LOC_CUR[0]:
            current = None
            record["dress_reason"] = "location"
        request = es_ai_cameo_clothing_request(record.get("id", "")) if record.get("id") else None
        if request and not es_ai_clothing_refused(record.get("activity", "")):
            dress = request
        elif es_ai_clothing_refused(record.get("activity", "")):
            return current if current is not None else base
        elif es_ai_location().get("id") == "beach" and es_ai_clothing_night() and es_ai_no_swimming(ES_AI_CAMEO_PLAYER_TEXT[0]):
            dress = "cover"
        party = globals().get("ES_AI_PARTY", [False])[0]
        if isinstance(dress, basestring) and dress.strip().lower() not in ("dress", "party", u"платье", "cover", "swim", "sport"):
            return current if current is not None else base
        if (dress in ("dress", "party", u"платье") or party) and record.get("id"):
            if (request == "dress" or party) and request in (None, "dress") and dress not in ("cover", "swim", "sport") and (request == "dress" or not (record.get("dress_reason") == "player" and current != "dress")):
                if es_ai_has_party_dress(record["id"]):
                    record.update(dress_reason="player" if request else "party", dress_location=ES_AI_LOC_CUR[0])
                    return "dress"
            if dress in ("dress", "party", u"платье"):
                dress = None
        home_reason = record.get("dress_reason")
        home_allowed = (home_reason in ("night_home", "home_changing") and
                        home_reason == es_ai_cameo_home_reason(record.get("id")))
        romantic_allowed = (home_reason == "romantic_choice" and record.get("id") not in ("us", "uv")
                            and record.get("id") in es_ai_cameo_adult_home_ids())
        if isinstance(dress, basestring):
            signal = dress.strip().lower()
            if signal in ("cover", "swim", "sport"):
                if signal != "swim" or base == "swim" or request == "swim" or home_allowed or (romantic_allowed and current == "swim"):
                    if signal != "cover":
                        record.pop("cover_choice", None)
                    record["dress_reason"] = "player" if request or (party and signal == "cover") else (home_reason if signal == "swim" and base != "swim" else "location")
                    record["dress_location"] = ES_AI_LOC_CUR[0]
                    return "pioneer" if signal == "cover" else signal
        if current == "dress" and record.get("dress_reason") != "player" and not party:
            current = None
        if current == "swim" and base != "swim" and not (record.get("dress_reason") == "player" or home_allowed or romantic_allowed):
            current = None
            record["dress_reason"] = "location"
        if current is not None:
            return current
        return base if base in ("swim", "sport") else None

    def es_ai_cameo_enter(cameo_id, emotion, stay=False, stay_lines=0, dress=None, romantic=False):
        emo = emotion or "surprise"
        saved = es_ai_cameo_take_nearby(cameo_id)
        for g in ES_AI_SHOWN:
            if g["id"] == cameo_id:
                g["emo"] = emo
                g["dress"] = es_ai_cameo_dress(dress, g.get("dress"), g)
                g["cameo"] = True
                es_ai_refresh_girls()
                if stay:
                    es_ai_cameo_register(cameo_id, stay_lines)
                return
        record = dict(saved) if saved else {}
        dwell = record.pop("dwell", {})
        record["id"] = cameo_id
        if not saved:
            record.update(dress_location=ES_AI_LOC_CUR[0], dress_reason="location")
            reason = es_ai_cameo_home_reason(cameo_id)
            if reason and not romantic and any(
                    renpy.has_image(cameo_id + " " + emo + " swim" + distance)
                    for emo in ("normal", "smile", "shy") for distance in ("", " close", " far")):
                if _es_random.random() < (0.50 if reason == "night_home" else 0.10):
                    record.update(dress="swim", dress_reason=reason)
        record.update({"id": cameo_id, "emo": emo,
                       "dress": es_ai_cameo_dress(dress, record.get("dress"), record), "cameo": True})
        ES_AI_SHOWN.append(record)
        es_ai_refresh_girls()
        if stay:
            es_ai_cameo_register(cameo_id, stay_lines)
            if dwell:
                for a in ES_AI_CAMEO_ACTIVE:
                    if a["id"] == cameo_id:
                        a.update(dwell)
                        a["skip_tick"] = True

    def es_ai_cameo_leave(cameo_id):
        if any(g["id"] == cameo_id and g.get("travel_party") for g in ES_AI_SHOWN):
            for g in ES_AI_SHOWN:
                g.pop("travel_party", None)
        es_ai_cameo_take_nearby(cameo_id)
        es_ai_cameo_unregister(cameo_id)
        ES_AI_SHOWN[:] = [g for g in ES_AI_SHOWN if g.get("id") != cameo_id]
        try:
            renpy.hide(cameo_id)
        except Exception:
            pass
        es_ai_refresh_girls()

    def es_ai_cameo_speak(cameo_id, text, emotion=None, dress=None, story_ack=None, choices=None):
        """Реплика уже вошедшего камео-персонажа (без входа/ухода).
        С эмоций — меняем «лицо» спрайта, чтобы не выглядело заскриптованно."""
        raw = (text or u"").strip()
        if not raw:
            return
        for g in ES_AI_SHOWN:
            if g["id"] == cameo_id:
                g["activity"] = raw
                if es_ai_clothing_cover_choice(raw, cameo_id):
                    g.update(cover_choice=True, dress="pioneer", dress_reason="cover_choice", dress_location=ES_AI_LOC_CUR[0])
                    dress = "cover"
        # Emphasize the speaker within their row, without moving anyone's slot.
        for g in ES_AI_SHOWN:
            g["focused"] = g["id"] == cameo_id
            if g["id"] == cameo_id and (emotion or dress is not None):
                if emotion:
                    g["emo"] = emotion
                if not es_ai_clothing_refused(raw):
                    g["dress"] = es_ai_cameo_dress(dress, g.get("dress"), g)
        es_ai_refresh_girls()
        if persistent.es_ai_tts:
            try:
                es_ai_speak_async(raw, cameo_id)
            except Exception:
                pass
        safe = es_ai_sanitize_text(raw)
        es_ai_internal_speaking[0] = True
        try:
            if choices is None:
                es_ai_delivery_say(es_ai_speakers[cameo_id], safe, cameo_id, raw, story_ack)
            else:
                es_ai_delivery_say(es_ai_speakers[cameo_id], safe, cameo_id, raw, story_ack, choices)
        finally:
            es_ai_internal_speaking[0] = False

    def es_ai_cameo_tick(active_id, st=None):
        """At most one interjection; passive NPCs never randomly disappear."""
        if st is None:
            st = es_ai_read_cameo_settings()
        if not es_ai_cameo_on() or not st["cameo_stay"]:
            es_ai_cameo_clear(clear_pending=not st["cameo_enabled"])
            return
        p_speak = st["cameo_interject"] / 100.0
        p_ctx = st["cameo_ctx"] / 100.0
        eligible = []
        for a in list(ES_AI_CAMEO_ACTIVE):
            cid = a["id"]
            if a.pop("skip_tick", False):
                continue
            if not any(g["id"] == cid for g in ES_AI_SHOWN):
                ES_AI_CAMEO_ACTIVE.remove(a)
                continue
            turns = a.get("turns", 0)
            a["turns"] = turns + 1
            eligible.append(a)
        if p_speak <= 0 or not eligible or _es_random.random() >= p_speak:
            return
        # One stochastic interjection per exchange, independent of crowd size.
        for a in [_es_random.choice(eligible)]:
            cid = a["id"]
            on_topic = _es_random.random() < p_ctx
            others = [es_ai_cameo_name(g["id"]) for g in ES_AI_SHOWN
                      if g.get("cameo") and g["id"] != cid]
            line = es_ai_cameo_line(cid, active_id, False, mode="stay",
                                    on_topic=on_topic, others=others)
            if line and line.get("reply"):
                emo, text = line.get("emotion"), line.get("reply")
            else:
                emo, text = es_ai_cameo_split(_es_random.choice(ES_AI_CAMEO_STAY_FALLBACK))
            es_ai_log("cameo stay: %s -> %r (on_topic=%s)" % (cid, text, on_topic))
            es_ai_recent_push(es_ai_cameo_name(cid), text)
            es_ai_cameo_speak(cid, text, emo, line.get("dress") if line else None)
            if line and line.get("aside") is True:
                es_ai_cameo_park(cid, text)

    def es_ai_cameo_deliver_group(cameos, active_id, romantic, st, explicit=False, arrival=False, story_token=None):
        """Register the whole group; only one or two participants need a line."""
        existing = set(g["id"] for g in ES_AI_SHOWN)
        if explicit:
            for a in ES_AI_CAMEO_ACTIVE:
                if a["id"] in cameos:
                    a["skip_tick"] = True
        present = existing | set(cameos)
        stay = bool(st["cameo_stay"])
        speakers = set(_es_random.sample(cameos,
            _es_ai_cameo_builtins.min(len(cameos), _es_random.randint(1, 2))))
        for cid in cameos:
            if cid in existing:
                continue
            current_request = ES_AI_CAMEO_PLAYER_TEXT[0]
            ES_AI_CAMEO_PLAYER_TEXT[0] = u""
            try:
                es_ai_cameo_enter(cid, "normal", stay=stay,
                    romantic=romantic,
                    stay_lines=_es_random.randint(1, st["cameo_stay_lines"]) if stay else 0)
            finally:
                ES_AI_CAMEO_PLAYER_TEXT[0] = current_request
            if arrival and stay:
                for a in ES_AI_CAMEO_ACTIVE:
                    if a["id"] == cid:
                        a["skip_tick"] = True
        try:
            renpy.with_statement(dissolve)
        except Exception:
            pass
        for cid in cameos:
            if cid not in speakers:
                continue
            on_topic = False if arrival else (explicit or _es_random.random() < st["cameo_ctx"] / 100.0)
            mode = "here" if arrival else (("stay" if cid in existing else "here") if explicit else "enter")
            line = es_ai_cameo_line(cid, active_id, romantic, mode=mode, on_topic=on_topic,
                story_token=story_token if explicit and not arrival else None,
                others=[es_ai_cameo_name(c) for c in sorted(present) if c not in (cid, active_id)])
            if line and line.get("reply"):
                emo, text = line.get("emotion"), line["reply"]
            else:
                raw = _es_random.choice(ES_AI_CAMEO_STAY_FALLBACK) if explicit else es_ai_cameo_fallback(cid, romantic)
                emo, text = es_ai_cameo_split(raw)
            es_ai_recent_push(es_ai_cameo_name(cid), text)
            es_ai_cameo_speak(cid, text, emo, line.get("dress") if line else None,
                              line.get("story_ack") if line and line.get("reply", "").strip() else None,
                              line.get("choices") if line and line.get("reply", "").strip() else None)
            if line and line.get("aside") is True:
                es_ai_cameo_park(cid, text)
        if not stay:
            for cid in cameos:
                if cid not in existing and any(g["id"] == cid for g in ES_AI_SHOWN):
                    es_ai_cameo_leave(cid)
            try:
                renpy.with_statement(dissolve)
            except Exception:
                pass

    def es_ai_cameo_on_arrive():
        """Хук при входе в новую локацию: кто-то может уже быть на месте
        (чтобы локации не казались пустыми, когда гуляешь с одним персонажем)."""
        ES_AI_CAMEO_PLAYER_TEXT[0] = u""
        try:
            st = es_ai_read_cameo_settings()
            if not es_ai_cameo_on():
                return
            if not st["cameo_stay"]:
                es_ai_cameo_clear(clear_pending=False)
            if not es_ai_chat_active[0]:
                return
            if ES_AI_CAMEO_CD[0] > 0:
                return
            active = ES_AI_LOC_LAST_CHAR[0]
            if not active:
                return
            if not any(g["id"] == active for g in ES_AI_SHOWN):
                return
            p = (st["cameo_freq"] / 100.0) * 0.5   # при входе — половинный шанс
            if p <= 0:
                return
            cameos = es_ai_maybe_cameo(active, False, chance=p)
            if not cameos:
                return
            es_ai_cameo_deliver_group(cameos, active, False, st, arrival=True)
        except Exception as e:
            import traceback
            es_ai_log("cameo arrive error: %s\n%s" % (type(e).__name__, traceback.format_exc()))

    def es_ai_try_cameo(active_id, player_text, res):
        """Главная точка: вызвать после реплики героини. Сама решает, кого звать.

        1) Пополняем хвост реплик (контекст для LLM).
        2) Решаем, не зайти ли кому-то новому (случайный персонаж, иногда пара).
        3) Зашедшие говорят первую реплику — в тему по контексту или без него.
        4) Если включено «остаются в сцене» — остаются и дальше рандомно
           вклиниваются; иначе — сказали по одной фразе и ушли (как раньше).
        Активная героиня остаётся на месте."""
        if hasattr(res, "get") and res.get("ok") is False:
            return
        try:
            reply = res.get("reply", "") if hasattr(res, "get") else ""
        except Exception:
            reply = ""
        ES_AI_CAMEO_PLAYER_TEXT[0] = player_text or u""
        es_ai_recent_push(u"Игрок", player_text)
        es_ai_recent_push(es_ai_cameo_name(active_id), reply)
        try:
            import json
            debug = res.get("scene_debug") if hasattr(res, "get") else None
            keys = ("build", "source", "pid", "scene_received", "enabled", "capacity", "active",
                    "present", "available", "invitable", "direct_result", "address_id",
                    "address_reason", "origin", "status", "failure", "chosen_cameo",
                    "runtime", "primary_before", "primary_after", "auto_primary", "movement_blocked",
                    "runtime_chain", "player_goto", "switch_primary", "travel_with", "travel_all", "cameo_aside",
                    "response_id", "response_switch", "response_goto", "response_dress", "suppress_main_reply")
            clean = {}
            if isinstance(debug, _es_ai_cameo_builtins.dict):
                for key in keys:
                    value = debug.get(key)
                    if isinstance(value, basestring):
                        clean[key] = value[:512] if key == "source" else value[:64]
                    elif isinstance(value, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)):
                        clean[key] = [cid[:32] for cid in value[:64] if isinstance(cid, basestring)]
                    elif value is None or isinstance(value, (bool, int, long)):
                        clean[key] = value
            es_ai_log("scene server: " + json.dumps(clean if isinstance(debug, _es_ai_cameo_builtins.dict) else
                      {"status": "missing-scene-debug"}, ensure_ascii=True, sort_keys=True))
            requested = res.get("cameo", []) if hasattr(res, "get") else []
            explicit = isinstance(requested, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)) and bool(requested)
            enabled = es_ai_cameo_on()
            existing = set(g["id"] for g in ES_AI_SHOWN)
            es_ai_log("scene action: requested=%r current=%s present=%r enabled=%s"
                      % (requested if explicit else [], active_id, sorted(existing), enabled))
            if res.get("privacy") and not res.get("movement_blocked"):
                return
            if not enabled:
                return
            st = es_ai_read_cameo_settings()
            explicit_handled = False
            npc_calls = res.get("npc_calls", [])
            if st.get("npc_activity_enabled", True) is not True:
                # Ignore stale schedule outcomes, but deliver this exchange's invitations.
                requested = list(requested) if explicit else []
                if isinstance(npc_calls, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)):
                    requested.extend(call.get("id") for call in npc_calls[:6]
                                     if isinstance(call, _es_ai_cameo_builtins.dict)
                                     and call.get("status") in ("pending", "refused", "ready")
                                     and call.get("id") not in requested)
                explicit = bool(requested)
                npc_calls = []
            if player_text and isinstance(npc_calls, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)):
                known = set(c[0] for c in ES_AI_CHARS) - {active_id}
                for call in npc_calls[:6]:
                    if not isinstance(call, _es_ai_cameo_builtins.dict):
                        continue
                    cid, status, wait = call.get("id"), call.get("status"), call.get("wait_turns")
                    if (isinstance(cid, basestring) and cid in known
                            and call.get("location_id") == ES_AI_LOC_CUR[0]
                            and isinstance(call.get("reason"), basestring)
                            and type(wait) is _es_ai_cameo_builtins.int
                            and ((status == "pending" and 1 <= wait <= 3)
                                 or (status in ("refused", "ready") and wait == 0))):
                        explicit_handled = True
                        break
            activity_exchange = globals().get("es_ai_activity_exchange")
            ready = activity_exchange(res) if callable(activity_exchange) else []
            if ready:
                requested = list(requested) if explicit else []
                requested.extend(cid for cid in ready if cid not in requested)
                explicit = bool(requested)
                if any(ES_AI_ACTIVITY_PENDING[cid].get("replace") for cid in ready):
                    res["cameo_replace"] = True
            requested_leave = res.get("cameo_leave", []) if hasattr(res, "get") else []
            if isinstance(requested_leave, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)) and requested_leave:
                leaving = []
                local = existing | set(g["id"] for g in ES_AI_CAMEO_NEARBY.get(ES_AI_LOC_CUR[0], []))
                for cid in requested_leave:
                    if isinstance(cid, basestring) and cid != active_id and cid in local and cid not in leaving:
                        leaving.append(cid)
                for cid in [c for c in leaving if c in existing][:2]:
                    line = es_ai_cameo_line(cid, active_id, False, mode="leave",
                        story_token=res.get("story_token"),
                        others=[es_ai_cameo_name(c) for c in sorted(existing) if c not in (cid, active_id)])
                    text = line.get("reply") if line else None
                    text = text or u"До встречи!"
                    es_ai_recent_push(es_ai_cameo_name(cid), text)
                    es_ai_cameo_speak(cid, text, line.get("emotion") if line else None,
                                      line.get("dress") if line else None,
                                      line.get("story_ack") if line and line.get("reply", "").strip() else None,
                                      line.get("choices") if line and line.get("reply", "").strip() else None)
                for cid in leaving:
                    es_ai_cameo_leave(cid)
                    absent = globals().setdefault("ES_AI_SCENE_ABSENT", {}).setdefault(ES_AI_LOC_CUR[0], [])
                    if cid not in absent:
                        absent.append(cid)
                    globals().get("ES_AI_ACTIVITY_PENDING", {}).pop(cid, None)
                    es_ai_log("cameo requested leave: %s" % cid)
                requested = [cid for cid in requested if cid not in requested_leave] if explicit else []
                explicit = bool(requested)
                existing = set(g["id"] for g in ES_AI_SHOWN)
                if not explicit:
                    return
            if not explicit and (explicit_handled or res.get("cameo_requested") is True):
                if not st["cameo_stay"]:
                    if globals().get("ES_AI_ACTIVITY_PENDING"):
                        es_ai_cameo_clear(clear_pending=False)
                    else:
                        es_ai_cameo_clear()
                return
            if explicit:
                # Revalidate against the live scene: it may have changed during HTTP.
                scene = es_ai_scene_snapshot(active_id, st)
                known = set(c[0] for c in ES_AI_CHARS)
                cameos = []
                slots = scene["capacity"]
                protected = set(cid for cid in requested if isinstance(cid, basestring))
                for cid in requested:
                    if not isinstance(cid, basestring) or cid not in known \
                            or cid == active_id or cid in cameos:
                        continue
                    if cid not in existing:
                        while slots <= 0 and res.get("cameo_replace") is True:
                            victims = [g for g in ES_AI_SHOWN if g.get("cameo")
                                       and g["id"] != active_id and g["id"] not in protected]
                            if not victims:
                                break
                            if victims:
                                victim = _es_ai_cameo_builtins.min(victims, key=lambda g: (
                                    bool(g.get("focused")), -next((a.get("turns", 0)
                                    for a in ES_AI_CAMEO_ACTIVE if a["id"] == g["id"]), 0)))
                                es_ai_cameo_park(victim["id"])
                                existing.discard(victim["id"])
                                slots = _es_ai_cameo_builtins.max(0, es_ai_cameo_capacity(st=st)
                                    - len(existing - {active_id}) - len([c for c in cameos if c not in existing]))
                        if cid not in scene["invitable"] or slots <= 0:
                            continue
                        slots -= 1
                    cameos.append(cid)
                    if len(cameos) >= 6:
                        break
                if cameos != list(requested):
                    es_ai_log("scene action filtered: accepted=%r capacity=%s invitable=%r"
                              % (cameos, scene["capacity"], scene["invitable"]))
                romantic = False
                if any(cid not in existing for cid in cameos):
                    ES_AI_CAMEO_CD[0] = ES_AI_CAMEO_COOLDOWN
            else:
                es_ai_cameo_tick(active_id, st)
                romantic = es_ai_is_romantic_moment(active_id, player_text, reply)
                cameos = es_ai_maybe_cameo(active_id, romantic)
            if cameos:
                for cid in cameos:
                    globals().get("ES_AI_ACTIVITY_PENDING", {}).pop(cid, None)
                es_ai_cameo_deliver_group(cameos, active_id, romantic, st, explicit=explicit,
                                         story_token=res.get("story_token") if explicit else None)
                if romantic and active_id in ES_AI_ROMANCEABLE:
                    es_ai_set_dress("cover")   # застали врасплох — героиня прикрывается
        except Exception as e:
            import traceback
            es_ai_log("cameo error: %s\n%s" % (type(e).__name__, traceback.format_exc()))
        finally:
            ES_AI_CAMEO_PLAYER_TEXT[0] = u""
