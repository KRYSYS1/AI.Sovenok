"""Pure activity decisions. No wall clock, persistence, network or model calls."""
import json

HOMES = {"mz": "sl_room", "sl": "sl_room", "un": "un_room", "mi": "un_room",
         "dv": "dv_room", "us": "dv_room", "mt": "mt_room"}


def schedule(cid, clock=None):
    clock = clock if isinstance(clock, dict) else {}
    phase = clock.get("phase", "day")
    if clock.get("enabled") is True:
        try:
            hour, minute = map(int, clock.get("time", "").split(":"))
            if 0 <= hour < 24 and 0 <= minute < 60:
                phase = "morning" if 6 <= hour < 10 else "day" if 10 <= hour < 18 else "sunset" if 18 <= hour < 22 else "night"
        except (ValueError, TypeError, AttributeError):
            pass
    location, task, busy, eta = "square", "walking", False, 1
    if cid == "cs":
        location, task, busy, eta = "aidpost_inside", "medical_duty", True, 3
    elif phase == "night" and cid in HOMES:
        location, task, busy, eta = HOMES[cid], "resting", True, 3
    elif cid == "mi" and phase == "day":
        location, task, busy, eta = "musclub_inside", "rehearsal", True, 2
    elif cid == "mi" and phase == "sunset":
        location, task, busy, eta = "stage", "concert_preparation", True, 2
    elif cid == "mz" and phase in ("morning", "day"):
        location, task, busy, eta = "library", "reading", True, 2
    elif cid in ("el", "sh") and phase == "day":
        location, task, busy, eta = "club_room", "club_work", True, 2
    elif cid == "mt" and phase in ("morning", "day"):
        location, task, busy, eta = "mt_room", "camp_work", True, 2
    elif cid == "un" and phase == "day":
        location, task = "polyana", "drawing"
    elif cid == "sl" and phase == "morning":
        location, task, busy, eta = "dining", "camp_help", True, 2
    elif cid == "dv" and phase == "day":
        location, task = "beach", "resting"
    elif cid == "us" and phase == "day":
        location, task = "playground", "playing"
    elif cid == "uv":
        location, task = "old_building", "walking"
    return dict(location=location, task=task, status="busy" if busy else "available", eta_turns=eta)


def authoritative(scene, clock=None, enabled=True):
    """Only new free-scene clients opt in; actual local/parked presence wins."""
    if not isinstance(scene, dict):
        return scene
    scene = dict(scene)
    scene["npc_activity_enabled"] = enabled is True
    if enabled is not True:
        scene["activity"] = {}
        scene["pending_calls"] = {}
        return scene
    if scene.get("enabled") is not True or not isinstance(scene.get("activity"), dict):
        return scene
    origin = scene.get("location_id")
    activity = {cid: schedule(cid, clock) for cid in scene["activity"] if isinstance(cid, str)}
    records = scene.get("destination_nearby", {})
    if isinstance(records, dict):
        for loc, ids in records.items():
            if isinstance(ids, list):
                for cid in ids:
                    if cid in activity:
                        activity[cid] = dict(location=loc, task="local_business", status="busy", eta_turns=2, recorded=True)
    for cid in scene.get("present", []) + scene.get("nearby", []):
        if cid in activity:
            activity[cid] = dict(location=origin, task="present", status="available", eta_turns=0, recorded=True)
    for cid in scene.get("absent", []):
        if cid in activity and activity[cid].get("location") == origin and cid not in scene.get("present", []) + scene.get("nearby", []):
            activity[cid] = dict(location=None, task="away", status="busy", eta_turns=2, recorded=True)
    scene["activity"] = activity
    return scene


def decide(ids, scene, destination=None):
    """Return eligible ready IDs and explicit call outcomes, without claiming arrival."""
    if not isinstance(scene, dict) or scene.get("npc_activity_enabled", True) is not True or scene.get("enabled") is not True or not isinstance(scene.get("activity"), dict):
        return ids, []
    location = destination or scene.get("location_id")
    pending = scene.get("pending_calls", {})
    pending = pending if isinstance(pending, dict) else {}
    ready, calls = [], []
    for cid in dict.fromkeys(ids):
        state = scene["activity"].get(cid)
        if not isinstance(state, dict):
            ready.append(cid)
            continue
        wait = state.get("eta_turns", 1)
        wait = min(3, max(1, wait)) if type(wait) is int else 1
        status, reason = "pending", state.get("task", "walking")
        old = pending.get(cid)
        if cid in scene.get("present", []) or (not destination and cid in scene.get("nearby", [])) or state.get("location") == location:
            status, wait = "ready", 0
        elif cid == "cs" or reason == "medical_duty":
            reason = "medical_duty"
            status, wait = "refused", 0
        elif isinstance(old, dict) and old.get("location_id") == location:
            wait = old.get("wait_turns", wait)
            wait = min(3, max(0, wait)) if type(wait) is int else 1
            if wait == 0:
                status = "ready"
        if status == "ready":
            ready.append(cid)
        calls.append(dict(id=cid, status=status, reason=reason, wait_turns=wait,
                          location_id=location))
    return ready, calls


def prompt(scene):
    if not isinstance(scene, dict) or scene.get("npc_activity_enabled", True) is not True or not isinstance(scene.get("activity"), dict):
        return ""
    return ("\nAUTHORITATIVE NPC ACTIVITY: " + json.dumps(scene["activity"], ensure_ascii=True) +
            "\nSchedules describe whereabouts, NOT scene presence. Actual present/nearby rosters win. "
            "Nonlocal invitations require waiting; medical duty cannot leave its post. Never describe "
            "a pending/refused NPC as present, speaking, promising or following. Use only your own speech. "
            "Pending calls: " + json.dumps(scene.get("pending_calls", {}), ensure_ascii=True))
