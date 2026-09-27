# -*- coding: utf-8 -*-
# AI Совёнок — API-слой: фоновые запросы к серверу, очередь TTS, голосовой ввод.
#
# Потоки + флаги вместо async (Python 2.7): результат отдаётся через объект
# EsAiJob, игра ждёт его в лейбле циклом с renpy.pause.

init 10 python:
    import threading
    import os
    import shutil

    class EsAiJob:
        """Результат фонового запроса: ждём .done в лейбле, читаем .result/.error."""
        def __init__(self, kind=""):
            self.kind = kind
            self.done = False
            self.result = None
            self.error = None

    def es_ai_run_async(kind, fn):
        job = EsAiJob(kind)

        def worker():
            try:
                job.result = fn()
            except Exception as e:
                job.error = str(e)
            job.done = True

        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()
        return job

    def es_ai_sanitize_text(text):
        """LLM-текст для Ren'Py: экранируем { и [, чтобы не ломать text-теги."""
        if not text:
            return ""
        return text.replace("{", "{{").replace("[", "[[")

    # ---------------------------------------------------------- запросы ----

    def es_ai_chat_async(char_id, text, novel_context=None, speaker=""):
        payload = {"character": char_id, "text": text,
                   "novel_context": novel_context or [], "speaker": speaker}
        if es_ai_chat_active[0]:
            payload["location"] = es_ai_location_context()

        def fn():
            r = es_ai_http("/chat", payload)
            if not r.get("ok"):
                raise Exception(r.get("error", "неизвестная ошибка сервера"))
            return r

        return es_ai_run_async("chat", fn)

    def es_ai_report_loc(loc_id):
        """Сообщить серверу текущую локацию (для маркера «вы здесь» в окне
        настроек, вкладка «Карта»). Тихо и в фоне — не мешает игре."""
        try:
            name = ES_AI_LOCATION_INDEX.get(loc_id, {}).get("name", u"")
        except Exception:
            name = u""

        def fn():
            try:
                es_ai_http("/state/loc", {"loc": loc_id, "loc_name": name},
                           timeout=ES_AI_TIMEOUT_SHORT)
            except Exception:
                pass
            return None

        try:
            es_ai_run_async("state", fn)
        except Exception:
            pass

    def es_ai_initiative_async(char_id, novel_context=None):
        payload = {"character": char_id, "novel_context": novel_context or []}
        if es_ai_chat_active[0]:
            payload["location"] = es_ai_location_context()

        def fn():
            r = es_ai_http("/initiative", payload)
            if not r.get("ok"):
                raise Exception(r.get("error", "неизвестная ошибка сервера"))
            return r

        return es_ai_run_async("initiative", fn)

    def es_ai_stt_async(max_seconds=8):
        payload = {"max_seconds": max_seconds}

        def fn():
            r = es_ai_http("/stt/record", payload, timeout=ES_AI_TIMEOUT_SHORT + max_seconds + 30)
            if not r.get("ok"):
                raise Exception(r.get("error", "микрофон недоступен"))
            return r.get("text", "")

        return es_ai_run_async("stt", fn)

    def es_ai_clear_history_async(char_id=None):
        payload = {"character": char_id}

        def fn():
            return es_ai_http("/history/clear", payload, timeout=ES_AI_TIMEOUT_SHORT)

        return es_ai_run_async("clear", fn)

    # -------------------------------------------------------------- TTS ----

    es_ai_tts_queue = []       # пути к mp3, играет es_ai_tts_pump
    es_ai_tts_jobs = []        # фоновые синтезы; забирает pump в главном потоке
    es_ai_tts_counter = [0]

    def es_ai_tts_relpath(path):
        """Путь, который Ren'Py откроет: относительно game/, без обратных слэшей.

        Абсолютный Windows-путь с \\ ломает loader (reject_backslash) — из-за
        этого тест в окне настроек (MCI) играл, а реплика в игре молчала.
        """
        if not path:
            return path
        path = path.replace("\\", "/")
        try:
            gd = config.gamedir.replace("\\", "/")
            if path.lower().startswith(gd.lower() + "/"):
                return path[len(gd) + 1:]
        except Exception:
            pass
        try:
            dst_dir = os.path.join(ES_AI_MOD_DIR, "voice_play")
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
            base = os.path.basename(path.replace("\\", "/"))
            dst = os.path.join(dst_dir, base)
            shutil.copyfile(path, dst)
            return ES_AI_REL + "voice_play/" + base
        except Exception as e:
            es_ai_log("tts copy error: %s" % e)
            return path

    def es_ai_tts_channel():
        """Если ползунок «голос» на нуле — играем в sound, иначе тишина."""
        try:
            vol = renpy.game.preferences.volumes.get("voice")
            if vol is not None and vol < 0.02:
                return "sound"
        except Exception:
            pass
        return "es_voice"

    def es_ai_speak_async(text, char_id=None, narrator=False):
        """Озвучить текст: фоново синтезируем, playback — из главного потока.

        Нельзя Thread(..., daemon=True): это Python 3, в Ren'Py 7.4 (py2.7)
        конструктор кидает TypeError, его глотал say_girl, и очередь была пустой.
        """
        if not persistent.es_ai_tts:
            return None
        if not text:
            return None
        if len(text) > 600:
            text = text[:600]
        payload = {"text": text, "narrator": bool(narrator)}
        if char_id:
            payload["character"] = char_id

        def fn():
            r = es_ai_http("/tts", payload, timeout=60)
            if not r.get("ok"):
                raise Exception(r.get("error") or "tts")
            return r.get("path")

        job = es_ai_run_async("tts", fn)
        es_ai_tts_jobs.append(job)
        return job

    def es_ai_tts_pump():
        """Вызывается из screen-таймера (главный поток): играет очередь."""
        if es_ai_tts_jobs:
            pending = []
            for job in list(es_ai_tts_jobs):
                if not job.done:
                    pending.append(job)
                    continue
                if job.error:
                    es_ai_log("tts error: %s" % job.error)
                elif job.result:
                    es_ai_tts_queue.append(job.result)
            es_ai_tts_jobs[:] = pending
        if not es_ai_tts_queue:
            return
        try:
            import renpy.game as _rg
            if not _rg.contexts:
                return  # идёт смена контекста — аудио не трогаем
        except Exception:
            pass
        ch = es_ai_tts_channel()
        try:
            if renpy.music.is_playing(channel=ch):
                return
        except Exception:
            pass
        path = es_ai_tts_relpath(es_ai_tts_queue.pop(0))
        try:
            renpy.music.play(path, channel=ch, fadeout=0.05)
            es_ai_log("tts play %s ch=%s" % (path, ch))
        except Exception as e:
            es_ai_log("tts play error: %s" % e)

    def es_ai_tts_stop():
        try:
            del es_ai_tts_queue[:]
            renpy.music.stop(channel="es_voice")
        except Exception:
            pass

    # ------------------------------------------------- контекст новеллы ----

    es_ai_novel_context = []   # [{"who": ..., "what": ...}] — последние реплики романа

    def es_ai_push_context(who, what):
        es_ai_novel_context.append({"who": who or "", "what": what or ""})
        if len(es_ai_novel_context) > 30:
            del es_ai_novel_context[:len(es_ai_novel_context) - 30]

    def es_ai_context_snapshot():
        return list(es_ai_novel_context)

    # ------------------------------------------------- озвучка романа ------

    es_ai_internal_speaking = [False]  # защита от рекурсии say-хука
    es_ai_chat_active = [False]        # находимся в сцене AI-чата
    es_ai_last_voiced = [("", "")]     # (who, what) последней озвученной реплики

    def es_ai_on_game_say(who, what):
        """Перехват реплик новеллы: контекст + опциональная озвучка.
        Реплики без имени (нарратор/мысли Семёна) в контекст не идут —
        иначе служебные строки мода утекают нейросети."""
        if not what or not who:
            return
        try:
            es_ai_push_context(who, what)
        except Exception:
            pass
        if not persistent.es_ai_novel_voice:
            return
        if es_ai_internal_speaking[0]:
            return
        if not who:
            return
        char_id = ES_AI_NAME_TO_ID.get(who)
        if not char_id:
            return
        if es_ai_last_voiced[0] == (who, what):
            return  # дедупликация, как WasLastLlmResponse в Smart Lolis
        es_ai_last_voiced[0] = (who, what)
        try:
            es_ai_speak_async(what, char_id)
        except Exception:
            pass

    # --------------------------------------- высокоуровневые хелперы чата ----

    def es_ai_ask_girl(char_id, text):
        """Синхронный диалог с сервером. Возвращает dict {reply, emotion} или None.

        Вызывать из лейбла через $ — внутри используется renpy.pause."""
        try:
            job = es_ai_chat_async(char_id, text, es_ai_context_snapshot())
        except Exception as e:
            es_ai_log("chat async error: %s" % e)
            return None
        while not job.done:
            renpy.pause(0.05)
        if job.error is not None:
            es_ai_log("chat error: %s" % job.error)
            set_es_ai_error(job.error)
            return None
        set_es_ai_error(u"")
        return job.result

    def es_ai_initiative_girl(char_id):
        """Инициатива героини: dict или None."""
        try:
            job = es_ai_initiative_async(char_id, es_ai_context_snapshot())
        except Exception as e:
            es_ai_log("initiative error: %s" % e)
            return None
        while not job.done:
            renpy.pause(0.05)
        if job.error is not None:
            es_ai_log("initiative job error: %s" % job.error)
            set_es_ai_error(job.error)
            return None
        set_es_ai_error(u"")
        return job.result

    def es_ai_winh_dictate(max_seconds=18):
        """Диктовка Windows (Win+H) в процессе игры, чтобы фокус был у игры."""
        import ctypes
        import time
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.CreateWindowExW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetCurrentThreadId.restype = ctypes.c_uint
        user32.GetWindowThreadProcessId.restype = ctypes.c_uint
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        WS_POPUP = 0x80000000
        WS_VISIBLE = 0x10000000
        WS_CHILD = 0x40000000
        WS_EX_TOPMOST = 0x00000008
        WS_EX_TOOLWINDOW = 0x00000080
        ES_AUTOHSCROLL = 0x0080
        VK_LWIN = 0x5B
        KEYUP = 0x0002
        try:
            user32.AllowSetForegroundWindow(0xFFFFFFFF)
        except Exception:
            pass
        sw = user32.GetSystemMetrics(0)
        x = max(40, (sw - 520) // 2)
        hinst = kernel32.GetModuleHandleW(None)
        hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW, u"Static", u"Диктовка",
            WS_POPUP | WS_VISIBLE, int(x), 36, 520, 46, 0, 0, hinst, 0)
        if not hwnd:
            raise Exception(u"не удалось открыть поле диктовки")
        edit = user32.CreateWindowExW(
            0, u"Edit", u"", WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
            8, 10, 504, 26, hwnd, 0, hinst, 0)
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None)
        our_tid = kernel32.GetCurrentThreadId()
        attached = False
        try:
            if fg_tid and fg_tid != our_tid:
                attached = bool(user32.AttachThreadInput(our_tid, fg_tid, True))
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(edit or hwnd)
            time.sleep(0.12)
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(ord("H"), 0, 0, 0)
            user32.keybd_event(ord("H"), 0, KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYUP, 0)
            start = time.time()
            last_change = start
            last_text = u""
            msg = ctypes.wintypes.MSG()
            while time.time() - start < float(max_seconds or 18):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                n = user32.GetWindowTextLengthW(edit) if edit else 0
                buf = ctypes.create_unicode_buffer(max(1, n + 1))
                if edit:
                    user32.GetWindowTextW(edit, buf, n + 1)
                text = buf.value or u""
                if text != last_text:
                    last_text = text
                    last_change = time.time()
                if text.strip() and (time.time() - last_change) >= 1.6 and (time.time() - start) > 0.8:
                    return text.strip()
                time.sleep(0.05)
            return (last_text or u"").strip()
        finally:
            try:
                user32.DestroyWindow(hwnd)
            except Exception:
                pass
            if attached:
                try:
                    user32.AttachThreadInput(our_tid, fg_tid, False)
                except Exception:
                    pass
            time.sleep(0.08)
            try:
                user32.keybd_event(VK_LWIN, 0, 0, 0)
                user32.keybd_event(ord("H"), 0, 0, 0)
                user32.keybd_event(ord("H"), 0, KEYUP, 0)
                user32.keybd_event(VK_LWIN, 0, KEYUP, 0)
            except Exception:
                pass

    def es_ai_winh_girl(max_seconds=18):
        try:
            job = es_ai_run_async("winh", lambda: es_ai_winh_dictate(max_seconds))
        except Exception as e:
            es_ai_log("winh error: %s" % e)
            set_es_ai_error(str(e))
            return None
        while not job.done:
            renpy.pause(0.05)
        if job.error is not None:
            es_ai_log("winh job error: %s" % job.error)
            set_es_ai_error(job.error)
            return None
        set_es_ai_error(u"")
        return job.result or u""

    def es_ai_stt_girl(max_seconds=8):
        """Запись и распознавание речи. Win+H — диктовка Windows, не Whisper."""
        try:
            es_ai_cfg_refresh()
        except Exception:
            pass
        if (es_ai_cfg.get("stt") or {}).get("provider") == "winh":
            return es_ai_winh_girl(18)
        try:
            job = es_ai_stt_async(max_seconds)
        except Exception as e:
            es_ai_log("stt error: %s" % e)
            return None
        while not job.done:
            renpy.pause(0.05)
        if job.error is not None:
            es_ai_log("stt job error: %s" % job.error)
            set_es_ai_error(job.error)
            return None
        set_es_ai_error(u"")
        return job.result or ""

    def es_ai_say_girl(char_id, text, emotion=None, voice=True):
        """Показ реплики героини: спрайт по эмоции + текст + озвучка.

        Текст уже без эмоции в скобках; теги { } [ ] экранируются."""
        raw = (text or "").strip()
        if not raw:
            return
        ES_AI_LOC_LAST_CHAR[0] = char_id
        ES_AI_LOC_HAS_GIRL[0] = True
        if emotion:
            ES_AI_LOC_LAST_EMO[0] = emotion
        try:
            es_ai_girl_enter(char_id, emotion)
            renpy.with_statement(dissolve)
        except Exception as e:
            es_ai_log("girl enter error: %s" % e)
        if voice and persistent.es_ai_tts:
            try:
                es_ai_speak_async(raw, char_id)
            except Exception as e:
                es_ai_log("speak error: %s" % e)
        safe = es_ai_sanitize_text(raw)
        es_ai_internal_speaking[0] = True
        try:
            es_ai_speakers[char_id](safe)
        finally:
            es_ai_internal_speaking[0] = False

    # Последняя ошибка сервера для показа в диалогах (строка, не список:
    # Ren'Py-интерполяция [es_ai_last_error] в тексте)
    def set_es_ai_error(msg):
        global es_ai_last_error
        es_ai_last_error = msg or u""

    es_ai_last_error = u""

