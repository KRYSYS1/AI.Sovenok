# -*- coding: utf-8 -*-
# AI Совёнок — ядро мода: регистрация в меню модов, автостарт сервера,
# словари эмоций/спрайтов, утилиты.
#
# Часть проекта ES-AI-Mod. Сервер (Python 3) лежит рядом: mods/es_ai/server/
# Устройство перенято у AI_lena (workshop) и у схемы kcd2-ai-npc / Smart Lolis.

################################################################################
## Регистрация в меню модов Бесконечного лета
################################################################################

init 1 python:
    mods["es_ai"] = "AI Совёнок"

################################################################################
## Константы и настройки
################################################################################

init -10 python:
    import os
    import sys
    import json
    import threading
    import time as _time
    import subprocess
    import urllib2
    import atexit

    # Папка мода. Два варианта установки:
    #   1) вручную/установщиком: game/mods/es_ai/        -> ассеты "mods/es_ai/..."
    #   2) Steam Workshop: workshop/content/331470/<id>/  -> ассеты "..." (корень
    #      папки мастерской сам входит в config.searchpath, см. renpy/main.py)
    # ES_AI_REL — префикс для путей, которые открывает загрузчик Ren'Py.
    def _es_ai_is_mod_dir(d):
        try:
            return ((os.path.exists(os.path.join(d, "es_ai.rpy"))
                     or os.path.exists(os.path.join(d, "es_ai.rpyc")))
                    and os.path.isdir(os.path.join(d, "server")))
        except Exception:
            return False

    def _es_ai_find_mod_dir():
        local = os.path.join(config.gamedir, "mods", "es_ai")
        if _es_ai_is_mod_dir(local):
            return os.path.normpath(os.path.abspath(local)), "mods/es_ai/"
        for sp in list(config.searchpath or []):
            try:
                d = os.path.abspath(sp)
            except Exception:
                continue
            sub = os.path.join(d, "mods", "es_ai")
            if _es_ai_is_mod_dir(sub):
                return os.path.normpath(sub), "mods/es_ai/"
            if _es_ai_is_mod_dir(d):
                return os.path.normpath(d), ""
        return os.path.normpath(local), "mods/es_ai/"

    ES_AI_MOD_DIR, ES_AI_REL = _es_ai_find_mod_dir()
    ES_AI_SERVER_DIR = os.path.join(ES_AI_MOD_DIR, "server")
    ES_AI_LOG_PATH = os.path.join(ES_AI_MOD_DIR, "log.txt")

    # Состояние сервера: "checking" | "starting" | "ready" | "down" | "disabled"
    es_ai_server_state = "checking"
    es_ai_server_info = ""
    es_ai_health = {}
    es_ai_autostart_process = None

    def es_ai_log(msg):
        try:
            line = u"[%s] %s\n" % (_time.strftime("%H:%M:%S"), msg)
            with open(ES_AI_LOG_PATH, "a") as f:
                f.write(line.encode("utf-8", "replace"))
        except Exception:
            pass

    # Дефолты persistent (как флаги фич в Smart Lolis)
    if persistent.es_ai_tts is None:
        persistent.es_ai_tts = True          # озвучка ответов в чате
    if persistent.es_ai_novel_voice is None:
        persistent.es_ai_novel_voice = False # озвучка оригинального романа
    if persistent.es_ai_overlay_key is None:
        persistent.es_ai_overlay_key = "a"   # клавиша чата поверх новеллы
    if persistent.es_ai_last_char is None:
        persistent.es_ai_last_char = "un"
    if persistent.es_ai_last_char == "vi":
        persistent.es_ai_last_char = "cs"

################################################################################
## Персонажи и эмоции
##
## Эмоции извлечены из sprites.rpyc игры: валидные теги вида
## "{id} {эмоция} {одежда} [close|far]". Ключ — эмоция от сервера.
################################################################################

