"""Conservative current-turn travel selection; never recruits remote NPCs."""
import re


def resolve(text, scene, active, detect_location, enabled=False):
    scene = scene if isinstance(scene, dict) else {}
    present = list(dict.fromkeys(cid for cid in (scene.get("present") or []) if isinstance(cid, str) and cid != active)) if isinstance(scene.get("present"), list) else []
    nearby = [cid for cid in scene.get("nearby", []) if isinstance(cid, str) and cid != active] if isinstance(scene.get("nearby"), list) else []
    names = {"sl": r"слав(?:я|яй|ей|ь|и)", "dv": r"алис(?:а|ой|е|у)?", "mi": r"мику",
             "un": r"лен(?:а|ой|е|у)?", "mz": r"жен(?:я|ей|е|ю|ь)", "el": r"электроник(?:ом|а|у)?",
             "sh": r"шурик(?:ом|а|у)?", "us": r"ульян(?:а|ой|е|у)?", "uv": r"юл(?:я|ей|е|ю|ь)",
             "cs": r"виол(?:а|ой|е|у)?", "mt": r"ольг(?:а|ой|е|у)\s+дмитриевн(?:а|ой|е|у)"}
    name = r"(?:" + "|".join(names.values()) + r")(?!\w)"
    local = set(present + nearby + [active])
    stay = []
    for cid, pattern in names.items():
        if cid in local and re.search(r"(?<!\w)" + pattern + r"[\s,!:]*(?:оставай(?:ся|тесь)|остань(?:ся|тесь)|оставь(?:те)?\s+нас)\b", text, re.I) and not re.search(r"\bне\s+(?:оставай|остань|оставь)", text, re.I):
            stay.append(cid)
    movement = r"\b(?:пошли(?:те)?|пойд[её]м(?:те)?|пойду|ид[её]м(?:те)?|схожу|сходим|сходить|отправимся|двинем(?:ся)?|перейд[её]м|переместимся|гулять|отведи(?:те)?|go|let['’]s\s+go)\b"
    collective = r"\b(?:все|вс[её]й\s+компанией|вс[её]й\s+группой|everyone|all\s+together)\b"
    destination, selected, all_requested = None, [], False
    explicit = []
    for clause in re.split(r"[.!?;\n]+|\s+а\s+(?=мы\b)", text):
        if not (re.search(movement, clause, re.I) or re.search(r"\bдавай(?:те)?\s+(?:все\s+)?(?:на|в|к)\b", clause, re.I)):
            continue
        if re.search(r"\b(?:не|нет|don't|not|сказал[аи]?|говорит|спросил[аи]?|раньше|вчера|где|зачем)\b|[?\"«»]", clause, re.I):
            continue
        # Ignore an origin activity before the movement verb (e.g. 'оставайся читать').
        move = re.search(movement, clause, re.I)
        destination_text = clause[move.end():] if move else clause
        destination = detect_location(destination_text)
        if not destination:
            homes = {"un_room": r"к\s+лене\b|к\s+мику\b", "sl_room": r"к\s+славе\b|к\s+жене\b",
                     "dv_room": r"к\s+алисе\b|к\s+ульяне\b", "club_room": r"к\s+электронику\b|к\s+шурику\b"}
            destination = next((loc for loc, pattern in homes.items() if re.search(pattern, destination_text, re.I)), None)
        free_walk = bool(re.search(r"\b(?:гулять|прогуляемся|прогуляться)\b", clause, re.I))
        if not destination and not free_walk:
            continue
        all_requested = bool(re.search(collective, clause, re.I))
        selected = list(present) if all_requested else []
        # A named imperative is also a companion request, not only 'with NAME'.
        for cid, pattern in names.items():
            if cid in local and cid != active and re.search(r"(?:^\s*|[,!:]\s*)" + pattern + r"[\s,!:]*" + movement, clause, re.I):
                selected.append(cid)
                explicit.append(cid)
        for group in re.finditer(r"\b(?:с|со)\s+(" + name + r"(?:\s*(?:,\s*(?:и\s+)?|\s+и\s+)" + name + r")*)", clause, re.I):
            for mention in re.finditer(name, group.group(1), re.I):
                cid = next(cid for cid, pattern in names.items() if re.fullmatch(pattern, mention.group(), re.I))
                if cid in local and cid != active:
                    if cid not in selected:
                        selected.append(cid)
                    if cid not in explicit:
                        explicit.append(cid)
        break
    farewell = [cid for cid, pattern in names.items() if re.search(
        r"(?<!\w)(?:" + pattern + r"[\s,!:]*(?:пока|до\s+встречи|до\s+свидания|уходи(?:те)?)"
        r"|(?:пока|до\s+встречи|до\s+свидания)[\s,!:]*" + pattern + r")(?!\w)", text, re.I)]
    selected = [cid for cid in selected if cid not in stay + farewell]
    candidates = [cid for cid in explicit if cid in selected]
    if not candidates and all_requested:
        candidates = [cid for cid in present if cid in selected and cid in names]
    switch = candidates[0] if enabled is True and active in stay and candidates else None
    if switch:
        selected.remove(switch)
    # An explicit stay overrides model movement even without a known destination.
    blocked = active in stay and not switch
    return {"goto": None if blocked else destination, "travel_with": [] if blocked else selected,
             "travel_all": all_requested and not blocked, "cameo_aside": [cid for cid in stay if cid != active or switch] if destination or switch else [],
             "movement_blocked": blocked, "switch_primary": switch}