################################################################################
## Слой настроек (как SmartLolisSettings): чтение/запись конфига на сервере,
## кнопки самотестов, состояние для экрана настроек.
################################################################################

init 11 python:
    # Кэш текущего конфига (обновляется с сервера)
    es_ai_cfg = {}
    es_ai_keys = {}
    es_ai_tts_avail = {}
    es_ai_stt_avail = {}

    # Пресеты провайдеров LLM: id -> (заголовок, api_url, модель, имя ключа)
    ES_AI_LLM_PRESETS = {
        "groq":       (u"Groq (быстрый, бесплатный тариф)",
                       "https://api.groq.com/openai/v1/chat/completions",
                       "llama-3.3-70b-versatile", "groq_api_key"),
        "mistral":    (u"Mistral (работает из РФ)",
                       "https://api.mistral.ai/v1/chat/completions",
                       "mistral-small-latest", "mistral_api_key"),
        "openrouter": (u"OpenRouter (много моделей, есть бесплатные)",
                       "https://openrouter.ai/api/v1/chat/completions",
                       "meta-llama/llama-3.3-70b-instruct", "llm_api_key"),
        "openai":     (u"OpenAI (из РФ не работает!)",
                       "https://api.openai.com/v1/chat/completions",
                       "gpt-4o-mini", "openai_api_key"),
        "ollama":     (u"Ollama (локально, без ключа)",
                       "http://localhost:11434/v1/chat/completions",
                       "llama3.1:8b", ""),
        "lmstudio":   (u"LM Studio (локально, без ключа)",
                       "http://localhost:1234/v1/chat/completions",
                       "local-model", ""),
        "custom":     (u"Свой (OpenAI-совместимый)",
                       "http://127.0.0.1:8080/v1/chat/completions",
                       "model-name", "custom_llm_api_key"),
    }

    ES_AI_TTS_PROVIDERS = [
        ("auto", u"Авто (первый доступный)"),
        ("elevenlabs", u"ElevenLabs"),
        ("edge", u"edge-tts (бесплатно, интернет)"),
        ("openai", u"OpenAI TTS"),
        ("sapi", u"Windows SAPI (локально)"),
        ("off", u"Выключено"),
    ]

    ES_AI_STT_PROVIDERS = [
        ("auto", u"Авто (первый доступный)"),
        ("groq", u"Groq Whisper (облако)"),
        ("openai", u"OpenAI Whisper (облако)"),
        ("local", u"Локальный faster-whisper"),
        ("winh", u"Windows Win+H (диктовка)"),
    ]

    # Порядок кнопок провайдеров в интерфейсе
    ES_AI_LLM_PROVIDER_IDS = ["groq", "mistral", "openrouter", "openai", "ollama", "lmstudio", "custom"]

    def es_ai_open_settings_window():
        """Открыть нативное окно настроек (процесс у сервера). True — получилось."""
        try:
            r = es_ai_http("/ui/settings", {}, timeout=ES_AI_TIMEOUT_SHORT)
            return bool(r.get("ok"))
        except Exception as e:
            es_ai_log("settings window: %s" % e)
            return False

    # Состояние UI-тестов (экран настроек читает/пишет через функции ниже)
    es_ai_ui = {"job": None, "kind": "", "result": u"", "busy": False}

    def es_ai_cfg_refresh():
        try:
            r = es_ai_http("/config", timeout=ES_AI_TIMEOUT_SHORT)
            if r.get("ok"):
                es_ai_cfg.clear()
                es_ai_cfg.update(r.get("config", {}))
                es_ai_keys.clear()
                es_ai_keys.update(r.get("keys", {}))
                es_ai_tts_avail.clear()
                es_ai_tts_avail.update(r.get("tts_available", {}))
                es_ai_stt_avail.clear()
                es_ai_stt_avail.update(r.get("stt_available", {}))
        except Exception as e:
            es_ai_log("cfg refresh: %s" % e)

    def es_ai_cfg_set(section, key, value):
        try:
            es_ai_http("/config/set",
                       {"section": section, "key": key, "value": value},
                       timeout=ES_AI_TIMEOUT_SHORT)
        except Exception as e:
            es_ai_log("cfg set %s.%s: %s" % (section, key, e))
        es_ai_cfg_refresh()
        try:
            renpy.restart_interaction()
        except Exception:
            pass

    def es_ai_keys_set(name, value):
        try:
            es_ai_http("/keys/set", {"name": name, "value": value},
                       timeout=ES_AI_TIMEOUT_SHORT)
        except Exception as e:
            es_ai_log("keys set %s: %s" % (name, e))
        es_ai_cfg_refresh()

    def es_ai_pick_llm_provider(pid):
        """Выбор провайдера LLM: подставляем пресет url+модель."""
        preset = ES_AI_LLM_PRESETS.get(pid)
        if preset is None:
            return
        es_ai_cfg_set("llm", "provider", pid)
        es_ai_cfg_set("llm", "api_url", preset[1])
        es_ai_cfg_set("llm", "model", preset[2])
        es_ai_cfg_refresh()
        renpy.restart_interaction()

    def es_ai_ui_test(kind):
        """Кнопка теста: llm / tts / stt / deps. Результат — в es_ai_ui['result']."""
        if es_ai_ui["busy"]:
            return
        es_ai_ui["busy"] = True
        es_ai_ui["kind"] = kind
        es_ai_ui["result"] = u"..."
        es_ai_ui["job"] = None

        if kind == "llm":
            def fn():
                return es_ai_http("/test/llm", {}, timeout=ES_AI_TIMEOUT_LONG)
        elif kind == "tts":
            payload = {"character": persistent.es_ai_last_char or "un"}

            def fn():
                return es_ai_http("/test/tts", payload, timeout=ES_AI_TIMEOUT_LONG)
        elif kind == "stt":
            payload = {"max_seconds": 3}

            def fn():
                return es_ai_http("/test/stt", payload, timeout=ES_AI_TIMEOUT_LONG)
        else:  # deps
            def fn():
                return es_ai_http("/deps/install", {}, timeout=300)

        es_ai_ui["job"] = es_ai_run_async("test_" + kind, fn)

    def es_ai_ui_poll():
        """Тик из экрана (главный поток): забрать результат теста."""
        job = es_ai_ui.get("job")
        if job is None or not job.done:
            return
        es_ai_ui["job"] = None
        kind = es_ai_ui.get("kind", "")
        r = job.result
        if job.error is not None:
            es_ai_ui["result"] = u"Ошибка: %s" % job.error
            es_ai_ui["busy"] = False
            renpy.restart_interaction()
            return

        if kind == "llm":
            if r.get("ok"):
                es_ai_ui["result"] = u"LLM отвечает (%s мс): «%s»" % (r.get("latency_ms"), r.get("preview", ""))
            else:
                es_ai_ui["result"] = u"LLM не ответил: %s" % r.get("error", "")
        elif kind == "tts":
            if r.get("ok"):
                es_ai_ui["result"] = u"Голос готов (%s), играю..." % r.get("provider", "")
                try:
                    renpy.music.play(es_ai_tts_relpath(r.get("path")), channel=es_ai_tts_channel(), fadeout=0.1)
                except Exception as e:
                    es_ai_log("test tts play: %s" % e)
            else:
                es_ai_ui["result"] = u"TTS не сработал: %s" % r.get("error", "")
        elif kind == "stt":
            if r.get("ok"):
                es_ai_ui["result"] = u"Распознано (%s): «%s»" % (r.get("provider", ""), r.get("text", ""))
            else:
                es_ai_ui["result"] = u"Микрофон/STT не сработал: %s" % r.get("error", "")
        else:  # deps
            if r.get("ok"):
                es_ai_ui["result"] = u"Компоненты установлены. TTS: %s | микрофон: %s" % (
                    "да" if r.get("tts_available", {}).get("edge") else "нет",
                    "да" if r.get("stt_available", {}).get("record") else "нет")
            else:
                es_ai_ui["result"] = u"Установка не удалась: %s" % r.get("error", "")
        es_ai_ui["busy"] = False
        es_ai_cfg_refresh()
        renpy.restart_interaction()

    def es_ai_key_display(name):
        """Строка для показа ключа: (не задан) / ••••abcd"""
        info = es_ai_keys.get(name, {})
        if not info.get("present"):
            return u"(не задан)"
        return u"\u2022\u2022\u2022\u2022" + (info.get("tail") or "")


