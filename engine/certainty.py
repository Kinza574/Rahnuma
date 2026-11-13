"""MYCIN certainty factor maths and CF labels.

All CFs in this project are between 0 and 1 (no negative evidence).
"""


def combine(cf1, cf2):
    """Combine two agreeing CFs for the same fact: CF1 + CF2 x (1 - CF1)."""
    return cf1 + cf2 * (1 - cf1)


def conclude(rule_cf, fact_cfs):
    """Conclusion CF = rule CF x min(CF of the matched facts)."""
    if not fact_cfs:
        return rule_cf
    return rule_cf * min(fact_cfs)


def label(cf, thresholds):
    """Turn a CF into words. Returns None when the CF is too low to show."""
    if cf >= thresholds["label_very_likely"]:
        return "Very likely"
    if cf >= thresholds["label_likely"]:
        return "Likely"
    if cf >= thresholds["min_show_cf"]:
        return "Possible"
    return None

