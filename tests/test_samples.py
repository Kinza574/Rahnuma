from engine.consult import run_consultation


def top_ids(r):
    return [t["id"] for t in r.top]


def test_ayesha(results, kb):
    r = results["Ayesha"]
    assert top_ids(r)[0] == "mbbs"
    assert {"nursing", "pharmd"} <= set(top_ids(r))
    for fid in ("ee", "me", "civil"):
        assert r.eligibility[fid]["status"] == "conditional"
        assert any("PEC" in x for x in r.eligibility[fid]["reasons"])
    karachi = [u for u in r.universities["mbbs"]["items"] if u["city"] == "Karachi"]
    assert karachi
    assert all(u["fee_band"] in ("low", "medium") for u in karachi)


def test_hamza(results, kb):
    r = results["Hamza"]
    assert top_ids(r)[:2] == ["cs", "se"]
    assert r.top[0]["label"] == "Very likely"
    ee = r.wm.get("suit.ee")
    assert ee is None or ee.cf < kb.t("min_show_cf")
    for fid in ("mbbs", "bds", "pharmd", "dpt", "nursing"):
        assert r.eligibility[fid]["status"] == "not_eligible"


def test_sana(results, kb):
    r = results["Sana"]
    assert {"media", "law"} <= set(top_ids(r))
    assert r.eligibility["law"]["status"] == "conditional"
    assert any("HEC LAT" in p for p in r.action_plan)
    for fid in ("media", "law"):
        items = r.universities[fid]["items"]
        assert items
        assert all(u["women_only"] and u["sector"] == "public" for u in items)
        assert any(u["uni_id"] == "fjwu" for u in items)


def test_bilal(results, kb):
    r = results["Bilal"]
    assert top_ids(r)[0] == "bba"
    assert r.profile["band"] == "Low"
    assert "Pre-Medical" in r.eligibility["mbbs"]["reasons"][0]
    rc07 = dict(r.like_but_not)
    assert "mbbs" in rc07 and "Closest options you are eligible for" in rc07["mbbs"]
    assert not set(top_ids(r)) & {"mbbs", "bds", "pharmd", "dpt", "nursing"}


def test_zara(results, kb):
    r = results["Zara"]
    assert top_ids(r)[0] == "arch"
    assert any("Part-I" in w for w in r.warnings)
    assert r.eligibility["arch"]["status"] == "conditional" or r.top[0]["cf"] < 0.9 * kb.t("part1_cf")
    assert "civil" in top_ids(r)


def test_what_if_ayesha_low_mdcat(samples, kb):
    r = run_consultation(dict(samples["Ayesha"], mdcat_pct=40), kb)
    assert r.eligibility["mbbs"]["status"] == "not_eligible"
    assert r.eligibility["bds"]["status"] == "not_eligible"
    assert "mbbs" not in top_ids(r)


def test_what_if_sana_passes_lat(samples, kb):
    a = dict(samples["Sana"], lat_pct=60, lat_pct_not_taken=False)
    r = run_consultation(a, kb)
    assert r.eligibility["law"]["status"] == "eligible"


def test_summary_written(results):
    for r in results.values():
        assert r.summary
