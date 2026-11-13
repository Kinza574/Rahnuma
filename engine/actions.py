"""THEN-part actions of rules.

Each action is a small dict in rules.json, e.g. {"assert": "apt_analytical"}.
execute() runs one action and returns short texts for the trace.
"""

from engine.certainty import label
from engine.conditions import evaluate, ranked_suits, resolve

STATUS_RANK = {"conditional": 1, "eligible": 2}
FEE_ORDER = {"low": 0, "medium": 1, "high": 2}
BUDGET_MAX_BAND = {"low": 0, "medium": 1, "high": 2}


def execute(act, rule, bind, match, cf, wm, kb):
    rid = rule["id"] + (f"[{bind}]" if bind else "")
    for key, handler in HANDLERS.items():
        if key in act:
            return handler(act, rid, bind, match, cf, wm, kb) or []
    raise ValueError(f"Unknown action in {rid}: {act}")


def fill(text, wm, kb, bind=None, extra=None):
    """Fill {placeholders} in a message from thresholds, facts and labels."""
    values = dict(kb.threshold_values())
    for name, f in wm.facts.items():
        values[name] = kb.answer_label(name, f.value)
    if bind:
        values["field"] = kb.fields[bind]["name"]
    values.update(extra or {})
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


# ---- G0 / G1 ----

def _add_missing(act, rid, bind, match, cf, wm, kb):
    f = wm.get("missing")
    items = (f.value if f else []) + [act["add_missing"]]
    wm.put("missing", items, 1.0, rid)
    return [f"missing += {act['add_missing']}"]


def _halt(act, rid, bind, match, cf, wm, kb):
    wm.halted = True
    wm.result["status"] = act.get("status", "insufficient")
    return ["HALT: " + act.get("text", "")]


def _warn(act, rid, bind, match, cf, wm, kb):
    text = fill(act["warn"], wm, kb, bind)
    wm.warnings.append((rid, text))
    return [f"warning: {text}"]


def _ignore(act, rid, bind, match, cf, wm, kb):
    """Ignore an input (only if its own small condition holds) and warn with its value."""
    name = act["ignore"]
    f = wm.get(name)
    if f is None:
        return []
    if "if" in act and not evaluate(act["if"], wm, kb, bind).ok:
        return []
    text = fill(act["warn"], wm, kb, bind, {"value": kb.answer_label(name, f.value)})
    wm.ignore(name, text, rid)
    wm.warnings.append((rid, text))
    return [f"ignored {name} = {f.value}: {text}"]


# ---- facts ----

def _assert(act, rid, bind, match, cf, wm, kb):
    name = resolve(act["assert"], kb, bind)
    value_cf = resolve(act["cf"], kb, bind) if "cf" in act else cf
    how = wm.add(name, act.get("value", True), value_cf, rid)
    return [f"{name} (CF {wm.get(name).cf:.3f})" + (f"; {how}" if how else "")]


def _set(act, rid, bind, match, cf, wm, kb):
    wm.put(act["set"], act["value"], cf, rid)
    return [f"{act['set']} = {act['value']}"]


def _note(act, rid, bind, match, cf, wm, kb):
    text = fill(act["note"], wm, kb, bind)
    wm.notes.append((rid, bind, text))
    return [f"note: {text}"]


# ---- G4 eligibility ----

def _eligibility(act, rid, bind, match, cf, wm, kb):
    fields = [bind] if act["eligibility"] == "$F" else act["eligibility"]
    status = act["status"]
    reasons, plans = [], []
    if status == "not_eligible":
        new_cf = 1.0
        if act["eligibility"] == "$F":
            reasons.append(not_eligible_reason(bind, wm, kb))
        else:
            reasons.append(fill(act["reason"], wm, kb))
    else:
        uncertain = [(n, c) for n, v, c in match.used if c < 1.0]
        if status == "eligible" and uncertain:
            status = "conditional"
        if status == "conditional":
            new_cf = min(kb.t("conditional_cf"), cf)
        else:
            new_cf = 1.0
        if act.get("reason"):
            reasons.append(fill(act["reason"], wm, kb))
        if act.get("plan"):
            plans.append(fill(act["plan"], wm, kb))
        for n, c in uncertain:
            text = kb.confirm_text(n)
            if text and text not in reasons:
                reasons.append(text)
                plans.append(text[0].upper() + text[1:])
    out = []
    for fid in fields:
        name = f"elig.{fid}"
        old = wm.get(name)
        meta = {"reasons": list(reasons), "plans": list(plans), "notes": act.get("notes", [])}
        if old is not None and status != "not_eligible" and old.value != "not_eligible":
            # D2: the better status wins; same status keeps the higher CF; reasons merge
            if STATUS_RANK[old.value] > STATUS_RANK[status]:
                continue
            if STATUS_RANK[old.value] == STATUS_RANK[status]:
                new_meta = {k: old.meta.get(k, []) + [x for x in meta[k] if x not in old.meta.get(k, [])] for k in meta}
                wm.put(name, status, max(old.cf, new_cf), rid, new_meta)
                out.append(f"{name} = {status} (CF {max(old.cf, new_cf):.3f}, merged)")
                continue
        if old is not None and old.value == "not_eligible":
            continue  # strict: once not eligible, nothing upgrades it
        wm.put(name, status, new_cf, rid, meta)
        out.append(f"{name} = {status} (CF {new_cf:.3f})")
    return out


