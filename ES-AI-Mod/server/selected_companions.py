"""Conservative travel selection; remote visits are validated separately."""
import re


def movement_clause(text):
    """Authorize player travel, never an NPC imperative or generated narration."""
    if re.search(r"[?\"'«»„“”]", text):
        return None
    for clause in re.split(r"[.!?;\n]|,\s*|\b(?:но|а)\s+", text, flags=re.I):
        if re.search(r"\b(?:не|нет|если|бы|может|думал|сказал[аи]?|говорит|вчера|раньше)\b|[?\"'«»„“”]", clause, re.I):
            continue
        if re.match(r"\s*(?:\w+\s+)?(?:отведи|проводи)\s+(?:меня\s+)?(?:туда|на|в|к)\b", clause, re.I):
            return clause
        if re.match(r"\s*(?:я\s+)?(?:пошли(?:те)?|пойд[её]м(?:те)?|пойду|пош[её]л|ид[её]м(?:те)?|схожу|сходим|отправлюсь|отправимся|перейд[её]м|давай(?:те)?|хочу\s+(?:пойти|сходить))\b", clause, re.I):
            return clause
    return None


def directional_target(text, names):
    if re.search(r"\b(?:не|нет|если|бы|может|думал|думаю|сказал[аи]?|говорит|вчера|раньше)\b|[?\"'«»„“”]", text, re.I):
        return None
    targets = [cid for cid, pattern in names.items() if re.search(
        r"^\s*я\s+(?:\w+\s+){0,2}(?:к|до)\s+" + pattern + r"(?!\w)", text, re.I)]
    return targets[0] if len(targets) == 1 else None


def retrospective_farewell(text):
    """A past goodbye is not a new action; explicit current commands still win."""
    past = re.search(r"\bя\s+(?:(?:же|уже|ведь)\s+)*попрощал(?:ся|ась)\s+с\s+тобой\b", text, re.I)
    if not past:
        return False
    current = text[:past.start()] + text[past.end():]
    return not re.search(
        r"\b(?:пока|до\s+встречи|до\s+свидания|пойду|схожу|пош[её]л|пошли|пойд[её]м|"
        r"иди|уходи|оставайся|останься|оставь|позови|пригласи|хочу|поговорю|помогу)\b"
        r"|\bмне\s+пора\b|\bя\s+от\s+тебя\s+ухожу\b", current, re.I)


def encounter_intent(text, names):
    """Decide direction before locality; visiting never means summoning."""
    if re.search(r"\b(?:не|нет|если|бы|может|сказал[аи]?|говорит|спросил[аи]?|цитата|вчера|раньше|где)\b|[?\"'«»„“”]", text, re.I):
        return None
    found = []
    for cid, pattern in names.items():
        person = r"(?<!\w)" + pattern + r"(?!\w)"
        first_person = r"(?:пойду|схожу|пош[её]л|отправлюсь)"
        visit = (r"\b(?:я\s+(?:(?:теперь|дальше|лучше)\s+)?|а\s+теперь\s+)" + first_person + r"\s+(?:к|до)\s+" + person +
                 r"|(?:^|[.!;\n])\s*" + first_person + r"\s+(?:к|до)\s+" + person +
                 r"|\bя\s+(?:к|до)\s+" + person + r"\s+" + first_person + r"\b")
        invite = r"\b(?:позови|пригласи|зови|позов[её]м)\s+" + person
        if re.search(visit, text, re.I):
            found.append(dict(target=cid, direction="visit"))
        elif re.search(invite, text, re.I):
            found.append(dict(target=cid, direction="invite"))
    return found[0] if len(found) == 1 else None


def preferred_context_target(text, names):
    """Only positive player intentions, never incidental names or generated speech."""
    if re.search(r"\b(?:не|нет|если|бы|может|сказал[аи]?|говорит|спросил[аи]?|цитата|вчера|раньше)\b|[?\"'«»„“”]", text, re.I):
        return None
    targets = []
    for clause in re.split(r"[.!;\n]", text):
        for cid, pattern in names.items():
            person = r"(?<!\w)" + pattern + r"(?!\w)"
            intention = (r"\b(?:я\s+(?:(?:теперь|дальше|лучше)\s+)?|а\s+теперь\s+)(?:"
                         r"(?:хочу\s+)?(?:поговорить|поболтать|пообщаться|поговорю|поболтаю|пообщаюсь)\s+с\s+" + person +
                         r"|(?:хочу\s+)?(?:помочь|помогу)\s+" + person +
                         r"|" + person + r"\s+(?:помогу|хочу\s+помочь)\b"
                         r"|(?:пойду|схожу|пош[её]л)\s+(?:к|до)\s+" + person + r")")
            if re.search(intention, clause, re.I) or re.search(
                    r"^\s*хочу\s+(?:поговорить|поболтать|пообщаться)\s+с\s+" + person, clause, re.I):
                targets.append(cid)
                # A coordinated group is not an unambiguous primary request.
                if len([key for key, value in names.items() if re.search(r"(?<!\w)" + value + r"(?!\w)", clause, re.I)]) > 1 and re.search(r"\sи\s", clause, re.I):
                    return None
    return targets[0] if len(set(targets)) == 1 else None


