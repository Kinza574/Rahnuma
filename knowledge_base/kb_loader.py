"""Load and check all knowledge-base files.

The KB object is plain Python data. Nothing here imports Streamlit.
"""

import copy
import json
from pathlib import Path

from engine.conditions import count_leaves, threshold_keys

KB_DIR = Path(__file__).parent
FILES = ["rules", "thresholds", "questions", "fields", "universities", "market_data"]
TRI_LABELS = {"yes": "Yes", "no": "No", "notsure": "Not sure"}


class KB:
    def __init__(self, data):
        self.data = data
        self.rules = data["rules"]["rules"]
        self.thresholds = data["thresholds"]["thresholds"]
        self.questions = data["questions"]["questions"]
        self.steps = data["questions"]["steps"]
        self.cities = data["questions"]["cities"]
        self.fields = data["fields"]["fields"]
        self.aptitudes = data["fields"]["aptitudes"]
        self.universities = data["universities"]
        self.market = data["market_data"]
        self.question_by_id = {q["id"]: q for q in self.questions}
        self.rule_by_id = {r["id"]: r for r in self.rules}

    # ---- thresholds ----
    def t(self, key):
        return self.thresholds[key]["value"]

    def threshold_values(self):
        return {k: v["value"] for k, v in self.thresholds.items()}

    # ---- labels ----
    def options(self, qid):
        q = self.question_by_id[qid]
        if q["type"] == "tri":
            return [{"value": v, "label": l} for v, l in TRI_LABELS.items()]
        opts = q.get("options", [])
        if opts == "@cities":
            return [{"value": c, "label": c} for c in self.cities]
        values = {k: f"{v:,}" if isinstance(v, int) and v >= 1000 else v for k, v in self.threshold_values().items()}
        return [{"value": o["value"], "label": o["label"].format(**values)} for o in opts]

    def answer_label(self, name, value):
        """Human text for a fact value (e.g. 'pre_med' -> 'Pre-Medical')."""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if name in self.question_by_id and isinstance(value, str):
            for o in self.options(name):
                if o["value"] == value:
                    return o["label"]
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return value

    def confirm_text(self, fact_name):
        return self.data["questions"]["confirm_texts"].get(fact_name)

    def fact_label(self, name):
        if name in self.aptitudes:
            return self.aptitudes[name]
        if name in self.question_by_id:
            return self.question_by_id[name]["label"]
        if name.startswith(("suit.", "elig.", "unis.")):
            kind, fid = name.split(".", 1)
            word = {"suit": "suits", "elig": "eligibility for", "unis": "universities for"}[kind]
            return f"{word} {self.fields.get(fid, {}).get('name', fid)}"
        return name.replace("_", " ")

    # ---- counts for the KB page ----
    def counts(self):
        return {
            "total": len(self.rules),
            "compute": sum(r["type"] == "compute" for r in self.rules),
            "decision": sum(r["type"] == "decision" for r in self.rules),
            "leaf_conditions": sum(count_leaves(r["if"]) for r in self.rules),
        }

    def copy(self):
        return KB(copy.deepcopy(self.data))


def load_kb(folder=KB_DIR):
    data = {}
    for name in FILES:
        with open(Path(folder) / f"{name}.json", encoding="utf-8") as f:
            data[name] = json.load(f)
    return KB(data)


def check_threshold_order(values):
    """Return a list of plain messages; empty means the thresholds are in order."""
    v = values
    errors = []
    if not (v["band_excellent"] > v["band_good"] > v["band_average"] > v["band_pass"] > 0):
        errors.append("Inter bands must go down: band_excellent > band_good > band_average > band_pass > 0.")
    if not v["mdcat_pass_mbbs"] >= v["mdcat_pass_bds"]:
        errors.append("The MBBS MDCAT pass mark must be at least the BDS pass mark.")
    if not (v["label_very_likely"] > v["label_likely"] > v["min_show_cf"] > 0):
        errors.append("CF words must go down: label_very_likely > label_likely > min_show_cf > 0.")
    if not v["budget_low_max"] < v["budget_medium_max"]:
        errors.append("budget_low_max must be smaller than budget_medium_max.")
    if not v["sat_min"] < v["sat_max"]:
        errors.append("sat_min must be smaller than sat_max.")
    if v["pct_min"] != 0 or v["pct_max"] != 100:
        errors.append("pct_min must be 0 and pct_max must be 100.")
    for key, meta in THRESHOLD_KINDS.items():
        for k in meta:
            x = v.get(k)
            if key == "cf" and not (isinstance(x, (int, float)) and 0 <= x <= 1):
                errors.append(f"{k} is a CF and must be between 0 and 1.")
            if key == "pct" and not (isinstance(x, (int, float)) and 0 <= x <= 100):
                errors.append(f"{k} is a percentage and must be between 0 and 100.")
    return errors


THRESHOLD_KINDS = {
    "cf": ["notsure_cf", "part1_cf", "conditional_cf", "min_show_cf", "label_likely", "label_very_likely",
           "strong_aptitude_cf", "market_high_cf", "abroad_cf"],
    "pct": ["band_excellent", "band_good", "band_average", "band_pass", "med_min", "mdcat_pass_mbbs",
            "mdcat_pass_bds", "pharmd_min", "dpt_min", "nursing_min", "eng_min", "cs_min", "arch_min",
            "design_min", "business_min", "law_min", "lat_pass", "socsci_min", "max_marks_gap"],
}


def validate(kb):
    """Structural checks on all files. Returns a list of problems (empty = fine)."""
    problems = []
    ids = [r["id"] for r in kb.rules]
    if len(ids) != len(set(ids)):
        problems.append("Rule IDs are not unique.")
    for r in kb.rules:
        for key in ("group", "priority", "cf", "type", "text", "if", "then"):
            if key not in r:
                problems.append(f"{r.get('id')} has no '{key}'.")
        for k in threshold_keys(r):
            if k not in kb.thresholds:
                problems.append(f"{r['id']} uses @{k}, which is not in thresholds.json.")
    problems += check_threshold_order(kb.threshold_values())
    for u in kb.universities["universities"]:
        for o in u["offerings"]:
            if o["field"] not in kb.fields:
                problems.append(f"{u['id']} has an offering for unknown field {o['field']}.")
    for fid in kb.fields:
        if fid not in kb.market["fields"]:
            problems.append(f"No market data for {fid}.")
    return problems
