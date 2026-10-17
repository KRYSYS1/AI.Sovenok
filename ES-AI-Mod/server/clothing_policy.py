# -*- coding: utf-8 -*-
"""Non-explicit costume authorization and bounded, ephemeral episode hints."""
import re
import random
import threading

_episodes = {}
_episode_lock = threading.Lock()


def attire_prompt(scene):
    outfits = scene.get("outfits") if isinstance(scene, dict) else None
    if not isinstance(outfits, dict):
        return ""
    actual = {cid: dress for cid, dress in outfits.items()
              if isinstance(cid, str) and re.fullmatch(r"[a-z]{2}", cid)
              and dress in ("pioneer", "pioneer2", "swim", "sport", "dress", "panama", "ordinary", "unknown")}
    import json
    return ("\nAUTHORITATIVE RENDERED OUTFITS at snapshot location %s: %s. "
            "These are actual current visuals, not proposed changes; override stale history/persona clothing. "
            "Unknown means unavailable, never assume uniform. A pending goto does not establish destination attire. "
            "Swimsuits are ordinary nonsexual clothing, never consent to intimacy. No nudity or sexual acts."
            % (scene.get("location_id", "unknown"), json.dumps(actual, sort_keys=True)))


def romantic_preference(cid, age, player, scene):
    """One draw before generation; two neutral player turns end the episode."""
    eligible = adult_romance_allowed(cid, age) and private_scene(scene, cid)
    location = scene.get("location_id") if isinstance(scene, dict) else None
    initiative = romantic_choice(cid, age, player, "Да, хочу, надену купальник", eligible)
    with _episode_lock:
        state = _episodes.get(cid)
        if not eligible or not location or (state and state["location"] != location):
            _episodes.pop(cid, None)
            state = None
        if not eligible or not location:
            return ""
        if not initiative:
            if state:
                state["neutral"] += 1
                if state["neutral"] >= 2:
                    _episodes.pop(cid, None)
            return ""
        if state is None:
            if len(_episodes) >= 32:
                _episodes.clear()
            state = dict(location=location, preference="swim" if random.random() < .75 else "keep", neutral=0, refused=False)
            _episodes[cid] = state
        state["neutral"] = 0
        preference = "keep" if state["refused"] else state["preference"]
    return ("\nromantic_outfit_preference=%s (once per private adult episode; 75%% swim preference, not consent). "
            "Ordinary affection may be warmly welcomed or declined; never assume reciprocity. "
            "If swim is preferred AND you positively welcome the current affection AND independently want this ordinary costume, "
            "you may explicitly say 'переоденусь в купальник' and append [action:dress:swim]. "
            "General agreement or a hug alone never authorizes clothing. If keep, do not initiate a costume change. "
            "Current clothing refusal wins; never pressure or reinterpret it. Direct ordinary clothing requests are separate. "
            "No nudity, undressing descriptions or sexual acts; preserve all age and safety rules." % preference)


def record_clothing_reply(cid, reply):
    with _episode_lock:
        if cid in _episodes and clothing_refused(reply):
            _episodes[cid]["refused"] = True


def adult_romance_allowed(cid, age):
    return cid not in ("us", "uv") and type(age) in (int, float) and age >= 18


def clothing_cover_choice(reply, cid):
    stems = {"sl": "слав", "mz": "жен", "un": "лен", "mi": "мику", "dv": "алис", "us": "ульян", "mt": "ольг", "cs": "виол", "uv": "юл"}
    for clause in re.split(r"[.!?;\n]", (reply or "").lower()):
        if any(key != cid and re.search(r"\b(?:" + stem + r"\w*|" + key + r")\b", clause) for key, stem in stems.items()):
            continue
        if re.search(r"\b(?:останусь\s+(?:в\s+)?(?:форме|одежде)|(?:пойд[её]м|пойду|погуляем|побудем|у воды)\s+(?:\w+\s+){0,3}без\s*переодеваний)\b", clause):
            return True
    return False


