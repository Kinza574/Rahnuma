from conftest import make_kb, rule

from engine.consult import run_consultation
from engine.inference import Engine
from engine.working_memory import WorkingMemory


def start(facts):
    wm = WorkingMemory()
    for name in facts:
        wm.add(name, True, 1.0, "input")
    return wm


def fired(trace):
    return [s["instance"] for s in trace]


def test_priority_wins():
    kb = make_kb([rule("A1", {"fact": "x", "exists": True}, [{"assert": "a"}], priority=10),
                  rule("Z9", {"fact": "x", "exists": True}, [{"assert": "z"}], priority=20)])
    assert fired(Engine(kb).run(start(["x"])))[0] == "Z9"


def test_specificity_wins_at_same_priority():
    kb = make_kb([rule("A1", {"fact": "x", "exists": True}, [{"assert": "a"}]),
                  rule("Z9", {"all": [{"fact": "x", "exists": True}, {"fact": "y", "exists": True}]}, [{"assert": "z"}])])
    assert fired(Engine(kb).run(start(["x", "y"])))[0] == "Z9"


def test_smaller_id_wins_last():
    kb = make_kb([rule("B2", {"fact": "x", "exists": True}, [{"assert": "b"}]),
                  rule("B1", {"fact": "x", "exists": True}, [{"assert": "a"}])])
    assert fired(Engine(kb).run(start(["x"]))) == ["B1", "B2"]


def test_refraction_rule_fires_once():
    # This rule would loop forever without refraction: its THEN keeps its IF true.
    kb = make_kb([rule("L1", {"fact": "x", "exists": True}, [{"assert": "x"}])])
    trace = Engine(kb).run(start(["x"]))
    assert fired(trace) == ["L1"]


def test_cycle_cap_stops_engine():
    rules = [rule(f"R{i}", {"fact": "x", "exists": True}, [{"assert": f"y{i}"}]) for i in range(10)]
    kb = make_kb(rules, {"max_cycles": 3})
    wm = start(["x"])
    trace = Engine(kb).run(wm)
    assert len(trace) == 3
    assert wm.result.get("cap_hit")
    assert any("safety cap" in w for _, w in wm.warnings)


def test_forward_chaining_derives_new_facts():
    kb = make_kb([rule("C1", {"fact": "b", "exists": True}, [{"assert": "c"}]),
                  rule("B1", {"fact": "a", "exists": True}, [{"assert": "b"}])])
    wm = start(["a"])
    assert fired(Engine(kb).run(wm)) == ["B1", "C1"]
    assert wm.has("c")


def test_agreeing_rules_combine_cf():
    kb = make_kb([rule("A1", {"fact": "x", "exists": True}, [{"assert": "y"}], cf=0.6),
                  rule("A2", {"fact": "x", "exists": True}, [{"assert": "y"}], cf=0.5)])
    wm = start(["x"])
    Engine(kb).run(wm)
    assert abs(wm.get("y").cf - 0.8) < 1e-9


def test_empty_input_is_insufficient(kb):
    r = run_consultation({}, kb)
    assert r.status == "insufficient"
    assert r.missing
    assert r.halted
    assert r.top == []
    assert r.trace[-1]["rule"] == "DS06"


def test_blank_inter_is_missing_but_zero_is_data(kb, samples):
    a = dict(samples["Hamza"])
    a["inter_pct"] = None
    r = run_consultation(a, kb)
    assert r.status == "insufficient"
    assert "Intermediate marks (%)" in r.missing

    a["inter_pct"] = 0
    r = run_consultation(a, kb)
    assert r.status == "ok"
    assert r.profile["band"] == "Very low"
    assert all(e["status"] == "not_eligible" for e in r.eligibility.values())
    assert r.top == []


def test_every_schema_instance_fires_at_most_once(results):
    for r in results.values():
        ids = fired(r.trace)
        assert len(ids) == len(set(ids))


def test_trace_has_cf_calculations(results):
    step = next(s for s in results["Hamza"].trace if s["rule"] == "FM01")
    assert "x min(" in step["cf_text"]
    assert step["matched"]


def test_sanity_ignore_keeps_value_visible(kb, samples):
    # Quick Diagnosis shows all questions, so an ICS student can type an MDCAT score.
    a = dict(samples["Zara"], mdcat_pct=70, mdcat_pct_not_taken=False)
    r = run_consultation(a, kb, use_ask_if=False)
    assert any("MDCAT 70 ignored because your stream is ICS" in w for w in r.warnings)
    assert any("ignored mdcat_pct = 70" in x for s in r.trace for x in s["added"])
    assert not r.wm.has("mdcat_pct")


def test_out_of_range_test_is_treated_as_not_taken(kb, samples):
    a = dict(samples["Zara"], ecat_pct=140, ecat_pct_not_taken=False)
    r = run_consultation(a, kb)
    assert any("ECAT 140 ignored" in w for w in r.warnings)
    assert not r.wm.has("ecat_pct")
