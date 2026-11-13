"""One entry point for a consultation: run_consultation(answers, kb) -> Result."""

from dataclasses import dataclass, field

from engine.conditions import evaluate
from engine.explanation import plain_steps, reasons_for, word
from engine.inference import Engine
from engine.working_memory import WorkingMemory


@dataclass
class Result:
    """Everything the pages need to show one consultation."""
    status: str = "ok"                 # "ok" or "insufficient"
    missing: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    eligibility: dict = field(default_factory=dict)
    top: list = field(default_factory=list)
    universities: dict = field(default_factory=dict)
    job_outlook: dict = field(default_factory=dict)
    profile: dict = field(default_factory=dict)
    advice: list = field(default_factory=list)
    action_plan: list = field(default_factory=list)
    like_but_not: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    summary: str = ""
    trace: list = field(default_factory=list)
    halted: bool = False
    wm: object = None


def visible_questions(answers, kb, use_ask_if=True):
    """Questions whose ask_if is true for the earlier answers, in order.

    The Counsellor Desk shows every question, so it passes use_ask_if=False and the
    sanity rules (G1) catch answers that do not fit the stream.
    """
    wm = WorkingMemory()
    shown = []
    for q in kb.questions:
        cond = q.get("ask_if")
        if not use_ask_if or cond is None or evaluate(cond, wm, kb).ok:
            shown.append(q)
            add_input(wm, q, answers, kb)
    return shown


def add_input(wm, q, answers, kb):
    """Turn one answer into a fact. Tri: Yes = CF 1, Not sure = notsure_cf, No = no fact."""
    qid, value = q["id"], answers.get(q["id"])
    if q["type"] == "tri":
        if value == "yes":
            wm.add(qid, "yes", 1.0, "input")
        elif value == "notsure":
            wm.add(qid, "notsure", kb.t("notsure_cf"), "input")
    elif q["type"] in ("number", "test"):
        # a blank box is missing data, but 0 is a real answer
        if value is not None and value != "" and not answers.get(f"{qid}_not_taken"):
            wm.add(qid, float(value), 1.0, "input")
    elif q["type"] == "multiselect":
        if value:
            wm.add(qid, list(value), 1.0, "input")
    elif value not in (None, ""):
        wm.add(qid, value, 1.0, "input")


def build_memory(answers, kb, use_ask_if=True):
    """Turn the answers into input facts for working memory."""
    wm = WorkingMemory()
    shown = visible_questions(answers, kb, use_ask_if)
    for q in shown:
        add_input(wm, q, answers, kb)
    answered = sum(1 for q in shown if q.get("group") in ("interest", "skill") and answers.get(q["id"]) in ("yes", "no", "notsure"))
    wm.add("answered_count", answered, 1.0, "input")
    if wm.has("inter_pct") and wm.has("matric_pct"):
        wm.add("marks_gap", abs(wm.value("inter_pct") - wm.value("matric_pct")), 1.0, "input")
    return wm


def run_consultation(answers, kb, use_ask_if=True):
    """Run the engine on the answers and package the result."""
    wm = build_memory(answers, kb, use_ask_if)
    trace = Engine(kb).run(wm)
    r = Result(trace=trace, wm=wm, halted=wm.halted)
    r.warnings = [text for _, text in wm.warnings]
    if wm.result.get("status") == "insufficient":
        r.status = "insufficient"
        # list missing items in rule order (DS01 stream, DS02 Inter %, ...)
        order = [a["add_missing"] for rr in kb.rules for a in rr["then"] if "add_missing" in a]
        r.missing = sorted(wm.value("missing", []), key=lambda m: order.index(m) if m in order else len(order))
        return r

    for fid, f in kb.fields.items():
        e = wm.get(f"elig.{fid}")
        if e:
            r.eligibility[fid] = {"status": e.value, "cf": e.cf, "reasons": e.meta.get("reasons", []),
                                  "notes": e.meta.get("notes", []), "plans": e.meta.get("plans", []),
                                  "rules": e.source_rules}
    for fid in wm.result.get("top", []):
        s = wm.get(f"suit.{fid}")
        e = r.eligibility.get(fid, {})
        r.top.append({"id": fid, "name": kb.fields[fid]["name"], "cf": s.cf, "label": word(s.cf, kb),
                      "status": e.get("status"), "reasons": reasons_for(fid, wm, kb),
                      "conditions": e.get("reasons", []) if e.get("status") == "conditional" else [],
                      "notes": e.get("notes", []), "rules": s.source_rules})
    for n, f in wm.facts.items():
        if n.startswith("unis."):
            fid = n[5:]
            r.universities[fid] = {"items": f.value, "removed": f.meta.get("removed", []),
                                   "relaxed": f.meta.get("relaxed", []),
                                   "notes": [t for _, b, t in wm.notes if b == fid and t.startswith("No ")]}
    for t in r.top:
        m = kb.market["fields"][t["id"]]
        r.job_outlook[t["id"]] = dict(m, notes=[x for _, b, x in wm.notes if b == t["id"] and x.startswith("Fewer")])
    r.advice = [t for _, t in wm.result.get("advice", [])]
    r.action_plan = wm.result.get("action_plan", [])
    r.like_but_not = wm.result.get("like_but_not", [])
    r.notes = [t for _, _, t in wm.notes]
    r.summary = wm.result.get("summary", "")
    r.profile = profile(wm, r, kb)
    return r


def profile(wm, r, kb):
    """The 'diagnosis': marks band, aptitudes, eligibility conditions met or missed."""
    apts = sorted(((kb.aptitudes[n], f.cf) for n, f in wm.facts.items() if n in kb.aptitudes), key=lambda a: -a[1])
    met, by_reason = [], {}
    for fid, e in r.eligibility.items():
        name = kb.fields[fid]["name"]
        if e["status"] == "eligible":
            met.append(name)
        elif e["status"] == "conditional":
            by_reason.setdefault("; ".join(e["reasons"]), []).append(name)
    # fields that share a reason are grouped: "EE, ME, Civil: PEC lets ..."
    missed = [f"{', '.join(names)}: {reason}" for reason, names in by_reason.items()]
    not_elig = [kb.fields[f]["name"] for f, e in r.eligibility.items() if e["status"] == "not_eligible"]
    return {
        "band": wm.value("inter_band"),
        "marks_reliable": wm.get("marks_reliable").cf if wm.has("marks_reliable") else None,
        "aptitudes": [(n, cf, word(cf, kb)) for n, cf in apts],
        "eligible": met,
        "conditional": missed,
        "not_eligible": not_elig,
    }


def complete_answers(partial, kb):
    """Fill a sample: unlisted Yes/No questions become No, unlisted tests 'Not taken yet'."""
    answers = dict(partial)
    for q in kb.questions:
        if q["id"] in answers:
            continue
        if q["type"] == "tri":
            answers[q["id"]] = "no"
        elif q["type"] == "test":
            answers[q["id"]] = None
            answers[f"{q['id']}_not_taken"] = True
    return answers


def load_samples(path=None):
    """Read the five sample students."""
    import json
    from pathlib import Path
    path = path or Path(__file__).parent.parent / "samples" / "sample_students.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["students"]


def steps(result, kb, technical=False):
    """The trace as plain-English lines."""
    return plain_steps(result.trace, kb, technical)
