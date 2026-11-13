"""Condition evaluation for rules.

Condition language (kept small on purpose):
  groups:  all, any, not
  leaves:  {"fact": name, <op>: value}
           {"kb": "market.pk", <op>: value}   (schema rules: data about the current field)
           {"query": name, ...}                (a few named checks used by G8)
  ops:     eq, in, is, gte, gt, lt, between (lower included, upper excluded),
           exists, missing, empty
  values:  "@key" reads thresholds.json, "$F" is the current field in schema rules.
"""

from dataclasses import dataclass, field

OPS = ("eq", "in", "is", "gte", "gt", "lt", "between", "exists", "missing", "empty")


@dataclass
class Match:
    ok: bool
    cfs: list = field(default_factory=list)    # CFs that go into min()
    used: list = field(default_factory=list)   # (fact name, value, cf) for the trace


def resolve(value, kb, bind):
    """Replace "@key" with the threshold value and "$F" with the bound field."""
    if isinstance(value, str):
        if value.startswith("@"):
            return kb.t(value[1:])
        if bind and "$F" in value:
            return value.replace("$F", bind)
        return value
    if isinstance(value, list):
        return [resolve(v, kb, bind) for v in value]
    return value


def _op_of(leaf):
    for op in OPS:
        if op in leaf:
            return op
    raise ValueError(f"Condition has no known operator: {leaf}")


def compare(op, actual, expected):
    """Compare a value that exists against the expected value."""
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == "is":
        # "is yes" matches Yes and Not sure answers
        return actual in ("yes", "notsure") if expected == "yes" else actual == expected
    if op == "empty":
        return (len(actual) == 0) == bool(expected)
    if not isinstance(actual, (int, float)):
        return False
    if op == "gte":
        return actual >= expected
    if op == "gt":
        return actual > expected
    if op == "lt":
        return actual < expected
    if op == "between":
        return expected[0] <= actual < expected[1]
    return False


def evaluate(cond, wm, kb, bind=None):
    """Evaluate a condition tree against working memory."""
    if "all" in cond:
        cfs, used = [], []
        for part in cond["all"]:
            m = evaluate(part, wm, kb, bind)
            if not m.ok:
                return Match(False)
            cfs += m.cfs
            used += m.used
        return Match(True, cfs, used)

    if "any" in cond:
        best = None
        for part in cond["any"]:
            m = evaluate(part, wm, kb, bind)
            if m.ok and (best is None or min(m.cfs or [1.0]) > min(best.cfs or [1.0])):
                best = m
        return best if best else Match(False)

    if "not" in cond:
        m = evaluate(cond["not"], wm, kb, bind)
        return Match(not m.ok)

    if "query" in cond:
        return QUERIES[cond["query"]](cond, wm, kb, bind)

    op = _op_of(cond)
    expected = resolve(cond[op], kb, bind)

    if "kb" in cond:
        actual = kb_lookup(kb, cond["kb"], bind)
        return Match(actual is not None and compare(op, actual, expected))

    name = resolve(cond["fact"], kb, bind)
    fact = wm.get(name)
    if op == "missing":
        return Match(fact is None)
    if fact is None:
        return Match(False)
    if op == "exists" or compare(op, fact.value, expected):
        # "use_cf": false means the fact is only a trigger (e.g. MK rules update it)
        cfs = [] if cond.get("use_cf") is False else [fact.cf]
        return Match(True, cfs, [(name, fact.value, fact.cf)])
    return Match(False)


def kb_lookup(kb, path, bind):
    """Read data about the current field, e.g. "market.pk"."""
    table, key = path.split(".")
    if table == "market":
        return kb.market["fields"].get(bind, {}).get(key)
    if table == "field":
        return kb.fields[bind].get(key)
    return None


# ---- named queries used by G8 ----

def ranked_suits(wm, kb):
    """Suitable fields sorted by CF (highest first), ties by field order."""
    order = list(kb.fields)
    suits = [(n[5:], f.cf) for n, f in wm.facts.items() if n.startswith("suit.")]
    return sorted(suits, key=lambda s: (-s[1], order.index(s[0])))


POSITIONS = {"first": 1, "second": 2, "third": 3}


def _q_rank(cond, wm, kb, bind):
    """The n-th best suitability CF compared with a threshold."""
    ranked = ranked_suits(wm, kb)
    n = POSITIONS[cond["position"]]
    if len(ranked) < n:
        return Match(False)
    field_id, cf = ranked[n - 1]
    op = "gte" if "gte" in cond else "lt"
    ok = compare(op, cf, resolve(cond[op], kb, bind))
    return Match(ok, [], [(f"suit.{field_id}", "rank " + str(n), cf)] if ok else [])


def _q_best_below(cond, wm, kb, bind):
    """True when no field reaches the threshold."""
    ranked = ranked_suits(wm, kb)
    limit = resolve(cond["lt"], kb, bind)
    return Match(not ranked or ranked[0][1] < limit)


def _q_top_conditional(cond, wm, kb, bind):
    """True when one of the recommended fields is only conditionally eligible."""
    for fid in wm.result.get("top", []):
        e = wm.get(f"elig.{fid}")
        if e and e.value == "conditional":
            return Match(True, [], [(f"elig.{fid}", e.value, e.cf)])
    return Match(False)


def _q_aptitudes_strong(cond, wm, kb, bind):
    """True when every aptitude linked to the field is at least the threshold."""
    keys = kb.fields[bind].get("aptitude_keys", [])
    limit = resolve(cond["gte"], kb, bind)
    used = []
    for k in keys:
        f = wm.get(k)
        if f is None or f.cf < limit:
            return Match(False)
        used.append((k, f.value, f.cf))
    return Match(bool(keys), [], used)


QUERIES = {
    "rank": _q_rank,
    "best_below": _q_best_below,
    "top_conditional": _q_top_conditional,
    "aptitudes_strong": _q_aptitudes_strong,
}


def count_leaves(cond):
    """Number of leaf conditions (used for specificity and the KB page)."""
    for g in ("all", "any"):
        if g in cond:
            return sum(count_leaves(c) for c in cond[g])
    if "not" in cond:
        return count_leaves(cond["not"])
    return 1


def facts_in(cond):
    """All fact names a condition reads (for checks and the rule inspector)."""
    out = []
    for g in ("all", "any"):
        if g in cond:
            for c in cond[g]:
                out += facts_in(c)
            return out
    if "not" in cond:
        return facts_in(cond["not"])
    if "fact" in cond:
        return [cond["fact"]]
    return []


def threshold_keys(obj):
    """All "@key" references inside a rule (conditions or actions)."""
    if isinstance(obj, str):
        return [obj[1:]] if obj.startswith("@") else []
    if isinstance(obj, dict):
        return [k for v in obj.values() for k in threshold_keys(v)]
    if isinstance(obj, list):
        return [k for v in obj for k in threshold_keys(v)]
    return []
