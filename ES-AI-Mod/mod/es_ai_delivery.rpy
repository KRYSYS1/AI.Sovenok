# -*- coding: utf-8 -*-
# Event-driven delivery. Backend state is outside Ren'Py's rollback store.
init 12 python:
    import sys as _delivery_sys
    import types as _delivery_types
    import threading as _delivery_threading
    import json as _delivery_json
    import os as _delivery_os
    import tempfile as _delivery_tempfile
    try:
        import __builtin__ as _delivery_builtins
    except ImportError:
        import builtins as _delivery_builtins

    if "_es_ai_delivery_backend" not in _delivery_sys.modules:
        _delivery_backend = _delivery_types.ModuleType(_delivery_builtins.str("_es_ai_delivery_backend"))
        _delivery_backend.lock = _delivery_threading.RLock()
        _delivery_backend.loaded = False
        _delivery_backend.running = False
        _delivery_backend.data = _delivery_builtins.dict(version=1, public_events=[], story_acks=[])
        _delivery_backend.retired = set()
        _delivery_sys.modules[_delivery_backend.__name__] = _delivery_backend
    else:
        _delivery_backend = _delivery_sys.modules["_es_ai_delivery_backend"]

    def es_ai_delivery_path():
        base = _delivery_os.environ.get("LOCALAPPDATA")
        if not base:
            base = _delivery_os.path.join(_delivery_os.path.expanduser("~"), "AppData", "Local")
        return _delivery_os.path.join(base, "AI.Sovenok", "delivery_outbox.json")

    def _es_ai_delivery_key(kind, value):
        if kind == "public_events":
            return (kind, value.get("id"))
        return (kind, value.get("token"), value.get("delivery_id"))

    def _es_ai_delivery_load():
        backend = _delivery_backend
        if backend.loaded:
            return
        path = es_ai_delivery_path()
        if _delivery_os.path.exists(path):
            with open(path, "rb") as stream:
                data = _delivery_json.loads(stream.read().decode("utf-8"))
            if not isinstance(data, _delivery_builtins.dict) or data.get("version") != 1:
                raise ValueError("unsupported delivery outbox version")
            if not _delivery_builtins.all(isinstance(data.get(k), _delivery_builtins.list) for k in ("public_events", "story_acks")):
                raise ValueError("invalid delivery outbox")
            backend.data = data
        backend.loaded = True

    def _es_ai_delivery_save(data):
        path = es_ai_delivery_path()
        directory = _delivery_os.path.dirname(path)
        if not _delivery_os.path.isdir(directory):
            _delivery_os.makedirs(directory)
        fd, temporary = _delivery_tempfile.mkstemp(prefix=".delivery-", dir=directory)
        try:
            with _delivery_os.fdopen(fd, "wb") as stream:
                stream.write(_delivery_json.dumps(data, ensure_ascii=True).encode("utf-8"))
                stream.flush()
                _delivery_os.fsync(stream.fileno())
            if _delivery_os.name == "nt":
                # Python 2 os.rename cannot replace an existing Windows file.
                import ctypes
                move = ctypes.windll.kernel32.MoveFileExW
                move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                move.restype = ctypes.c_int
                if not move(unicode(temporary), unicode(path), 0x1 | 0x8):
                    raise ctypes.WinError()
            else:
                _delivery_os.rename(temporary, path)
        finally:
            if _delivery_os.path.exists(temporary):
                _delivery_os.unlink(temporary)

    def _es_ai_delivery_send():
        backend = _delivery_backend
        owner = backend.running
        try:
            while True:
                with backend.lock:
                    payload = _delivery_builtins.dict(public_events=backend.data["public_events"][:40],
                                   story_acks=backend.data["story_acks"][:30])
                    if not any(payload.values()):
                        backend.running = False
                        return
                result = es_ai_http("/scene/flush", payload, timeout=2)
                if not result.get("ok"):
                    return
                retired = set(("public_events", eid) for eid in result.get("public_event_ids", []))
                retired.update(_es_ai_delivery_key("story_acks", ack) for ack in result.get("story_acks", []))
                sent = set(_es_ai_delivery_key(k, v) for k in payload for v in payload[k])
                retired.intersection_update(sent)
                if not retired:
                    return
                with backend.lock:
                    updated = _delivery_builtins.dict(version=1)
                    for kind in ("public_events", "story_acks"):
                        updated[kind] = [v for v in backend.data[kind]
                                         if _es_ai_delivery_key(kind, v) not in retired]
                    _es_ai_delivery_save(updated)
                    backend.data = updated
                    backend.retired.update(retired)
        except Exception as e:
            es_ai_log("delivery retained: %s" % e)
        finally:
            with backend.lock:
                if backend.running is owner:
                    backend.running = False

    def es_ai_delivery_flush(send=True):
        """Main-thread snapshot and durable save BEFORE starting any network work."""
        backend = _delivery_backend
        try:
            snapshots = _delivery_builtins.dict(public_events=es_ai_public_snapshot(), story_acks=es_ai_story_ack_snapshot())
            # JSON roundtrip detaches nested Ren'Py rollback containers.
            snapshots = _delivery_json.loads(_delivery_json.dumps(snapshots))
            with backend.lock:
                _es_ai_delivery_load()
                updated = _delivery_builtins.dict(version=1)
                for kind in ("public_events", "story_acks"):
                    values = _delivery_builtins.list(backend.data[kind])
                    seen = set(_es_ai_delivery_key(kind, v) for v in values)
                    for value in snapshots[kind]:
                        key = _es_ai_delivery_key(kind, value)
                        if key not in seen and key not in backend.retired:
                            values.append(value)
                            seen.add(key)
                    updated[kind] = values
                _es_ai_delivery_save(updated)
                backend.data = updated
                if not send or backend.running or not (updated["public_events"] or updated["story_acks"]):
                    return
                backend.running = object()
                try:
                    es_ai_run_async("delivery", _es_ai_delivery_send)
                except Exception:
                    backend.running = False
                    raise
        except Exception as e:
            es_ai_log("delivery snapshot failed: %s" % e)

    def es_ai_delivery_say(speaker, text, speaker_id, raw, story_ack=None, choices=None):
        """Ren'Py 7.4: show_done follows text validation, precedes ui.interact."""
        original = speaker.display_args.get("callback")
        if original is None:
            original = getattr(config, "character_callback", None)
        callbacks = (_delivery_builtins.list(original) if isinstance(original, _delivery_builtins.list)
                     else ([original] if original is not None else []))
        recorded = [False]

        def displayed(event, **kwargs):
            if event == "show_done" and not recorded[0]:
                recorded[0] = True
                es_ai_public_record(speaker_id, raw)
                es_ai_story_ack_record(story_ack)
                if choices is not None:
                    es_ai_story_choices_record(choices)
                ES_AI_CLOCK["lines"] += 1
                es_ai_delivery_flush(send=False)
            for callback in callbacks:
                callback(event, **kwargs)

        # Character(kind=self, **kwargs) clones properties; never mutate the speaker.
        return speaker(text, callback=displayed)

    # Preserve other quit callbacks. No HTTP or disk I/O merely from loading the mod.
    if hasattr(config, "quit_callbacks") and es_ai_delivery_flush not in config.quit_callbacks:
        config.quit_callbacks.append(es_ai_delivery_flush)