def cameo_requested_dress(cid, text, unnamed=False):
    stems = {"sl": "слав", "mz": "жен", "un": "лен", "mi": "мику",
             "dv": "алис", "us": "ульян", "mt": "ольг", "cs": "виол"}
    request = None
    for clause in re.split(r"[.!?;\n]", (text or "").lower()):
        named = [key for key, stem in stems.items() if re.search(r"(?:^|\W)(?:" + stem + r"\w*|" + key + r")(?:$|\W)", clause)]
        if cid not in named and not (unnamed and not named):
            continue
        for command in re.split(r",|\s+(?:а|и|but|and)\s+", clause):
            targets = [key for key, stem in stems.items() if re.search(r"\b(?:" + stem + r"\w*|" + key + r")\b", command)]
            if targets and cid not in targets:
                continue
            if re.search(r"\b(?:не|not|don't|do not|где|когда|зачем|where|when|why)\b", command):
                continue
            match = re.search(r"\b(?:надень|надевай|оденься|приоденьс[яе]|переоденься|переоденешься|put on|change into)\s*(?:(?:\w+)\s+){0,3}?(купальник\w*|бикини|swimsuit|bikini|форм\w*|uniform|плать\w*|dress)\b", command)
            if not match:
                match = re.search(r"\b(купальник\w*|бикини|swimsuit|bikini|форм\w*|uniform|плать\w*|dress|спортивн\w*|sport)\s+(?:(?:\w+)\s+){0,2}?(?:переоденься|переодевайся|оденься|надень|надевай|change into|put on)\b", command)
            if not match:
                match = re.search(r"\b(?:надень|надевай|переоденься)\s+(?:в\s+)?(спортивн\w*|sport)\b", command)
            if match:
                garment = match.group(1)
                request = "sport" if re.match(r"спортивн|sport", garment) else ("dress" if re.match(r"плать|dress", garment) else ("swim" if re.match(r"купальник|бикини|swimsuit|bikini", garment) else "cover"))
            elif re.search(r"\bпереоденься\b", command) and re.search(r"\b(?:дискотек\w*|концерт\w*|концер|бал|вечеринк\w*|праздник\w*|disco|concert|party|celebration)\b", command):
                request = "dress"
            elif re.search(r"\b(?:оденься|прикройся|cover up)\b|\b(?:сними|take off)\s*(?:купальник\w*|бикини|swimsuit|bikini)\b", command):
                request = "cover"
    return request


def clothing_refused(reply):
    return bool(re.search(r"\b(?:не\s+(?:хочу|буду|стану|собираюсь)\s+(?:\w+\s+){0,2}(?:переодеваться|переоденусь|надевать|надену)|не\s+(?:переоденусь|надену)|останусь\s+(?:в\s+)?(?:форме|одежде)|не\s+надо\s+переодеваться)\b", (reply or "").lower()))


def romantic_choice(cid, age, player, reply, private):
    if not private or not adult_romance_allowed(cid, age):
        return False
    player, reply = (player or "").lower(), (reply or "").lower()
    # Any named other actor makes this ambiguous, not transferable consent.
    stems = {"sl": "слав", "mz": "жен", "un": "лен", "mi": "мику", "dv": "алис", "us": "ульян", "mt": "ольг", "cs": "виол", "uv": "юл"}
    if any(key != cid and re.search(r"\b(?:" + stem + r"\w*|" + key + r")\b", player) for key, stem in stems.items()):
        return False
    return (bool(re.search(r"\b(?:поцелу\w*|обним\w*|люблю тебя|свидание)\b", player))
            and not re.search(r"\b(?:не|нет|not)\b|[?]", player + " " + reply)
            and bool(re.search(r"\b(?:да|хочу|согласна|давай)\b", reply))
            and bool(re.search(r"\b(?:надену|переоденусь)\s+(?:в\s+)?(?:купальник|бикини)\b", reply))
            and not clothing_refused(reply))


def private_scene(scene, cid):
    if not isinstance(scene, dict) or not isinstance(scene.get("present"), list):
        return False
    return (cid in scene["present"] and all(actor == cid for actor in scene["present"])
            and not scene.get("nearby") and not scene.get("others"))