init -10 python:
    # id = префикс спрайта в sprites.rpyc (не путать!):
    #   mz = Женя (библиотекарь), sh = Шурик, cs = Виола (медсестра).
    # Раньше sh/mz были перепутаны, а Виолу искали как несуществующий vi.
    ES_AI_CHARS = [
        ("sl", u"Славя", "#7EA854"),
        ("dv", u"Алиса", "#EE5C42"),
        ("un", u"Лена", "#8DB6CD"),
        ("us", u"Ульяна", "#FFD700"),
        ("mi", u"Мику", "#5CCFEA"),
        ("mz", u"Женя", "#9932CC"),
        ("mt", u"Ольга Дмитриевна", "#CD5C5C"),
        ("uv", u"Юля", "#F0A6CA"),
        ("el", u"Электроник", "#4E9AD1"),
        ("sh", u"Шурик", "#6FAE5B"),
        ("cs", u"Виола", "#7D5BA6"),
    ]

    # Кому можно романтику. Ульяна (us) — канонически ребёнок (~14 лет), поэтому
    # исключена из ЛЮБЫХ романтических механик мода (переодевание «для настроения»,
    # «поимка» камео, флирт). Парни (el, sh) — не романтические цели. Остальные
    # героини — по дисклеймеру игры совершеннолетние.
    ES_AI_ROMANCEABLE = set(["sl", "dv", "un", "mi", "mz", "mt", "uv", "cs"])

    # Примерный рост (см). Кто ниже — тот на переднем плане (выше zorder), чтобы
    # низкие (Ульяна 143) не пропадали за высокими при совместных сценах.
    ES_AI_HEIGHTS = {
        "mt": 170, "sl": 168, "un": 160, "dv": 158,
        "mi": 157, "mz": 155, "us": 143,
        "el": 176, "sh": 174, "cs": 175, "uv": 154,
    }

    ES_AI_EMOTIONS = {
        "sl": ["angry", "happy", "laugh", "normal", "sad", "scared", "serious", "shy", "smile", "smile2", "surprise", "tender"],
        "dv": ["angry", "cry", "grin", "guilty", "laugh", "normal", "rage", "sad", "scared", "shocked", "shy", "smile", "surprise"],
        "un": ["angry", "angry2", "cry", "cry_smile", "evil_smile", "grin", "laugh", "normal", "rage", "sad", "scared", "serious", "shocked", "shy", "smile", "smile2", "smile3", "surprise"],
        "mi": ["angry", "cry", "cry_smile", "dontlike", "grin", "happy", "laugh", "normal", "rage", "sad", "scared", "serious", "shocked", "shy", "smile", "surprise", "upset"],
        "us": ["angry", "calml", "cry", "cry2", "dontlike", "fear", "grin", "laugh", "laugh2", "normal", "sad", "shy", "shy2", "smile", "surp1", "surp2", "surp3", "upset"],
        "sh": ["cry", "laugh", "normal", "normal_smile", "rage", "scared", "serious", "smile", "surprise", "upset"],
        "mt": ["angry", "grin", "laugh", "normal", "rage", "sad", "scared", "shocked", "smile", "surprise"],
        "uv": ["normal", "smile", "laugh", "grin", "sad", "dontlike", "guilty", "shocked", "surprise", "surprise2", "upset", "rage"],
        "el": ["normal", "smile", "laugh", "grin", "sad", "serious", "scared", "shocked", "surprise", "upset", "angry"],
        "mz": ["normal", "smile", "laugh", "angry", "rage", "shy"],
        "cs": ["normal", "shy", "smile"],
    }

    # Русские слова эмоций -> универсальный ключ
    ES_AI_EMOTION_RU = {
        u"нормально": "normal", u"спокойствие": "normal",
        u"улыбка": "smile", u"смущение": "shy", u"стеснение": "shy",
        u"грусть": "sad", u"злость": "angry", u"удивление": "surprise",
        u"страх": "scared", u"испуг": "scared", u"смех": "laugh",
        u"радость": "happy", u"плачь": "cry", u"плач": "cry", u"слёзы": "cry",
        u"ярость": "rage", u"шок": "shocked", u"усмешка": "grin", u"ухмылка": "grin",
        u"серьёзность": "serious", u"нежность": "tender", u"обида": "upset",
        u"недовольство": "dontlike", u"вина": "guilty",
    }

    # Имя в романе -> id персонажа (для озвучки оригинальных реплик)
    ES_AI_NAME_TO_ID = {
        u"Славя": "sl", u"Алиса": "dv", u"Лена": "un", u"Ульяна": "us",
        u"Мику": "mi", u"Женя": "mz", u"Ольга Дмитриевна": "mt",
        u"Юля": "uv", u"Электроник": "el", u"Шурик": "sh", u"Виола": "cs",
    }

    # Порядок перебора одежды/дистанции при подборе спрайта
    ES_AI_DRESSES = ["pioneer", "sport", "dress", "swim", ""]

    def es_ai_resolve_sprite(char_id, emotion, dress_pref=None):
        """Эмоция -> существующий тег спрайта игры (с проверкой renpy.has_image).
        dress_pref — предпочтительная одежда (например swim на пляже)."""
        emotion = (emotion or "").strip().lower()
        vocab = ES_AI_EMOTIONS.get(char_id, [])
        if emotion not in vocab:
            key = ES_AI_EMOTION_RU.get(emotion, emotion)
            if key not in vocab:
                emotion = es_ai_fallback_emotion(char_id, key)
        candidates = []
        # Виола (cs): нет тега pioneer, есть вариант со стетоскопом.
        if char_id == "cs":
            candidates.append("%s %s stethoscope close" % (char_id, emotion))
            candidates.append("%s %s stethoscope" % (char_id, emotion))
        dresses = ([dress_pref] if dress_pref else []) + ES_AI_DRESSES
        seen_d = set()
        dresses = [d for d in dresses if not (d in seen_d or seen_d.add(d))]
        for dress in dresses:
            if dress:
                candidates.append("%s %s %s close" % (char_id, emotion, dress))
                candidates.append("%s %s %s" % (char_id, emotion, dress))
            else:
                candidates.append("%s %s close" % (char_id, emotion))
                candidates.append(char_id + " " + emotion)
        for tag in candidates:
            if renpy.has_image(tag):
                return tag
        # Совсем ничего — нормальная эмоция
        for dress in ES_AI_DRESSES:
            base = "%s normal %s" % (char_id, dress) if dress else "%s normal" % char_id
            for tag in (base + " close", base):
                if renpy.has_image(tag):
                    return tag
        return None

    def es_ai_fallback_emotion(char_id, key):
        """Подбор ближайшей допустимой эмоции, если у персонажа её нет."""
        chains = {
            "shy": ["shy", "smile", "normal"], "smile": ["smile", "happy", "normal"],
            "sad": ["sad", "cry", "normal"], "angry": ["angry", "rage", "normal"],
            "surprise": ["surprise", "shocked", "normal"], "scared": ["scared", "shocked", "normal"],
            "laugh": ["laugh", "grin", "normal"], "happy": ["happy", "smile", "normal"],
            "cry": ["cry", "sad", "normal"], "rage": ["rage", "angry", "normal"],
            "shocked": ["shocked", "surprise", "normal"], "grin": ["grin", "laugh", "normal"],
            "serious": ["serious", "normal"], "tender": ["tender", "smile", "normal"],
            "upset": ["upset", "sad", "normal"], "dontlike": ["dontlike", "angry", "normal"],
            "guilty": ["guilty", "sad", "normal"], "normal": ["normal"],
        }
        for cand in chains.get(key, ["normal"]):
            if cand in ES_AI_EMOTIONS.get(char_id, []):
                return cand
        return "normal"

    def es_ai_char_name(char_id):
        for cid, name, _color in ES_AI_CHARS:
            if cid == char_id:
                return name
        return "?"

    def es_ai_char_color(char_id):
        for cid, _name, color in ES_AI_CHARS:
            if cid == char_id:
                return color
        return "#FFFFFF"

