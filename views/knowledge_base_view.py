"""Knowledge Base page: all rules, counts and a rule inspector."""

import json

import pandas as pd
import streamlit as st

from engine.conditions import count_leaves, threshold_keys
from engine.explanation import condition_text
from ui import components as c
from ui import state


def render():
    kb = state.kb()
    c.page_title("Knowledge Base", "All 90 rules, their conditions and the thresholds they use")
    c.expert_note()
    counts = kb.counts()
    m = st.columns(4)
    m[0].metric("Rules", counts["total"])
    m[1].metric("Compute rules", counts["compute"])
    m[2].metric("Decision rules", counts["decision"])
    m[3].metric("Leaf conditions", counts["leaf_conditions"])
    c.muted("Counts are worked out from rules.json. A schema rule (FOR EACH field) counts as one rule.")

    groups = sorted({(r["group"], r["group_name"]) for r in kb.rules})
    labels = ["All groups"] + [f"{g} — {n}" for g, n in groups]
    pick = st.selectbox("Group", labels)
    rows = [r for r in kb.rules if pick == "All groups" or pick.startswith(r["group"] + " ")]
    df = pd.DataFrame([{
        "ID": r["id"], "Group": f"{r['group']} {r['group_name']}", "Type": r["type"], "Priority": r["priority"],
        "CF": str(r["cf"]), "Conditions": count_leaves(r["if"]), "Rule": r["text"],
    } for r in rows])
    st.dataframe(df, hide_index=True, width="stretch", height=420,
                 column_config={"Rule": st.column_config.TextColumn(width="large")})

    c.section("Rule inspector")
    rid = st.selectbox("Rule", [r["id"] for r in kb.rules], index=None, placeholder="Choose a rule ID")
    if rid:
        inspect(kb, kb.rule_by_id[rid])
    c.footer()


def inspect(kb, r):
    st.markdown(f"**{r['id']}** · {r['group']} {r['group_name']} · {r['type']} · priority {r['priority']} · CF {r['cf']}"
                + (" · schema rule (one instance per field)" if r.get("for_each") else ""))
    st.write(r["text"])
    left, right = st.columns(2)
    with left:
        st.markdown("**IF (conditions)**")
        st.code("\n".join(condition_text(r["if"], kb)), language=None)
    with right:
        st.markdown("**THEN (actions)**")
        st.code(json.dumps(r["then"], indent=1, ensure_ascii=False), language="json")
    keys = list(dict.fromkeys(threshold_keys(r)))
    if keys:
        st.markdown("**Thresholds used (current values)**")
        st.dataframe(pd.DataFrame([{"Key": k, "Value": str(kb.t(k)), "Source": kb.thresholds[k].get("source", "")} for k in keys]),
                     hide_index=True, width="stretch")
    asks = r.get("asks", [])
    st.markdown("**Used by questions:** " + (", ".join(f"{a} ({kb.question_by_id[a]['label']})" for a in asks) if asks else "none (uses derived facts only)"))