def not_eligible_reason(fid, wm, kb):
    """Plain reason built from the field's requirements and the student's data."""
    f = kb.fields[fid]
    need = fill(f["requirements_text"], wm, kb)
    have = []
    stream = wm.get("stream")
    if stream:
        have.append(f"your stream is {kb.answer_label('stream', stream.value)}")
    inter = wm.get("inter_pct")
    if inter:
        have.append(f"your Inter marks are {inter.value:g}%")
    if not wm.has("marks_reliable") and inter:
        have.append("your Inter result type is not known")
    for test, qid in (("MDCAT", "mdcat_pct"), ("LAT", "lat_pct")):
        if test in f.get("required_test", "") and wm.has(qid):
            have.append(f"your {test} score is {wm.value(qid):g}")
    return f"Needs {need}" + (f"; {', '.join(have)}." if have else ".")


# ---- G5 / G6 suitability ----

def _suit(act, rid, bind, match, cf, wm, kb):
    fid = bind if act["suit"] == "$F" else act["suit"]
    name = f"suit.{fid}"
    weight = cf
    how = wm.add(name, True, weight, rid)
    return [f"{name} (CF {wm.get(name).cf:.3f})" + (f"; {how}" if how else "")]


# ---- G7 universities ----

def _uni(act, rid, bind, match, cf, wm, kb):
    step = act["uni"]
    name = f"unis.{bind}"
    if step == "candidates":
        base = candidates(bind, wm, kb)
        wm.put(name, base, 1.0, rid, {"base": base, "steps": [], "removed": [], "relaxed": []})
        return [f"{name}: {len(base)} candidates"]
    f = wm.get(name)
    if step == "relax":
        return relax(f, bind, wm, kb, rid)
    kept, removed = FILTERS[step](f.value, wm, kb)
    f.meta["steps"].append(step)
    f.meta["removed"] += removed
    f.value = kept
    f.source_rules.append(rid)
    return [f"{name}: {step} filter -> {len(kept)} left ({len(removed)} removed)"]


def candidates(fid, wm, kb):
    gender = wm.value("gender")
    test_inputs = {"mdcat": "mdcat_pct", "ecat": "ecat_pct", "net": "net_pct", "nat": "nat_pct", "sat": "sat_score", "lat": "lat_pct"}
    out = []
    for u in kb.universities["universities"]:
        if u["women_only"] and gender == "male":
            continue
        for o in u["offerings"]:
            if o["field"] != fid:
                continue
            tags = []
            if u["women_only"] and gender != "female":
                tags.append("women only")
            if not o.get("verified"):
                tags.append("Not yet verified")
            keys = o.get("test_keys", [])
            if keys:
                taken = any(wm.has(test_inputs[k]) for k in keys if k in test_inputs)
                test_status = "taken" if taken else "not yet"
            else:
                test_status = "university's own test" if o.get("tests") else "none"
            out.append({
                "uni_id": u["id"], "name": u["name"], "city": u["city"], "sector": u["sector"],
                "women_only": u["women_only"], "hostel": u.get("hostel") or "unknown",
                "fee_band": o["fee_band"], "min_pct": o.get("min_pct"),
                "tests": ", ".join(o.get("tests", [])) or "None stated",
                "test_status": test_status, "source_url": o.get("source_url", ""),
                "verified": bool(o.get("verified")), "tags": tags,
            })
    return out


def f_min_pct(items, wm, kb):
    inter = wm.value("inter_pct")
    kept, removed = [], []
    for it in items:
        if inter is not None and it["min_pct"] is not None and inter < it["min_pct"]:
            removed.append((it["name"], f"needs at least {it['min_pct']:g}% in Inter"))
        else:
            kept.append(it)
    return kept, removed


def f_budget(items, wm, kb):
    top = BUDGET_MAX_BAND[wm.value("budget")]
    kept, removed = [], []
    for it in items:
        band = it["fee_band"]
        if band in FEE_ORDER and FEE_ORDER[band] <= top:
            kept.append(it)
        elif band not in FEE_ORDER and wm.value("budget") == "high":
            it["tags"].append("fee not confirmed")
            kept.append(it)
        else:
            why = "fee not confirmed" if band not in FEE_ORDER else f"{band} fee is above your budget"
            removed.append((it["name"], why))
    return kept, removed


def f_city(items, wm, kb):
    cities = set(wm.value("pref_cities", []) or [])
    if wm.has("home_city"):
        cities.add(wm.value("home_city"))
    if not cities:
        return items, []
    not_sure = wm.value("relocate") == "notsure"
    kept, removed = [], []
    for it in items:
        if it["city"] in cities:
            kept.append(it)
        elif not_sure:
            it["tags"].append("outside your cities")
            kept.append(it)
        else:
            removed.append((it["name"], f"in {it['city']}, outside your cities"))
    # your own cities first
    kept.sort(key=lambda it: it["city"] not in cities)
    return kept, removed


