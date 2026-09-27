# -*- coding: utf-8 -*-
"""Конфиг и ключи: config.json (настройки) + keys.json (секреты), как в kcd2-ai-npc."""
import json
import os
import threading

_DIR = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()

cfg = {}
keys = {}


def _read(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("CONFIG WARN: %s: %s" % (path, e))
    return default


def reload_all():
    """In-place обновление: все модули, сделавшие from config_loader import cfg,
    продолжают видеть один и тот же dict-объект."""
    global cfg, keys
    new_cfg = _read(os.path.join(_DIR, "config.json"), {})
    new_keys = _read(os.path.join(_DIR, "keys.json"), {})
    with _lock:
        cfg.clear()
        cfg.update(new_cfg)
        keys.clear()
        keys.update(new_keys)
    return cfg


def save_config():
    with _lock:
        path = os.path.join(_DIR, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def save_keys():
    with _lock:
        path = os.path.join(_DIR, "keys.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)


reload_all()
