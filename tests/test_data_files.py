def test_as_of_dates(kb):
    assert kb.universities["as_of"]
    assert kb.market["as_of"]


def test_university_offerings_are_complete(kb):
    for u in kb.universities["universities"]:
        assert u["sector"] in ("public", "private")
        assert isinstance(u["women_only"], bool)
        for o in u["offerings"]:
            assert o["field"] in kb.fields
            assert o["fee_band"] in ("low", "medium", "high", "unknown")
            assert o["source_url"].startswith("http")
            assert isinstance(o["verified"], bool)


def test_fee_bands_match_thresholds(kb):
    low, med = kb.t("budget_low_max"), kb.t("budget_medium_max")
    for u in kb.universities["universities"]:
        for o in u["offerings"]:
            fee = o.get("annual_fee_pkr")
            if fee is None:
                continue
            want = "low" if fee <= low else "medium" if fee <= med else "high"
            assert o["fee_band"] == want, (u["id"], o["field"])


def test_cities_are_known(kb):
    for u in kb.universities["universities"]:
        assert u["city"] in kb.cities


def test_every_field_has_universities_and_market_data(kb):
    offered = {o["field"] for u in kb.universities["universities"] for o in u["offerings"]}
    assert offered == set(kb.fields)
    for fid in kb.fields:
        m = kb.market["fields"][fid]
        assert m["pk"] in ("high", "medium", "low") and m["abroad"] in ("high", "medium", "low")
        assert set(m["confidence"]) == {"pk", "abroad"}
