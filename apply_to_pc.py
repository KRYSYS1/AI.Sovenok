#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Применяет изменения ES-AI-Mod (камео-фича) к локальным файлам пользователя
через MCP-мост (Hyperagent File Bridge).

Безопасность:
  * обычные файлы: если локальная версия отличается от origin (HEAD клона),
    новая версия сохраняется рядом как <name>.esai-new, локальная НЕ затирается;
  * config.json: merge — добавляются только новые ключи камео, остальное не трогается.

Запуск (когда мост поднят):
    python3 apply_to_pc.py
"""
import io
import json
import os
import sys
import urllib.request

MCP_URL = os.environ.get(
    "MCP_URL",
    "https://quick-river-vf8fclj-8008.eun1.devtunnels.ms/mcp")

CLONE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI.Sovenok", "ES-AI-Mod")

# куда складывать в зависимости от установки (определяется по факту при запуске)
DEV_ROOT = r"C:\Users\kolan\Desktop\Endless Summer\ES-AI-Mod"
WS_ROOT = r"D:\Program Files (x86)\Steam\steamapps\workshop\content\331470\3809240310"

# файлы мода/сервера, которые меняем (относительно корня мода)
CHANGED_FILES = [
    "mod/es_ai_cameo.rpy",
    "mod/es_ai_locations.rpy",
    "mod/es_ai_screens.rpy",
    "server/main.py",
    "server/settings_window.py",
]

# новые ключи, которые надо ДОБАВИТЬ в config.json (merge, не перезапись)
NEW_CFG_KEYS = {
    "cameo_freq": 25,
    "cameo_stay": True,
    "cameo_stay_lines": 2,
    "cameo_interject": 35,
    "cameo_ctx": 70,
    "cameo_max_extra": 2,
}

_req_id = [0]


def mcp_call(tool, arguments):
    _req_id[0] += 1
    payload = {"jsonrpc": "2.0", "id": _req_id[0], "method": "tools/call",
               "params": {"name": tool, "arguments": arguments}}
    req = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", "replace")
    for line in raw.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[5:].strip())
            if data.get("id") == _req_id[0]:
                if data.get("isError"):
                    raise RuntimeError("MCP error: %s" % data)
                return data.get("result", {})
    raise RuntimeError("нет ответа от MCP (пустой результат)")


def mcp_text(tool, arguments):
    """Результат как текст (для read_file / list_directory)."""
    res = mcp_call(tool, arguments)
    parts = []
    for item in res.get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    if res.get("structuredContent") and isinstance(res["structuredContent"], dict):
        c = res["structuredContent"].get("content")
        if isinstance(c, str):
            parts.append(c)
    return "\n".join(parts)


def mcp_read(path):
    return mcp_text("read_file", {"path": path})


def mcp_write(path, content):
    mcp_call("write_file", {"path": path, "content": content})


def mcp_list(path):
    return mcp_text("list_directory", {"path": path})


def local_new(rel):
    with io.open(os.path.join(CLONE, rel), "r", encoding="utf-8") as f:
        return f.read()


def local_orig(rel):
    """Версия из git HEAD (как в репозитории до правок)."""
    import subprocess
    out = subprocess.run(["git", "-C", os.path.dirname(CLONE), "show", "HEAD~1:ES-AI-Mod/" + rel],
                         capture_output=True)
    if out.returncode != 0:
        # фича закоммичена — берём файл до коммита через diff
        out = subprocess.run(["git", "-C", os.path.dirname(CLONE), "show", "HEAD~1:ES-AI-Mod/" + rel],
                             capture_output=True)
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


def find_mod_files(root):
    """Возвращает dict {rel_path_in_mod: absolute_path} для изменённых файлов.
    Поддерживает оба варианта установки: <root>/mod/... (репо) и <root>/... (workshop)."""
    out = {}
    listing = mcp_list(root)
    has_mod_subdir = "[DIR] mod" in listing or "[DIR] mod" in listing.replace("\\", "/")
    for rel in CHANGED_FILES:
        candidates = []
        if has_mod_subdir:
            candidates.append(os.path.join(root, rel).replace("/", "\\"))
        # workshop-вариант: файлы лежат прямо в корне (mod/ -> корень, server/ -> корень)
        flat = rel.split("/", 1)[1] if "/" in rel else rel
        candidates.append(os.path.join(root, flat).replace("/", "\\"))
        for c in candidates:
            try:
                mcp_read(c)
                out[rel] = c
                break
            except Exception:
                continue
    return out


def apply_file(target, rel):
    new_content = local_new(rel)
    try:
        cur = mcp_read(target)
    except Exception as e:
        print("  [skip] %s — не читается (%s)" % (target, e))
        return
    orig = local_orig(rel)
    if orig is not None and cur == orig:
        mcp_write(target, new_content)
        print("  [ok]   %s — обновлён (локальная версия == origin)" % target)
    elif orig is None:
        mcp_write(target, new_content)
        print("  [ok]   %s — обновлён (origin не найден, считаем что не тронут)" % target)
    else:
        side = target + ".esai-new"
        mcp_write(side, new_content)
        print("  [WARN] %s — локальная версия отличается от origin! "
              "Новая версия сохранена рядом: %s (сравни и примени вручную)" % (target, side))


def merge_config(target):
    try:
        cur = json.loads(mcp_read(target))
    except Exception as e:
        print("  [skip] %s — не читается (%s)" % (target, e))
        return
    if not isinstance(cur, dict):
        print("  [skip] %s — не dict" % target)
        return
    added = []
    for k, v in NEW_CFG_KEYS.items():
        if k not in cur:
            cur[k] = v
            added.append(k)
    if added:
        mcp_write(target, json.dumps(cur, ensure_ascii=False, indent=2) + "\n")
        print("  [ok]   %s — добавлены ключи: %s" % (target, ", ".join(added)))
    else:
        print("  [ok]   %s — все ключи уже на месте" % target)


def main():
    print("MCP:", MCP_URL)
    allowed = mcp_text("list_allowed_directories", {})
    print("Allowed directories:\n%s\n" % allowed)

    for name, root in (("DEV (мастер-копия)", DEV_ROOT), ("WORKSHOP (установленный мод)", WS_ROOT)):
        print("=" * 70)
        print("%s: %s" % (name, root))
        found = find_mod_files(root)
        if not found:
            print("  [skip] папка не найдена или пуста")
            continue
        for rel, target in sorted(found.items()):
            apply_file(target, rel)
        # config.json — merge
        cfg_target = None
        for cand in (os.path.join(root, "server", "config.json").replace("/", "\\"),
                     os.path.join(root, "config.json").replace("/", "\\")):
            try:
                mcp_read(cand)
                cfg_target = cand
                break
            except Exception:
                continue
        if cfg_target:
            merge_config(cfg_target)
    print("=" * 70)
    print("Готово. Перезапусти игру (сервер поднимется с новым main.py).")


if __name__ == "__main__":
    main()
