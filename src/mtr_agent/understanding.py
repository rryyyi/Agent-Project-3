"""Inspectable offline intent/slot extraction for a deliberately bounded demo."""

import re

OPERATIONAL = re.compile(
    r"尾班|末班|首班|幾點|几点|幾錢|多少钱|票價|票价|延誤|延误|實時|实时|即時|"
    r"\bfare\b|\bdelay\b|\btimetable\b|\bfirst train\b|\blast train\b|\blive\b",
    re.I,
)
ROUTE = re.compile(r"去|到|點搭|怎么走|怎麼走|換乘|换乘|路線|路线|\bfrom\b|\bto\b|\broute\b", re.I)
NEGATION = re.compile(r"唔係|不是|唔去|不去|未定|\bnot\b|\binstead\b", re.I)
FOLLOWUP = re.compile(r"咁|呢|那|改去|換去|换去|\bwhat about\b|\bhow about\b|\binstead\b", re.I)


def understand(message: str, kb, context: dict | None = None) -> dict:
    context = context or {}
    mentions = kb.mentions(message)
    ids = kb.resolve(message)
    objective = (
        "fewest_transfers"
        if re.search(
            r"少換|少换|最少.*換|最少.*换|fewest|minimal transfer|least transfer", message, re.I
        )
        else "fastest"
    )
    if OPERATIONAL.search(message):
        return {"intent": "knowledge", "query": message, "stations": ids}
    if len(ids) >= 2 or ROUTE.search(message):
        base = {"intent": "route", "query": message, "stations": ids, "objective": objective}
        if NEGATION.search(message) or len(ids) > 2:
            return {**base, "clarification": "請明確提供起點與終點；示例一次只規劃兩站行程。"}
        if len(ids) == 2:
            # Explicit direction markers win over mention order, including 'to A from B'.
            from_match = re.search(r"\bfrom\b|由|从|從", message, re.I)
            first_station = mentions[0]["start"]
            prefix = message[:first_station]
            direction_markers = list(re.finditer(r"\bfrom\b|\bto\b|由|从|從|去|到", prefix, re.I))
            last_marker = direction_markers[-1].group().casefold() if direction_markers else ""
            origin, destination = ids
            if from_match and last_marker in {"to", "去", "到"}:
                origin, destination = ids[1], ids[0]
            # Repeated aliases collapse, but two distinct slots remain unambiguous.
            return {
                **base,
                "origin": origin,
                "destination": destination,
                "query": f"route {origin} -> {destination}; objective={objective}",
            }
        if len(ids) == 1 and context.get("origin") and FOLLOWUP.search(message):
            mention = mentions[-1]
            # A follow-up may contain a single known destination, not a second unknown one.
            tail = message[mention["end"] :]
            if not re.search(r"去|到|\bto\b", tail, re.I):
                return {
                    **base,
                    "origin": context["origin"],
                    "destination": ids[0],
                    "query": f"route {context['origin']} -> {ids[0]}; objective={objective}",
                }
        # Handle a true same-station question, rather than treating duplicated bilingual aliases as slots.
        if len(ids) == 1 and len(mentions) >= 2:
            between = message[mentions[0]["end"] : mentions[-1]["start"]]
            if re.search(r"去|到|\bto\b", between, re.I):
                return {**base, "origin": ids[0], "destination": ids[0]}
        return {**base, "clarification": "請提供示例網絡內的起點和終點，例如 Central 去紅磡。"}
    return {"intent": "knowledge", "query": message, "stations": ids}
