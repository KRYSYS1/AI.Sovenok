# -*- coding: utf-8 -*-
"""Конфиг и ключи: config.json (настройки) + keys.json (секреты), как в kcd2-ai-npc."""
import json
import os
import threading
import urllib.parse

_DIR = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()

cfg = {}
keys = {}


def normalize_llm_urls(config):
    """Migrate only terminal chat paths, preserving query strings and other URLs."""
    llm = config.get("llm", {})
    if not isinstance(llm, dict):
        return
    for name in ("api_url", "custom_api_url"):
        value = llm.get(name)
        if not isinstance(value, str):
            continue
        try:
            parts = urllib.parse.urlsplit(value.strip())
        except ValueError:
            continue
        path = parts.path.rstrip("/")
        if path.endswith("/chat/completions"):
            path = path[:-len("/chat/completions")]
            llm[name] = urllib.parse.urlunsplit(parts._replace(path=path))


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
    normalize_llm_urls(new_cfg)
    new_keys = _read(os.path.join(_DIR, "keys.json"), {})
    with _lock:
        cfg.clear()
        cfg.update(new_cfg)
        keys.clear()
        keys.update(new_keys)
    return cfg


def save_config():
    with _lock:
        normalize_llm_urls(cfg)
        path = os.path.join(_DIR, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def save_keys():
    with _lock:
        path = os.path.join(_DIR, "keys.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)


reload_all()
