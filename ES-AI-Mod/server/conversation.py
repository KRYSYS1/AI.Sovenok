# -*- coding: utf-8 -*-
"""История разговоров по персонажам, персистентность и LLM-сжатие памяти.

Порт схемы kcd2-ai-npc (conversation.py): скользящее окно + суммаризация старых
сообщений лёгким LLM-запросом в compressed_summary.
"""
import json
import os
import threading

lock = threading.Lock()

# char_id -> {"messages": [{"role": ..., "content": ...}], "summary": str}
conversations = {}


def _dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "conversations")


def _path(char_id):
    safe = "".join(c for c in char_id if c.isalnum() or c in "-_")
    return os.path.join(_dir(), "%s.json" % safe)


def load():
    if not os.path.isdir(_dir()):
        return
    for fn in os.listdir(_dir()):
        if not fn.endswith(".json"):
            continue
        char_id = fn[:-5]
        try:
            with open(_path(char_id), "r", encoding="utf-8") as f:
                conversations[char_id] = json.load(f)
        except Exception:
            pass


def _persist(char_id):
    try:
        os.makedirs(_dir(), exist_ok=True)
        with open(_path(char_id), "w", encoding="utf-8") as f:
            json.dump(conversations.get(char_id, {}), f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def get_history(char_id):
    with lock:
        conv = conversations.get(char_id, {})
        return list(conv.get("messages", [])), conv.get("summary", "")


def set_summary(char_id, summary):
    """Ручная правка выжимки из вкладки «История». Полный лог не трогаем."""
    with lock:
        conv = conversations.setdefault(char_id, {"messages": [], "summary": ""})
        conv["summary"] = (summary or "").strip()
        _persist(char_id)
        return conv["summary"]


def add_exchange(char_id, user_text, assistant_text):
    with lock:
        conv = conversations.setdefault(char_id, {"messages": [], "summary": ""})
        conv["messages"].append({"role": "user", "content": user_text})
        conv["messages"].append({"role": "assistant", "content": assistant_text})
        _persist(char_id)


def clear(char_id):
    with lock:
        conversations[char_id] = {"messages": [], "summary": ""}
        _persist(char_id)


def _format_for_summary(messages, old_summary, player_name="Семён"):
    lines = []
    if old_summary:
        lines.append("Что уже было в памяти: " + old_summary)
    for m in messages:
        who = player_name if m.get("role") == "user" else "Персонаж"
        lines.append("%s: %s" % (who, m.get("content") or ""))
    return "\n".join(lines)


def maybe_compress(char_id, cfg, llm_chat_fn, force=False):
    """Старые реплики сжимаются в summary. Полный лог остаётся для вкладки «История».

    В нейронку уходит только summary + короткий хвост, не вся переписка.
    llm_chat_fn(text) -> str.
    """
    hcfg = cfg.get("history", {})
    threshold = int(hcfg.get("compress_threshold", 16))
    keep_recent = int(hcfg.get("keep_recent", 6))

    with lock:
        conv = conversations.get(char_id)
        if not conv:
            return False
        msgs = list(conv.get("messages", []))
        done = int(conv.get("summarized_count") or 0)
        pending_end = max(0, len(msgs) - keep_recent)
        if force and (pending_end <= done or not msgs[done:pending_end]):
            chunk = msgs
            pending_end = max(done, len(msgs) - keep_recent)
        else:
            if not force and pending_end - done < max(2, threshold - keep_recent):
                return False
            if pending_end <= done:
                return False
            chunk = msgs[done:pending_end]
        if not chunk:
            return False
        old_summary = conv.get("summary", "")

    text = _format_for_summary(chunk, old_summary)
    try:
        summary = llm_chat_fn(text).strip()
    except Exception:
        return False
    if not summary:
        return False

    with lock:
        conv = conversations.get(char_id, {"messages": []})
        # Не выкидываем реплики: вкладка «История» читает полный лог.
        conv["summary"] = summary
        conv["summarized_count"] = pending_end
        _persist(char_id)
    return True


def build_history_block(char_id, cfg, novel_context=None, novel_who="", location=""):
    """Собирает messages для LLM: system-промпт персонажа + summary + окно истории."""
    hcfg = cfg.get("history", {})
    max_messages = int(hcfg.get("max_messages", 16))

    hist, summary = get_history(char_id)
    keep_recent = int(hcfg.get("keep_recent", 6))
    # Выжимка уже покрывает старое. В модель — только короткий хвост, не весь архив.
    window = hist[-(keep_recent if summary else max_messages):]

    sys_prompt = build_system_prompt(char_id, novel_context, novel_who, summary, location)
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(window)
    return messages


def build_system_prompt(char_id, novel_context=None, novel_who="", summary="", location=""):
    from characters_store import get_character, reply_rules, player_block
    ch = get_character(char_id)
    parts = [ch["persona"], ch["speech"], reply_rules(ch)]
    pb = player_block()
    if pb:
        parts.append(pb)
    if location:
        parts.append("Текущее место действия (где вы сейчас): " + location + ". Не противоречь этой локации в описаниях и репликах.")
    if summary:
        parts.append("Память о прошлых разговорах:\n" + summary)
    if novel_context:
        lines = []
        for item in novel_context:
            who = item.get("who") or ""
            what = (item.get("what") or "").strip()
            if what:
                lines.append("%s: %s" % (who or "...", what))
        if lines:
            parts.append(
                "Сейчас идёт игра: это последние события новеллы «Бесконечное лето».\n"
                + "\n".join(lines)
            )
    if novel_who:
        parts.append("С тобой сейчас говорит: %s." % novel_who)
    return "\n\n".join(parts)
