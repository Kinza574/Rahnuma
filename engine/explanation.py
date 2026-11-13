"""Explanation facility: "Why are you asking?", "How did the system reach this?",
plain-English reasons and the summary."""

from engine.certainty import label

GROUP_PURPOSE = {
    "G0": "check that enough information was given",
    "G1": "check for unusual answers",
    "G2": "work out your marks band and test results",
    "G3": "build your aptitude profile",
    "G4": "decide which fields you are eligible for",
    "G5": "decide which fields suit you",
    "G6": "weigh job-market demand",
    "G7": "choose matching universities",
    "G8": "make the final recommendation",
}


def why_asking(qid, kb):
    """Built from the 'asks' list of every rule that uses this answer."""
    rules = [r for r in kb.rules if qid in r.get("asks", [])]
    if not rules:
        return "This answer is shown in your summary and helps you compare options."
    ids = [r["id"] for r in rules]
    shown = ", ".join(ids[:6]) + (" …" if len(ids) > 6 else "")
    purposes = []
    for r in rules:
        p = GROUP_PURPOSE[r["group"]]
        if p not in purposes:
            purposes.append(p)
    joined = purposes[0] if len(purposes) == 1 else ", ".join(purposes[:-1]) + " and " + purposes[-1]
    return f"This answer is used by rules {shown} to {joined}."


def word(cf, kb):
    return label(cf, kb.threshold_values()) or "Weak"


def answer_phrase(name, value, cf, kb):
    """'Yes to "Do you enjoy Mathematics?"' style text for input facts."""
    q = kb.question_by_id.get(name)
    if q is None:
        if name in kb.aptitudes:
            return f"{kb.aptitudes[name].lower()} ({word(cf, kb)})"
        return kb.fact_label(name)
    if q["type"] == "tri":
        ans = "Not sure" if value == "notsure" else "Yes"
        return f"{ans} to \"{q['label']}\""
    return f"{q['label']}: {kb.answer_label(name, value)}"


def field_names(ids, kb):
    return ", ".join(kb.fields[f]["name"] for f in ids if f in kb.fields)


def plain_step(step, kb, technical=False):
    """One trace step as a plain-English sentence."""
    rule = kb.rule_by_id[step["rule"]]
    g = rule["group"]
    added = step["added"]
    used = [u for u in step["matched"] if not u[0].startswith(("elig.", "suit.", "unis.", "missing"))]
    fid = step["field"]
    if g == "G0":
        text = "; ".join(added) if added else "Data check passed."
        text = text.replace("missing += ", "Missing: ").replace("HALT: ", "Stopped: ")
    elif g == "G1":
        text = "; ".join(a.split(": ", 1)[-1] for a in added) or "Checked your answers."
    elif g == "G2":
        text = rule["text"].split(" THEN ")[-1].rstrip(".")
        text = f"From your marks: {text}."
    elif g == "G3":
        fact = rule["then"][0]["assert"]
        reasons = " and ".join(answer_phrase(n, v, c, kb) for n, v, c in used)
        text = f"Because you answered {reasons}, you show {kb.fact_label(fact).lower()} ({word(step['cf'], kb)})."
    elif g == "G4":
        text = "Eligibility: " + "; ".join(a.replace("elig.", "").replace("not_eligible", "not eligible") for a in added) if added else "Eligibility checked."
        for f in kb.fields:
            text = text.replace(f"{f} = ", f"{kb.fields[f]['name']} = ")
    elif g == "G5":
        f = rule["then"][0]["suit"]
        reasons = ", ".join(answer_phrase(n, v, c, kb) for n, v, c in used) or "your answers"
        text = f"{kb.fields[f]['name']} suits you ({word(step['cf'], kb)}) because of {reasons}."
    elif g == "G6":
        if rule["id"] == "MK03":
            text = f"{kb.fields[fid]['name']}: fewer jobs in Pakistan right now (note only)."
        else:
            where = "in Pakistan" if rule["id"] == "MK01" else "abroad, and you want to work abroad"
            text = f"{kb.fields[fid]['name']}: high job demand {where}, so confidence goes up."
    elif g == "G7":
        text = f"Universities for {kb.fields[fid]['name']}: " + "; ".join(a.split(": ", 1)[-1] for a in added)
    else:
        text = "; ".join(added)
    if technical:
        text = f"[{step['instance']}, CF {step['cf_text']}] {text}"
        if len(step["conflict_set"]) > 1:
            text += f" (conflict set: {', '.join(step['conflict_set'][:6])}{' …' if len(step['conflict_set']) > 6 else ''})"
    return text


def plain_steps(trace, kb, technical=False):
    return [plain_step(s, kb, technical) for s in trace]


def reasons_for(fid, wm, kb, technical=False):
    """2-3 plain reasons why a field was recommended."""
    out = []
    suit = wm.get(f"suit.{fid}")
    for rid in suit.source_rules:
        base = rid.split("[")[0]
        rule = kb.rule_by_id[base]
        if rule["group"] == "G5":
            for cond in rule["if"]["all"][1:]:
                name = cond.get("fact") or cond.get("not", {}).get("fact")
                if "not" in cond or name is None:
                    continue
                f = wm.get(name)
                if f is None:
                    continue
                if name in kb.aptitudes:
                    out.append(f"Your {kb.aptitudes[name].lower()} aptitude is {word(f.cf, kb).lower()}.")
                else:
                    out.append(f"You answered {answer_phrase(name, f.value, f.cf, kb)}.")
        elif base == "MK01":
            out.append("Job demand in Pakistan is high for this field.")
        elif base == "MK02":
            out.append("Demand abroad is high, and you want to work abroad.")
        if technical:
            out[-1:] = [f"{out[-1]} ({rid})"] if out else []
    seen = []
    for r in out:
        if r not in seen:
            seen.append(r)
    return seen[:4]


def summary_text(wm, kb):
    """RC08: a 2-3 sentence summary."""
    parts = []
    band = wm.value("inter_band")
    if band:
        parts.append(f"Your Inter marks are in the {band} band.")
    top = wm.result.get("top", [])
    if top:
        named = [f"{kb.fields[f]['name']} ({word(wm.get('suit.' + f).cf, kb)})" for f in top]
        if len(named) == 1:
            parts.append(f"Your best match is {named[0]}.")
        else:
            parts.append(f"Your best match is {named[0]}, followed by {' and '.join(named[1:])}.")
    else:
        parts.append("No field is a strong match yet.")
    important = None
    plan = wm.result.get("action_plan") or []
    if wm.warnings:
        important = wm.warnings[0][1]
    elif plan:
        important = plan[0]
    if important:
        parts.append(f"Most important: {important}")
    return " ".join(parts)
