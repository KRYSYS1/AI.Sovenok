# -*- coding: utf-8 -*-
# AI Совёнок — камео: с некоторой вероятностью в сцену заходит другой персонаж
# (как в сюжете). Вероятность выше в романтический момент, максимальна — если это
# комната «хозяина» локации (например вожатая застаёт вас у неё в комнате).

init -10 python:
    import random as _es_random

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
        "beach": ["us", "mi", "dv"], "island": ["us", "dv"], "boathouse": ["us", "uv"],
        "bathhouse": ["mt", "us"],
        "playground": ["us", "sl"], "washstand": ["us", "mi"],
        "square": ["mt", "us", "sl", "dv", "el", "cs"], "houses": ["mt", "us", "sl"],
        "path": ["mz", "mi", "uv", "cs"], "polyana": ["mz", "un", "sl", "uv"],
        "stage": ["mi", "sl", "uv"], "stage_big": ["mi", "sl", "uv"],
        "camp_gate": ["mt"], "gate_no_bus": ["mt"], "road": ["mt"],
        "bus_gate": ["mt"], "bus_inside": ["us", "dv"],
        "old_building": ["uv", "sh", "el"], "catacombs": ["uv", "cs", "sh"],
        "mine": ["uv", "sh"],
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

    # Настройки частоты (можно крутить).
    ES_AI_CAMEO_P_OWNER = 0.55     # хозяин(ка) застаёт в свой комнате при романтике
    ES_AI_CAMEO_P_ROMANTIC = 0.22  # романтика в романтической локации
    ES_AI_CAMEO_P_ROMANTIC_OTHER = 0.12
    ES_AI_CAMEO_P_PASSBY = 0.05    # кто-то просто проходит мимо
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
               u"(серьёзность) Семён, это лагерь, а не место для свиданий.",
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
               u"(нормально) Семён, потом зайди ко мне."],
        "dv": [u"(усмешка) О, вы всё ещё тут?"],
        "us": [u"(смех) Приве-ет! А я тут мимо пробегала!"],
        "sl": [u"(улыбка) Ой, привет! Хорошо проводите время?"],
        "sh": [u"(нормально) Я в клуб. Если Электроник спросит — я уже иду."],
        "mz": [u"(нормально) Книгу на место. Сам знаешь, где стеллаж."],
        "cs": [u"(нормально) Если что-то болит — приходи в медпункт, а не терпи."],
        "mi": [u"(улыбка) Коннитива! Не буду мешать, ня."],
        "un": [u"(смущение) А, привет… я просто проходила мимо."],
    }


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

    def es_ai_cameo_chance(cameo_id, romantic):
        loc_id = ES_AI_LOC_CUR[0]
        if romantic:
            if cameo_id in ES_AI_LOC_OWNERS.get(loc_id, []):
                return ES_AI_CAMEO_P_OWNER
            if ES_AI_LOCATION_INDEX.get(loc_id, {}).get("romantic"):
                return ES_AI_CAMEO_P_ROMANTIC
            return ES_AI_CAMEO_P_ROMANTIC_OTHER
        return ES_AI_CAMEO_P_PASSBY

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
            if isinstance(data, dict) and "cameo_enabled" in data:
                return bool(data.get("cameo_enabled"))
        except Exception:
            pass
        return None

    def es_ai_write_cameo_flag(enabled):
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
            if not isinstance(data, dict):
                data = {}
            data["cameo_enabled"] = bool(enabled)
            f = io.open(path, "w", encoding="utf-8")
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            finally:
                f.close()
        except Exception:
            pass

    def es_ai_cameo_on():
        flag = es_ai_read_cameo_flag()
        if flag is None:
            return bool(getattr(persistent, "es_ai_cameo", True))
        persistent.es_ai_cameo = bool(flag)
        return bool(flag)

    def es_ai_toggle_cameo():
        cur = es_ai_cameo_on()
        persistent.es_ai_cameo = not cur
        es_ai_write_cameo_flag(not cur)

    def es_ai_sync_cameo_from_file():
        es_ai_cameo_on()

    def es_ai_maybe_cameo(active_id, romantic):
        """Решить, кто зайдёт. Возвращает СПИСОК id (обычно 1, иногда 2 — «пришли
        вместе»), или [] если никто. Список — чтобы поддержать сборку/разборку
        нескольких персонажей в сцене по контексту локации."""
        if not es_ai_cameo_on():
            return []
        if ES_AI_CAMEO_CD[0] > 0:
            ES_AI_CAMEO_CD[0] -= 1
            return []
        loc_id = ES_AI_LOC_CUR[0]
        shown = set(g["id"] for g in ES_AI_SHOWN)
        cands = [c for c in ES_AI_CAMEO_BY_LOC.get(loc_id, [])
                 if c != active_id and c not in shown]
        if not cands:
            return []
        owners = [c for c in cands if c in ES_AI_LOC_OWNERS.get(loc_id, [])]
        pool = owners if (romantic and owners) else cands
        cameo = _es_random.choice(pool)
        if _es_random.random() >= es_ai_cameo_chance(cameo, romantic):
            return []
        result = [cameo]
        # Иногда рядом оказывается «неразлучная» пара (Алиса+Ульяна, Лена+Алиса и т.п.):
        # с небольшим шансом заходит второй персонаж из этой же локации.
        rest = [c for c in cands if c != cameo]
        if rest and _es_random.random() < ES_AI_CAMEO_P_COMPANION:
            mate = None
            for pair in ES_AI_CAMEO_PAIRS:
                if cameo in pair:
                    for other in pair:
                        if other in rest:
                            mate = other
                            break
                if mate:
                    break
            if mate is None:
                mate = _es_random.choice(rest)
            result.append(mate)
        ES_AI_CAMEO_CD[0] = ES_AI_CAMEO_COOLDOWN
        return result

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

    def es_ai_cameo_line(cameo_id, active_id, romantic):
        """Реплика камео от сервера (LLM). None — если сервер недоступен."""
        payload = {"character": cameo_id, "active": es_ai_cameo_name(active_id),
                   "location": es_ai_location().get("desc", u""),
                   "romantic": bool(romantic)}

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

    def es_ai_cameo_enter(cameo_id, emotion):
        emo = emotion or "surprise"
        for g in ES_AI_SHOWN:
            if g["id"] == cameo_id:
                g["emo"] = emo
                g["dress"] = None
                es_ai_refresh_girls()
                return
        ES_AI_SHOWN.append({"id": cameo_id, "emo": emo, "dress": None, "cameo": True})
        es_ai_refresh_girls()

    def es_ai_cameo_leave(cameo_id):
        ES_AI_SHOWN[:] = [g for g in ES_AI_SHOWN if g.get("id") != cameo_id]
        try:
            renpy.hide(cameo_id)
        except Exception:
            pass
        es_ai_refresh_girls()

    def es_ai_cameo_speak(cameo_id, text):
        """Реплика уже вошедшего камео-персонажа (без входа/ухода)."""
        raw = (text or u"").strip()
        if not raw:
            return
        if persistent.es_ai_tts:
            try:
                es_ai_speak_async(raw, cameo_id)
            except Exception:
                pass
        safe = es_ai_sanitize_text(raw)
        es_ai_internal_speaking[0] = True
        try:
            es_ai_speakers[cameo_id](safe)
        finally:
            es_ai_internal_speaking[0] = False

    def es_ai_try_cameo(active_id, player_text, res):
        """Главная точка: вызвать после реплики героини. Сам решает, кого звать.
        Поддерживает вход СРАЗУ нескольких персонажей (сборка сцены), после чего
        все они уходят (разборка). Активная героиня остаётся на месте."""
        if not persistent.es_ai_cameo:
            return
        try:
            reply = res.get("reply", "") if hasattr(res, "get") else ""
            romantic = es_ai_is_romantic_moment(active_id, player_text, reply)
            cameos = es_ai_maybe_cameo(active_id, romantic)
            if not cameos:
                return
            # 1) собираем реплики для всех зашедших
            lines = []
            for cid in cameos:
                line = es_ai_cameo_line(cid, active_id, romantic)
                if line and line.get("reply"):
                    emo, text = line.get("emotion"), line.get("reply")
                else:
                    emo, text = es_ai_cameo_split(es_ai_cameo_fallback(cid, romantic))
                lines.append((cid, emo, text))
                es_ai_log("cameo: %s -> %r (romantic=%s)" % (cid, text, romantic))
            # 2) все входят в сцену вместе
            for cid, emo, _t in lines:
                es_ai_cameo_enter(cid, emo)
            try:
                renpy.with_statement(dissolve)
            except Exception:
                pass
            # 3) по очереди говорят
            for cid, _e, text in lines:
                es_ai_cameo_speak(cid, text)
            # 4) уходят
            for cid, _e, _t in lines:
                es_ai_cameo_leave(cid)
            try:
                renpy.with_statement(dissolve)
            except Exception:
                pass
            if romantic and active_id in ES_AI_ROMANCEABLE:
                es_ai_set_dress("cover")   # застали врасплох — героиня прикрывается
        except Exception as e:
            es_ai_log("cameo error: %s" % e)
