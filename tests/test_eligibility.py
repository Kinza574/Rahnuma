import random

from engine.consult import complete_answers, run_consultation

MEDICAL = {"mbbs", "bds", "pharmd", "dpt", "nursing"}
ENGINEERING = {"ee", "me", "civil"}


def test_not_sure_fires_with_half_cf(kb, results):
    # Zara answered Not sure to computers: apt_computing = 0.9 x 0.5
    f = results["Zara"].wm.get("apt_computing")
    assert abs(f.cf - 0.9 * kb.t("notsure_cf")) < 1e-9


def test_uncertain_qualification_gives_conditional(kb, samples):
    a = dict(samples["Zara"], inter_status="final", has_physics="notsure")
    r = run_consultation(a, kb)
    for fid in ENGINEERING:
        e = r.eligibility[fid]
        assert e["status"] == "conditional"
        assert any("Physics" in x for x in e["reasons"])


def test_uncertain_answer_never_makes_eligible(kb, samples):
    # Commerce student says Not sure to Maths: CS must stay conditional, never eligible
    a = dict(samples["Bilal"], has_maths="notsure")
    r = run_consultation(a, kb)
    assert r.eligibility["cs"]["status"] == "conditional"


def test_part1_makes_fields_conditional(results):
    for fid, e in results["Zara"].eligibility.items():
        assert e["status"] in ("conditional", "not_eligible")


def random_answers(kb, rng):
    a = {}
    for q in kb.questions:
        t = q["type"]
        if t == "tri":
            a[q["id"]] = rng.choice(["yes", "no", "notsure"])
        elif t == "select":
            a[q["id"]] = rng.choice([o["value"] for o in kb.options(q["id"])])
        elif t == "multiselect":
            a[q["id"]] = rng.sample(kb.cities, rng.randint(0, 2))
        elif t == "number":
            a[q["id"]] = rng.choice([0, 30, 44.9, 45, 50, 55, 59.9, 60, 65, 72, 80, 95, 100])
        elif t == "test":
            if rng.random() < 0.4:
                a[q["id"]] = None
                a[f"{q['id']}_not_taken"] = True
            else:
                a[q["id"]] = rng.choice([20, 40, 49, 50, 54.9, 55, 70, 90]) if q["id"] != "sat_score" else rng.choice([900, 1300])
    return a


def test_eligibility_never_violated_random(kb):
    rng = random.Random(7)
    checked = 0
    for _ in range(150):
        a = random_answers(kb, rng)
        r = run_consultation(a, kb)
        if r.status != "ok":
            continue
        checked += 1
        wm = r.wm
        suits = {n[5:] for n in wm.facts if n.startswith("suit.")}
        top = {t["id"] for t in r.top}
        for fid, e in r.eligibility.items():
            if e["status"] == "not_eligible":
                assert fid not in suits and fid not in top
        stream = a["stream"]
        if stream != "pre_med":
            assert not (suits & MEDICAL), "medical field without Pre-Medical"
        if stream in ("commerce", "humanities", "gen_sci"):
            assert not (suits & ENGINEERING), "engineering without the right stream"
        lat = wm.value("lat_pct")
        if lat is not None and lat < kb.t("lat_pass"):
            assert r.eligibility["law"]["status"] == "not_eligible"
        if wm.value("inter_pct") < kb.t("cs_min"):
            assert "cs" not in suits
        for fid, e in r.eligibility.items():
            if e["status"] == "eligible":
                assert e["cf"] == 1.0
    assert checked > 50


def test_mbbs_without_pre_med_is_not_eligible(results):
    e = results["Bilal"].eligibility["mbbs"]
    assert e["status"] == "not_eligible"
    assert "Pre-Medical" in e["reasons"][0]
