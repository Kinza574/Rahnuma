import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.consult import complete_answers, load_samples, run_consultation  # noqa: E402
from knowledge_base.kb_loader import KB, load_kb  # noqa: E402


@pytest.fixture(scope="session")
def kb():
    return load_kb()


@pytest.fixture(scope="session")
def samples(kb):
    return {s["name"]: complete_answers(s["answers"], kb) for s in load_samples()}


@pytest.fixture(scope="session")
def results(kb, samples):
    return {name: run_consultation(a, kb) for name, a in samples.items()}


def make_kb(rules, thresholds=None):
    """A tiny synthetic knowledge base for engine tests."""
    th = {"max_cycles": 500, "conditional_cf": 0.7, "notsure_cf": 0.5}
    th.update(thresholds or {})
    data = {
        "rules": {"rules": rules},
        "thresholds": {"thresholds": {k: {"value": v} for k, v in th.items()}},
        "questions": {"questions": [], "steps": [], "cities": [], "confirm_texts": {}},
        "fields": {"fields": {}, "aptitudes": {}},
        "universities": {"universities": []},
        "market_data": {"fields": {}},
    }
    return KB(data)


def rule(id, cond, then, priority=10, cf=1.0):
    return {"id": id, "group": "G3", "group_name": "Test", "type": "compute", "priority": priority,
            "cf": cf, "text": id, "if": cond, "then": then}
