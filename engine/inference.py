"""Forward-chaining inference engine.

Each cycle:
  1. Match: find rules (and schema-rule instances) whose IF part is true
     and that have not fired yet (refraction).
  2. Conflict resolution: higher priority first, then more conditions
     (specificity), then the smaller rule ID.
  3. Act: fire the winning rule, record a trace step, repeat.
The engine stops when nothing matches, when a rule says HALT,
or when the cycle cap (max_cycles) is reached.
"""

from engine import actions
from engine.certainty import conclude
from engine.conditions import count_leaves, evaluate, resolve


class Engine:
    def __init__(self, kb):
        self.kb = kb
        # Sort once by priority so matching can stop at the first level with a match.
        self.rules = sorted(kb.rules, key=lambda r: -r["priority"])
        self.leaves = {r["id"]: count_leaves(r["if"]) for r in kb.rules}

    def instances(self, rule):
        """A normal rule has one instance; a schema rule has one per field."""
        if rule.get("for_each") == "field":
            return [(f"{rule['id']}[{fid}]", fid) for fid in self.kb.fields]
        return [(rule["id"], None)]

    def conflict_set(self, wm, fired):
        """All matching, not-yet-fired instances at the highest priority that has any.

        Lower-priority rules can never win against them, so we stop looking there.
        """
        found, level = [], None
        for rule in self.rules:
            if level is not None and rule["priority"] < level:
                break
            for iid, bind in self.instances(rule):
                if iid in fired:
                    continue
                m = evaluate(rule["if"], wm, self.kb, bind)
                if m.ok:
                    found.append((rule, iid, bind, m))
                    level = rule["priority"]
        return found

    def resolve_conflict(self, found):
        order = list(self.kb.fields)
        return sorted(
            found,
            key=lambda x: (
                -x[0]["priority"],
                -self.leaves[x[0]["id"]],
                x[0]["id"],
                order.index(x[2]) if x[2] else -1,
            ),
        )

    def run(self, wm):
        fired, trace = set(), []
        max_cycles = int(self.kb.t("max_cycles"))
        cycle = 0
        while True:
            if cycle >= max_cycles:
                wm.warnings.append(("ENGINE", f"Stopped after {max_cycles} cycles (safety cap)."))
                wm.result["cap_hit"] = True
                break
            found = self.conflict_set(wm, fired)
            if not found:
                break
            cycle += 1
            ranked = self.resolve_conflict(found)
            rule, iid, bind, match = ranked[0]
            fired.add(iid)
            rule_cf = resolve(rule["cf"], self.kb, bind)
            cf = conclude(rule_cf, match.cfs)
            step = {
                "cycle": cycle,
                "rule": rule["id"],
                "instance": iid,
                "field": bind,
                "group": rule["group"],
                "priority": rule["priority"],
                "conflict_set": [x[1] for x in ranked],
                "matched": match.used,
                "cf": cf,
                "cf_text": cf_text(rule_cf, match.cfs, cf),
                "added": [],
            }
            for act in rule["then"]:
                step["added"] += actions.execute(act, rule, bind, match, cf, wm, self.kb)
            trace.append(step)
            if wm.halted:
                break
        return trace


def cf_text(rule_cf, cfs, cf):
    if not cfs:
        return f"{rule_cf:g}"
    inner = ", ".join(f"{c:.3g}" for c in cfs)
    return f"{rule_cf:g} x min({inner}) = {cf:.3f}"
