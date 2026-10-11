# -*- coding: utf-8 -*-
init -10 python:
    ES_AI_ACTIVITY_PENDING = {}

init 10 python:
    def es_ai_activity_enabled():
        enabled = es_ai_read_cameo_settings().get("npc_activity_enabled", True) is True
        if not enabled:
            ES_AI_ACTIVITY_PENDING.clear()
        return enabled

    def es_ai_activity_schedule(cid):
        phase = ES_AI_TIME[0]
        if ES_AI_CLOCK.get("enabled") and ES_AI_CLOCK.get("minutes") is not None:
            phase = es_ai_clock_phase(ES_AI_CLOCK["minutes"])
        homes = {"mz": "sl_room", "sl": "sl_room", "un": "un_room", "mi": "un_room",
                 "dv": "dv_room", "us": "dv_room", "mt": "mt_room"}
        loc, task, busy, eta = "square", "walking", False, 1
        if cid == "cs":
            loc, task, busy, eta = "aidpost_inside", "medical_duty", True, 3
        elif phase == "night" and cid in homes:
            loc, task, busy, eta = homes[cid], "resting", True, 3
        elif cid == "mi" and phase == "day":
            loc, task, busy, eta = "musclub_inside", "rehearsal", True, 2
        elif cid == "mi" and phase == "sunset":
            loc, task, busy, eta = "stage", "concert_preparation", True, 2
        elif cid == "mz" and phase in ("morning", "day"):
            loc, task, busy, eta = "library", "reading", True, 2
        elif cid in ("el", "sh") and phase == "day":
            loc, task, busy, eta = "club_room", "club_work", True, 2
        elif cid == "mt" and phase in ("morning", "day"):
            loc, task, busy, eta = "mt_room", "camp_work", True, 2
        elif cid == "un" and phase == "day":
            loc, task = "polyana", "drawing"
        elif cid == "sl" and phase == "morning":
            loc, task, busy, eta = "dining", "camp_help", True, 2
        elif cid == "dv" and phase == "day":
            loc, task = "beach", "resting"
        elif cid == "us" and phase == "day":
            loc, task = "playground", "playing"
        elif cid == "uv":
            loc, task = "old_building", "walking"
        return dict(location=loc, task=task, status="busy" if busy else "available", eta_turns=eta)

    def es_ai_activity_snapshot():
        if not es_ai_activity_enabled():
            return {}
        result = {cid: es_ai_activity_schedule(cid) for cid, _name, _color in ES_AI_CHARS}
        for loc, records in ES_AI_CAMEO_NEARBY.items():
            for record in records:
                cid = record["id"]
                result[cid] = dict(location=loc, task="local_business", status="busy", eta_turns=2, recorded=True)
        for record in ES_AI_SHOWN:
            result[record["id"]] = dict(location=ES_AI_LOC_CUR[0], task="present", status="available", eta_turns=0, recorded=True)
        return result

    def es_ai_activity_bias(cid):
        if not es_ai_activity_enabled():
            return 1.0
        state = es_ai_activity_snapshot().get(cid, {})
        if cid in ES_AI_ACTIVITY_PENDING:
            return 0.0
        if state.get("location") == ES_AI_LOC_CUR[0]:
            return 1.0
        if state.get("recorded") or state.get("status") == "busy":
            return 0.0
        return 0.35

    def es_ai_activity_notice(call):
        tasks = {"rehearsal": u"занята репетицией", "concert_preparation": u"готовится к концерту",
                 "reading": u"читает в библиотеке", "medical_duty": u"дежурит в медпункте",
                 "resting": u"отдыхает", "club_work": u"занят делами кружка",
                 "camp_work": u"занята делами лагеря", "camp_help": u"помогает в лагере",
                 "local_business": u"занимается своими делами", "drawing": u"рисует",
                 "playing": u"играет", "walking": u"находится в другом месте"}
        text = u"%s %s; " % (es_ai_cameo_name(call["id"]), tasks.get(call.get("reason"), u"занимается своими делами"))
        text += (u"не может оставить дежурство. Можно зайти в медпункт." if call["status"] == "refused"
                 else u"появление здесь возможно через %s обмена, если вы останетесь на месте." % call["wait_turns"])
        es_ai_recent_push("Narrator", text)
        es_ai_internal_speaking[0] = True
        try:
            renpy.say(None, es_ai_sanitize_text(text))
        finally:
            es_ai_internal_speaking[0] = False

    def es_ai_activity_exchange(res):
        """One tick per successful exchange, never per sprite line or arrival event."""
        if not es_ai_activity_enabled():
            return []
        if res.get("ok") is False:
            return []
        local = set(g["id"] for g in ES_AI_SHOWN)
        for cid in _es_ai_cameo_builtins.list(ES_AI_ACTIVITY_PENDING):
            old = ES_AI_ACTIVITY_PENDING[cid]
            if old["location_id"] != ES_AI_LOC_CUR[0] or cid in local:
                del ES_AI_ACTIVITY_PENDING[cid]
            else:
                old["wait_turns"] = _es_ai_cameo_builtins.max(0, old["wait_turns"] - 1)
        calls = res.get("npc_calls", [])
        known = set(c[0] for c in ES_AI_CHARS)
        if isinstance(calls, (_es_ai_cameo_builtins.list, _es_ai_cameo_builtins.tuple)):
            for call in calls[:6]:
                if not isinstance(call, _es_ai_cameo_builtins.dict) or call.get("id") not in known:
                    continue
                cid = call["id"]
                if call.get("location_id") != ES_AI_LOC_CUR[0] or cid in local:
                    continue
                if call.get("status") == "refused":
                    ES_AI_ACTIVITY_PENDING.pop(cid, None)
                    es_ai_activity_notice(call)
                elif call.get("status") == "pending" and cid not in ES_AI_ACTIVITY_PENDING:
                    wait = call.get("wait_turns")
                    if type(wait) is not _es_ai_cameo_builtins.int or not 1 <= wait <= 3:
                        continue
                    ES_AI_ACTIVITY_PENDING[cid] = dict(call, replace=res.get("cameo_replace") is True)
                    es_ai_activity_notice(call)
        return [cid for cid, call in ES_AI_ACTIVITY_PENDING.items() if call["wait_turns"] == 0]