def resolve(text, scene, active, detect_location, enabled=False, recent_player=None):
    # Only the observed one-character movement typo, in intent parsing, not history.
    text = re.sub(r"\bпош([её])лк(?=\s+(?:к|до)\s)", r"пош\1л", text, flags=re.I)
    if retrospective_farewell(text):
        return dict(goto=None, travel_with=[], travel_all=False, cameo_aside=[],
                    movement_blocked=True, switch_primary=None, visit_primary=None,
                    farewell_primary=False, retrospective_farewell=True,
                    primary_reason="no-handoff")
    scene = scene if isinstance(scene, dict) else {}
    present = list(dict.fromkeys(cid for cid in (scene.get("present") or []) if isinstance(cid, str) and cid != active)) if isinstance(scene.get("present"), list) else []
    nearby = [cid for cid in scene.get("nearby", []) if isinstance(cid, str) and cid != active] if isinstance(scene.get("nearby"), list) else []
    names = {"sl": r"слав(?:я|яй|ей|ь|и)", "dv": r"алис(?:а|ой|е|у|ы)?", "mi": r"мику",
             "un": r"лен(?:а|ой|е|у)?", "mz": r"жен(?:я|ей|е|ю|ь)", "el": r"электроник(?:ом|а|у)?",
             "sh": r"шурик(?:ом|а|у)?", "us": r"ульян(?:а|ой|е|у)?", "uv": r"юл(?:я|ей|е|ю|ь)",
             "cs": r"виол(?:а|ой|е|у)?", "mt": r"ольг(?:а|ой|е|у)\s+дмитриевн(?:а|ой|е|у)"}
    encounter = encounter_intent(text, names)
    directional = directional_target(text, names)
    npc_depart = []
    if not re.search(r"\b(?:не|нет|если|бы|сказал[аи]?|говорит|думал)\b|[?\"'«»„“”]", text, re.I):
        for cid, pattern in names.items():
            if cid in present + nearby + [active] and re.search(
                    r"^\s*(?:(?:ну|ладно)\s*[,!]\s*)?" + pattern +
                    r"\s*[,!:]?\s+(?:иди|уходи|отправляйся|возвращайся)\s+(?:в|на|к|домой|спать)\b", text, re.I):
                npc_depart.append(cid)
    name = r"(?:" + "|".join(names.values()) + r")(?!\w)"
    # Conversation termination is independent of finding a replacement NPC.
    farewell_primary = False
    if not re.search(r"\b(?:не|нет|если|бы|может|сказал[аи]?|говорит|спросил[аи]?|цитата)\b|[?\"'«»„“”]", text, re.I):
        other_address = any(cid != active and (re.match(r"^\s*" + pattern + r"\s*[,!:]", text, re.I)
                            or re.search(r"\b(?:пока|до\s+встречи|до\s+свидания)\s*[,!:]?\s*" + pattern + r"(?!\w)", text, re.I))
                            for cid, pattern in names.items())
        if not other_address:
            opening = re.sub(r"^\s*" + names.get(active, r"(?!)") + r"\s*[,!:]?\s*", "", text, flags=re.I)
            farewell_primary = not bool(re.match(r"пока\s+(?:мы|я|ты|он|она|они|здесь|тут|что)\b", opening, re.I)) and bool(re.search(
                r"^(?:(?:ну|ладно|вс[её])\b[\s,!]*)*(?:пока|до\s+свидания|до\s+встречи)(?=[\s,.!]|$)"
                r"|\bя\s+(?:от\s+тебя\s+ухожу|пойду\s+один|пош[её]л)(?=[\s,.!]|$)"
                r"|[,;]\s*пока\s*[!.]*\s*$"
                r"|\bмне\s+пора(?=[\s,.!]|$)"
                r"|(?:^|[.!;\n])\s*(?:ладно\s*,\s*)?я\s+(?:вас|тебя)\s+покидаю(?=[\s,.!]|$)"
                r"|\b(?:иди|уходи)\s+(?:наверное\s+)?(?:домой|спать)(?=[\s,.!]|$)", opening, re.I))
    local = set(present + nearby + [active])
    if npc_depart:
        remaining = sorted(local - set(npc_depart) - {active})
        switch = remaining[0] if active in npc_depart and enabled is True and scene.get("enabled") is True and len(remaining) == 1 else None
        return dict(goto=None, travel_with=[], travel_all=False, cameo_aside=[],
                    movement_blocked=False, player_travel_blocked=True, npc_depart=npc_depart,
                    travel_party=[],
                    switch_primary=switch, visit_primary=None,
                    farewell_primary=active in npc_depart, primary_reason="directed-npc-departure")
    preferred = preferred_context_target(text, names)
    source = "current" if preferred else None
    # A farewell or destination follow-up can complete a pending player visit.
    if not preferred and (farewell_primary or re.fullmatch(r"\s*пошли\s+(?:до\s+тебя|к\s+тебе)\s*[!.]*\s*", text, re.I)):
        for previous in reversed((recent_player or [])[-2:]):
            candidate = preferred_context_target(previous, names)
            if candidate:
                # An intention already addressed to the effective primary is consumed.
                prior_encounter = encounter_intent(previous, names)
                if candidate != active and (prior_encounter or not resolve(previous, {}, active, lambda t: None).get("farewell_primary")):
                    preferred, source = candidate, "prior"
                    if prior_encounter and prior_encounter["direction"] == "visit":
                        encounter = prior_encounter
                break
    stay = []
    release = False
    unsafe = r"\b(?:не|нет|don't|not|сказал[аи]?|говорит|спросил[аи]?|раньше|вчера|где|зачем|если|может)\b|[?\"«»]"
    # Privacy excludes the cohort; only explicit player movement may accompany it.
    privacy_targets = []
    if not re.search(unsafe + r"|\b(?:бы|сказала|сказано|цитата)\b|['„“”]", text, re.I):
        for clause in re.split(r"(?<=[.!?;\n])", text):
            request = re.match(r"\s*(?:(" + name + r")\s*,\s*)?(?:я\s+)?хочу\s+(?:побыть|быть|остаться)\s+наедине\s+с\s+", clause, re.I)
            if not request:
                continue
            partner = clause[request.end():].strip().rstrip(".! ")
            for cid, pattern in names.items():
                if re.fullmatch(pattern, partner, re.I) or (
                        cid == active and re.fullmatch(r"тобой", partner, re.I)
                        and (not request.group(1) or re.fullmatch(pattern, request.group(1), re.I))):
                    privacy_targets.append(cid)
    if len(set(privacy_targets)) == 1:
        target = privacy_targets[0]
        switch = target if target in local and target != active and enabled is True else None
        blocked = target not in local or (target != active and not switch)
        effective = switch or active
        move = movement_clause(text)
        destination = detect_location(move) if move and not blocked else None
        return {"goto": destination, "travel_with": [], "travel_all": False,
                "cameo_aside": [],
                "scene_depart": list(dict.fromkeys(cid for cid in [active] + present + nearby
                                                  if cid != effective and cid in names)) if not blocked else [],
                "movement_blocked": blocked, "switch_primary": switch, "visit_primary": None,
                 "privacy": True,
                 "travel_party": [] if not blocked else None,
                "primary_reason": "privacy-target-not-local" if target not in local else
                                  "privacy-disabled" if blocked else "local-privacy"}
    for cid, pattern in names.items():
        for clause in re.split(r"(?<=[.!?;\n])", text):
            if cid in local and not re.search(unsafe, clause, re.I) and re.search(r"(?<!\w)" + pattern + r"[\s,!:]*(?:оставай(?:ся|тесь)|остань(?:ся|тесь)|оставь(?:те)?\s+нас)\b", clause, re.I):
                stay.append(cid)
                if cid == active and re.search(r"\bоставь(?:те)?\s+нас\b", clause, re.I):
                    release = True
    movement = r"\b(?:пошли(?:те)?|пойд[её]м(?:те)?|пойду|пош[её]л|ид[её]м(?:те)?|схожу|сходим|сходить|отправлюсь|отправимся|двинем(?:ся)?|перейд[её]м|переместимся|гулять|отведи(?:те)?|go|let['’]s\s+go)\b"
    collective = r"\b(?:все|вс[её]й\s+компанией|вс[её]й\s+группой|everyone|all\s+together)\b"
    destination, selected, all_requested = None, [], False
    explicit = []
    handoff = False
    group_requested = False
    party = [cid for cid in scene.get("travel_party", []) if cid in present + [active] and cid in names] if isinstance(scene.get("travel_party"), list) else []
    party_update = None
    for clause in re.split(r"(?<=[.!?;\n])|\s+а\s+(?=мы\b)|(?<=нет),\s*(?=(?:пошли|пойд[её]м|пойду|давай)\b)", text):
        # Bind an imperative to its addressee, not to every name in the sentence.
        directed = []
        leaving = False
        for cid, pattern in names.items():
            if cid == active:
                continue
            address = re.search(r"^\s*" + pattern + r"[\s,!:]+", clause, re.I)
            command = clause[address.end():] if address else ""
            leave = bool(address and active in names and re.search(
                r"^оставим\s+" + names[active] + r"(?!\w)", command, re.I))
            if (address and (re.match(movement, command, re.I) or leave)) or re.search(
                    r"^\s*" + movement + r"\s*,\s*" + pattern + r"\s*[!.]?\s*$", clause, re.I):
                directed.append(cid)
                leaving = leaving or leave
        conversation = re.search(r"\bя\s+(?:(?:теперь|дальше|лучше)\s+)?(?:поговорю|поболтаю|продолжу\s+(?:разговор|общение))\s+с\b", clause, re.I)
        if not (directed or conversation or re.search(movement, clause, re.I) or re.search(r"\bдавай(?:те)?\s+(?:все\s+)?(?:на|в|к)\b", clause, re.I)):
            continue
        if re.search(unsafe, clause, re.I):
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
        departure = bool(re.search(r"\bя\s+(?:(?:теперь|дальше|лучше)\s+)?(?:пойду|схожу)\s+с\b", clause, re.I))
        all_requested = bool(re.search(collective, clause, re.I))
        group_requested = all_requested or bool(re.search(r"\bс\s+нами\b", clause, re.I)) or (
            not directed and bool(re.search(r"\b(?:ид[её]мте|пойд[её]мте|ид[её]м\s+дальше)\b", clause, re.I)))
        solo = bool(re.search(r"\b(?:я\s+(?:пойду|схожу|пош[её]л|отправлюсь)|один|одна|вдво[её]м|только)\b", clause, re.I))
        selected = list(present) if group_requested and not solo else [cid for cid in party if cid != active] if party and not solo else []
        if solo:
            party_update = []
            group_requested = False
            all_requested = False
        for cid in directed:
            if cid in local:
                selected.append(cid)
                explicit.append(cid)
        # A named imperative is also a companion request, not only 'with NAME'.
        for cid, pattern in names.items():
            if cid in local and cid != active and re.search(r"(?:^\s*|[,!:]\s*)" + pattern + r"[\s,!:]*" + movement, clause, re.I):
                if cid not in selected:
                    selected.append(cid)
                if cid not in explicit:
                    explicit.append(cid)
        for group in re.finditer(r"\b(?:с|со)\s+(" + name + r"(?:\s*(?:,\s*(?:и\s+)?|\s+и\s+)" + name + r")*)", clause, re.I):
            for mention in re.finditer(name, group.group(1), re.I):
                cid = next(cid for cid, pattern in names.items() if re.fullmatch(pattern, mention.group(), re.I))
                if cid in local and cid != active:
                    if cid not in selected:
                        selected.append(cid)
                    if cid not in explicit:
                        explicit.append(cid)
        handoff = len(explicit) == 1 and bool(conversation or departure or directed)
        if not destination and not directed and re.search(r"\b(?:к\s+тебе|до\s+тебя)\b", clause, re.I):
            destination = next((loc for loc, ids in {"sl_room": ("sl", "mz"), "un_room": ("un", "mi"),
                               "dv_room": ("dv", "us"), "club_room": ("el", "sh")}.items()
                               if active in ids), None)
        if handoff and directed and not destination and re.search(r"\bк\s+тебе\b", clause, re.I):
            destination = next((loc for loc, ids in {"sl_room": ("sl", "mz"), "un_room": ("un", "mi"),
                               "dv_room": ("dv", "us"), "club_room": ("el", "sh")}.items()
                               if explicit[0] in ids), None)
        if leaving and handoff:
            stay.append(active)
        if destination or free_walk or handoff or (move and (group_requested or party)):
            break
        selected, explicit = [], []
    farewell = [cid for cid, pattern in names.items() if re.search(
        r"(?<!\w)(?:" + pattern + r"[\s,!:]*(?:пока|до\s+встречи|до\s+свидания|уходи(?:те)?)"
        r"|(?:пока|до\s+встречи|до\s+свидания)[\s,!:]*" + pattern + r")(?!\w)", text, re.I)]
    if explicit and not group_requested:
        selected = [cid for cid in selected if cid in explicit]
        party_update = []
    selected = list(dict.fromkeys(cid for cid in selected if cid not in stay + farewell))
    candidates = [cid for cid in explicit if cid in selected]
    if not candidates and all_requested:
        candidates = [cid for cid in present if cid in selected and cid in names]
    if release and not candidates and not any(cid != active and re.search(r"(?<!\w)" + pattern + r"(?!\w)", text, re.I) for cid, pattern in names.items()):
        remaining = [cid for cid in present + nearby if cid in names and cid not in stay + farewell]
        remaining = list(dict.fromkeys(remaining))
        if len(remaining) == 1:
            candidates = remaining
    switch = candidates[0] if enabled is True and (active in stay or handoff) and candidates and (len(candidates) == 1 or (active in stay and destination)) else None
    if switch:
        if switch in selected:
            selected.remove(switch)
        if group_requested and active not in stay + farewell:
            selected.append(active)
        elif active not in stay:
            stay.append(active)
    # An explicit stay overrides model movement even without a known destination.
    blocked = active in stay and not switch
    visit = None
    # A visit is not an invitation to bring a remote character to the origin.
    if not switch and not re.search(unsafe, text, re.I):
        visitors = [cid for cid, pattern in names.items() if cid != active and cid not in local
                    and (re.search(r"\bя\s+(?:пойду|схожу|пош[её]л)\s+(?:к|до)\s+" + pattern + r"(?!\w)", text, re.I)
                         or re.search(r"\bя\s+(?:к|до)\s+" + pattern + r"\s+(?:пойду|схожу|пош[её]л)\b", text, re.I))]
        if len(visitors) == 1:
            visit = {"id": visitors[0], "location_id": None}
            blocked = True
    if enabled is True and preferred and preferred != active and not switch and not privacy_targets:
        if preferred in local and scene.get("enabled", True) is True:
            switch = preferred
            selected = []
            stay = list(dict.fromkeys(stay + [active]))
            blocked = False
            visit = None
            if source == "prior":
                destination = None
        else:
            # Only a canonical host visit may locate a remote intended partner.
            visit = {"id": preferred, "location_id": None}
            blocked = True
    if encounter and encounter["direction"] == "visit" and encounter["target"] != active:
        # Even a locally recorded host must pass destination conflict guards.
        visit = {"id": encounter["target"], "location_id": None}
        switch, selected, blocked = None, [], True
    if directional and directional != active and not visit:
        # A directional first-person request must never degrade into an invitation.
        switch, selected, blocked = None, [], True
    if stay or farewell or farewell_primary or visit or directional or (switch and not group_requested):
        party_update = []
    elif group_requested and not blocked:
        party_update = list(dict.fromkeys([switch or active] + selected))
    elif party and (destination or movement_clause(text)) and not blocked and party_update is None:
        party_update = list(dict.fromkeys([switch or active] + selected))
    return {"goto": None if blocked else destination, "travel_with": [] if blocked else selected,
              "travel_party": party_update,
             "travel_all": all_requested and not blocked, "cameo_aside": [cid for cid in stay if cid != active or switch] if destination or switch else [],
               "movement_blocked": blocked, "switch_primary": switch, "visit_primary": visit,
                "farewell_primary": farewell_primary,
                 "context_target": preferred, "context_source": source,
                 "encounter_direction": encounter["direction"] if encounter else "local" if switch else None,
                  "visit_recognized": bool(visit),
                  "directional_visit": directional,
                  "player_travel_blocked": not bool(movement_clause(text)),
                  "travel_refused": not movement_clause(text) and bool(re.search(r"^\s*(?:нет|не\s+(?:пойд|пош|хочу\s+(?:идти|пойти)))", text, re.I)),
               "primary_reason": "local-handoff" if switch else "disabled" if enabled is not True else "release-needs-local-partner" if blocked else "no-handoff"}