################################################################################
## Автостарт сервера
##
## Как в AI_lena (subprocess + скрытое окно), но без блокировки init:
## проверка health и запуск идут в фоновом потоке.
################################################################################

init 10 python:
    import urllib2 as _u2

    ES_AI_TIMEOUT_SHORT = 4
    ES_AI_TIMEOUT_LONG = 120

    def es_ai_server_url():
        return persistent.es_ai_server_url or "http://127.0.0.1:40310"

    # Разовый перенос со старых дефолтов: 4999 (конфликт с KCD2 AI NPC) и 33147
    if (persistent.es_ai_server_url is None
            or ":4999" in persistent.es_ai_server_url
            or ":33147" in persistent.es_ai_server_url):
        persistent.es_ai_server_url = "http://127.0.0.1:40310"

    def es_ai_http(path, payload=None, timeout=ES_AI_TIMEOUT_LONG):
        """Синхронный запрос к серверу. Возвращает dict, кидает исключение."""
        url = es_ai_server_url() + path
        if payload is None:
            req = _u2.Request(url, headers={"Content-Type": "application/json"})
        else:
            data = json.dumps(payload)
            req = _u2.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = _u2.urlopen(req, timeout=timeout)
        return json.loads(resp.read())

    def _es_ai_check_health():
        try:
            h = es_ai_http("/health", timeout=2)
            if h.get("ok"):
                return h
        except Exception:
            pass
        return None

    def _es_ai_find_python():
        """Ищем python3: скан PATH + известные расположения. Python 2.7-совместимо."""
        import glob as _glob
        cands = []
        try:
            for d in os.environ.get("PATH", "").split(os.pathsep):
                if not d:
                    continue
                cands.append(os.path.join(d, "python.exe"))
                cands.append(os.path.join(d, "python3.exe"))
                cands.append(os.path.join(d, "py.exe"))
        except Exception:
            pass
        for pat in ["C:\\Windows\\py.exe",
                    "C:\\Python*\\python.exe",
                    "C:\\Program Files\\Python*\\python.exe",
                    os.path.expanduser("~\\AppData\\Local\\Programs\\Python\\Python*\\python.exe")]:
            try:
                for m in _glob.glob(pat):
                    cands.append(m)
            except Exception:
                pass

        seen = set()
        for exe in cands:
            if exe in seen or not os.path.exists(exe):
                continue
            seen.add(exe)
            base = os.path.basename(exe).lower()
            if base == "py.exe":
                return [exe, "-3"]
            # проверяем, что это Python 3
            try:
                p = subprocess.Popen(
                    [exe, "-c", "import sys; print(sys.version_info[0])"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE, creationflags=0x08000000)
                out = p.stdout.read()
                p.wait()
                if "3" in out:
                    return [exe]
            except Exception:
                continue
        return None

    def _es_ai_autostart_thread():
        global es_ai_server_state, es_ai_server_info, es_ai_health
        try:
            h = _es_ai_check_health()
            if h:
                es_ai_health = h
                es_ai_server_state = "ready"
                es_ai_server_info = "сервер уже запущен"
                es_ai_log("server ready (already running)")
                return

            main_py = os.path.join(ES_AI_SERVER_DIR, "main.py")
            if not os.path.exists(main_py):
                es_ai_server_state = "down"
                es_ai_server_info = "нет папки server/ рядом с модом (%s)" % ES_AI_SERVER_DIR
                es_ai_log("autostart failed: no server/main.py")
                return

            cmd = _es_ai_find_python()
            if not cmd:
                es_ai_server_state = "down"
                es_ai_server_info = "Python 3 не найден в PATH — запусти start_server.bat вручную"
                es_ai_log("autostart failed: python3 not found")
                return

            es_ai_server_state = "starting"
            full_cmd = cmd + [main_py]
            global es_ai_autostart_process
            try:
                es_ai_autostart_process = subprocess.Popen(
                    full_cmd, cwd=ES_AI_SERVER_DIR, creationflags=0x08000000)
            except Exception as e:
                es_ai_server_state = "down"
                es_ai_server_info = "не удалось запустить сервер: %s" % e
                es_ai_log("autostart exception: %s" % e)
                return

            # Ждём подъёма до 20 секунд
            for _i in range(40):
                _time.sleep(0.5)
                h = _es_ai_check_health()
                if h:
                    es_ai_health = h
                    es_ai_server_state = "ready"
                    es_ai_server_info = "сервер запущен модом"
                    es_ai_log("server ready (autostart)")
                    return
            es_ai_server_state = "down"
            es_ai_server_info = "сервер не отвечает (см. %s)" % ES_AI_SERVER_DIR
            es_ai_log("autostart timeout")
        except Exception as e:
            es_ai_server_state = "down"
            es_ai_server_info = str(e)
            es_ai_log("autostart thread error: %s" % e)

    def es_ai_start_server_async():
        t = threading.Thread(target=_es_ai_autostart_thread)
        t.daemon = True
        t.start()

    def es_ai_stop_autostart():
        try:
            if es_ai_autostart_process is not None:
                es_ai_autostart_process.terminate()
        except Exception:
            pass

    atexit.register(es_ai_stop_autostart)
    es_ai_start_server_async()
    es_ai_log("mod init, gamedir=%s, mod_dir=%s, rel=%r"
              % (config.gamedir, ES_AI_MOD_DIR, ES_AI_REL))

################################################################################
## Аудио: регистрация TTS-канала + заплатка гонки аудиопотока Ren'Py 7.4
##
## В 7.4.11 фоновый аудиопоток периодически дергает Channel.periodic() ->
## get_context() -> renpy.game.context() — а в момент смены контекстов
## (выход из мода в меню, запуск новой игры) список renpy.game.contexts
## бывает пуст, и поток ловит IndexError: contexts[index]. Исключение
## откладывается и выстреливает в следующем interact ("IndexError: list
## index out of range" на первой же реплике). Заглушка ниже возвращает
## временный MusicContext(), когда контекстов нет, и гонка исчезает.
################################################################################

init 1 python:
    # Канал озвучки мода (mixer "voice" — громкость берётся из слайдера голоса)
    renpy.music.register_channel("es_voice", mixer="voice", loop=False,
                                 stop_on_mute=True, tight=False)

init 999 python:
    import renpy.game as _es_rg
    import renpy.audio.audio as _es_audio

    _es_ai_orig_get_context = _es_audio.Channel.get_context

    def _es_ai_safe_get_context(self):
        try:
            if not _es_rg.contexts:
                return _es_audio.MusicContext()
        except Exception:
            return _es_audio.MusicContext()
        return _es_ai_orig_get_context(self)

    # Важно: в коде движка есть оба пути — прямой вызов c.get_context()
    # (цикл в audio.periodic) и обращение к property self.context
    # (Channel.periodic, строка 437). property держит ссылку на исходную
    # функцию, поэтому патчим и метод, и property.
    _es_audio.Channel.get_context = _es_ai_safe_get_context
    _es_audio.Channel.context = property(_es_ai_safe_get_context)
    es_ai_log("audio guard installed")