def f_hostel(items, wm, kb):
    sure = wm.value("hostel") == "yes"
    kept, removed = [], []
    for it in items:
        if it["hostel"] in ("yes", "limited"):
            kept.append(it)
        elif sure:
            removed.append((it["name"], "no hostel confirmed"))
        else:
            it["tags"].append("check hostel")
            kept.append(it)
    return kept, removed


def f_women(items, wm, kb):
    if wm.value("women_only") == "yes":
        kept = [it for it in items if it["women_only"]]
        removed = [(it["name"], "not a women's university") for it in items if not it["women_only"]]
        return kept, removed
    # Not sure: women's universities first
    return sorted(items, key=lambda it: not it["women_only"]), []


def f_sector(items, wm, kb):
    want = wm.value("sector")
    kept = [it for it in items if it["sector"] == want]
    removed = [(it["name"], f"{it['sector']} sector") for it in items if it["sector"] != want]
    return kept, removed


FILTERS = {"min_pct": f_min_pct, "budget": f_budget, "city": f_city,
           "hostel": f_hostel, "women": f_women, "sector": f_sector}


def apply_steps(base, steps, wm, kb):
    items = [dict(it, tags=list(it["tags"])) for it in base]
    removed = []
    for s in steps:
        items, r = FILTERS[s](items, wm, kb)
        removed += r
    return items, removed


def relax(f, fid, wm, kb, rid):
    """UN08: relax city first, then budget, then both. Never relax min_pct."""
    steps = f.meta["steps"]
    options = [["city"], ["budget"], ["city", "budget"]]
    for drop in options:
        if not all(d in steps for d in drop):
            continue
        items, removed = apply_steps(f.meta["base"], [s for s in steps if s not in drop], wm, kb)
        if items:
            f.value = items
            f.meta["removed"] = removed
            f.meta["relaxed"] = drop
            f.source_rules.append(rid)
            words = " and ".join({"city": "your city choice", "budget": "your budget"}[d] for d in drop)
            text = f"No university matched all your choices, so {words} was relaxed."
            wm.notes.append((rid, fid, text))
            return [f"unis.{fid}: relaxed {drop} -> {len(items)}"]
    wm.notes.append((rid, fid, "No university in our list matches, even after relaxing city and budget."))
    return [f"unis.{fid}: still empty"]


# ---- G8 decisions ----

def _recommend(act, rid, bind, match, cf, wm, kb):
    n = act["recommend"]
    fid, fcf = ranked_suits(wm, kb)[n - 1]
    wm.result.setdefault("top", []).append(fid)
    return [f"recommendation #{n} = {fid} ({label(fcf, kb.threshold_values())}, CF {fcf:.3f})"]


def _advice(act, rid, bind, match, cf, wm, kb):
    text = fill(act["advice"], wm, kb)
    wm.result.setdefault("advice", []).append((rid, text))
    return [f"advice: {text[:60]}"]


def _action_plan(act, rid, bind, match, cf, wm, kb):
    by_step = {}
    for fid in wm.result.get("top", []):
        e = wm.get(f"elig.{fid}")
        if e and e.value == "conditional":
            for p in e.meta.get("plans", []):
                by_step.setdefault(p.rstrip("."), []).append(kb.fields[fid]["name"])
    plan = [f"{p} ({', '.join(names)})." for p, names in by_step.items()]
    wm.result["action_plan"] = plan
    return [f"action plan with {len(plan)} steps"]


def _like_but_not_eligible(act, rid, bind, match, cf, wm, kb):
    f = kb.fields[bind]
    alts = []
    for a in f.get("alternatives", []):
        e = wm.get(f"elig.{a}")
        if e and e.value in STATUS_RANK:
            alts.append(kb.fields[a]["name"])
    reason = wm.get(f"elig.{bind}").meta["reasons"][0]
    text = f"You seem to like {f['name']}, but you are not eligible. {reason}"
    text += f" Closest options you are eligible for: {', '.join(alts)}." if alts else " We found no close option you are eligible for right now."
    wm.result.setdefault("like_but_not", []).append((bind, text))
    return [f"RC07 message for {bind}"]


def _summary(act, rid, bind, match, cf, wm, kb):
    from engine.explanation import summary_text
    wm.result["summary"] = summary_text(wm, kb)
    return ["summary written"]


HANDLERS = {
    "add_missing": _add_missing, "halt": _halt, "ignore": _ignore, "warn": _warn,
    "assert": _assert, "set": _set, "note": _note, "eligibility": _eligibility,
    "suit": _suit, "uni": _uni, "recommend": _recommend, "advice": _advice,
    "action_plan": _action_plan, "like_but_not_eligible": _like_but_not_eligible,
    "summary": _summary,
}
