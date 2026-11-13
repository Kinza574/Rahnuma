from pytest import approx

from engine.certainty import combine, conclude, label


def test_combine_agreeing_evidence():
    assert combine(0.6, 0.5) == approx(0.8)
    assert combine(0.0, 0.7) == approx(0.7)
    assert combine(1.0, 0.3) == approx(1.0)


def test_combine_order_does_not_matter():
    assert combine(0.3, 0.9) == approx(combine(0.9, 0.3))


def test_rule_cf_times_min():
    assert conclude(0.9, [1.0, 0.85]) == approx(0.765)
    assert conclude(0.85, [0.5, 1.0]) == approx(0.425)
    assert conclude(0.2, []) == approx(0.2)


def test_labels_follow_thresholds(kb):
    t = kb.threshold_values()
    assert label(t["label_very_likely"], t) == "Very likely"
    assert label(t["label_likely"], t) == "Likely"
    assert label(t["min_show_cf"], t) == "Possible"
    assert label(t["min_show_cf"] - 0.01, t) is None
