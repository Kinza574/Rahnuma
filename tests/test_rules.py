import copy

from engine.conditions import count_leaves, resolve, threshold_keys
from knowledge_base.kb_loader import check_threshold_order, validate


def test_rule_ids_unique_and_count(kb):
    ids = [r["id"] for r in kb.rules]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 50
    assert len(ids) == 90


def test_compute_and_decision_counts(kb):
    c = kb.counts()
    assert (c["total"], c["compute"], c["decision"]) == (90, 55, 35)


def test_every_rule_has_required_parts(kb):
    for r in kb.rules:
        assert r["group"] and r["text"] and r["type"] in ("compute", "decision")
        assert isinstance(r["priority"], int)
        cf = resolve(r["cf"], kb, None)
        assert 0 < cf <= 1, r["id"]


def test_threshold_keys_exist(kb):
    for r in kb.rules:
        for k in threshold_keys(r):
            assert k in kb.thresholds, f"{r['id']} uses unknown @{k}"


def _numbers(obj):
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [obj]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in _numbers(v)]
    return []


def test_no_numeric_literals_in_conditions(kb):
    for r in kb.rules:
        assert _numbers(r["if"]) == [], f"{r['id']} has a number in its conditions"


def test_leaf_conditions_at_least_50(kb):
    assert sum(count_leaves(r["if"]) for r in kb.rules) >= 50


def test_kb_files_validate(kb):
    assert validate(kb) == []


def test_threshold_order_passes_on_shipped_file(kb):
    assert check_threshold_order(kb.threshold_values()) == []


def test_threshold_order_fails_on_broken_copy(kb):
    v = copy.deepcopy(kb.threshold_values())
    v["band_good"] = 85          # above band_excellent
    v["mdcat_pass_bds"] = 60     # above the MBBS mark
    v["notsure_cf"] = 1.5        # not a CF
    errors = check_threshold_order(v)
    assert len(errors) >= 3


def test_exclusive_g8_rules_have_different_priorities(kb):
    g8 = [r["priority"] for r in kb.rules if r["group"] == "G8"]
    assert len(g8) == len(set(g8))


def test_every_question_is_used_or_shown(kb):
    used = {a for r in kb.rules for a in r["asks"]}
    for q in kb.questions:
        if q["id"] not in ("priority", "board"):
            assert q["id"] in used, q["id"]
