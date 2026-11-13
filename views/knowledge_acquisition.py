"""Knowledge Acquisition page: edit thresholds and data for this session, download/upload JSON."""

import copy
import json

import pandas as pd
import streamlit as st

from knowledge_base.kb_loader import KB, check_threshold_order, validate
from ui import components as c
from ui import state


def render():
    kb = state.kb()
    c.page_title("Knowledge Acquisition", "Edit thresholds and data, check them, then apply for this session")
    c.expert_note()
    c.warning_box("Changes apply to this session only. Streamlit Cloud does not keep files after a restart, so download your changes.")
    if st.session_state.pop("ka_msg", None):
        c.warning_box("Applied for this session. New consultations use the changed knowledge.")
    tabs = st.tabs(["Thresholds", "Universities", "Market data", "Rules"])
    with tabs[0]:
        thresholds_tab(kb)
    with tabs[1]:
        universities_tab(kb)
    with tabs[2]:
        market_tab(kb)
    with tabs[3]:
        rules_tab(kb)
    c.footer()


def apply(new_data):
    new_kb = KB(new_data)
    problems = validate(new_kb)
    if problems:
        for p in problems:
            st.error(p)
        return
    state.set_kb(new_kb)
    st.session_state.ka_msg = True
    st.rerun()


def file_buttons(kb, name, label):
    data = kb.data[name]
    c1, c2 = st.columns(2)
    c1.download_button(f"Download {label} JSON", json.dumps(data, indent=1, ensure_ascii=False), file_name=f"{name}.json",
                       mime="application/json", key=f"ka_dl_{name}")
    up = c2.file_uploader(f"Upload {label} JSON", type="json", key=f"ka_up_{name}")
    if up is not None and st.button(f"Apply uploaded {label}", key=f"ka_apply_up_{name}"):
        try:
            new = copy.deepcopy(kb.data)
            new[name] = json.loads(up.getvalue().decode("utf-8"))
            KB(new)  # structure check
        except (ValueError, KeyError, TypeError) as e:
            st.error(f"That file could not be read: {e}")
            return
        apply(new)


def thresholds_tab(kb):
    c.muted("Edit a value, then press 'Check and apply'. Order checks run first (for example, the Inter bands must go down).")
    rows = [{"Key": k, "Value": json.dumps(v["value"]) if isinstance(v["value"], list) else v["value"],
             "Unit": v.get("unit", ""), "Note": v.get("note", ""), "Source": v.get("source", "")}
            for k, v in kb.thresholds.items()]
    df = pd.DataFrame(rows).astype({"Value": str})
    edited = st.data_editor(df, hide_index=True, width="stretch", disabled=["Key", "Unit", "Source"], key="ka_th")
    if st.button("Check and apply", type="primary", key="ka_th_apply"):
        new = copy.deepcopy(kb.data)
        try:
            for _, row in edited.iterrows():
                new["thresholds"]["thresholds"][row["Key"]]["value"] = json.loads(row["Value"])
                new["thresholds"]["thresholds"][row["Key"]]["note"] = row["Note"]
        except json.JSONDecodeError:
            st.error("Each value must be a number (or a list like [\"pre_med\"]).")
            return
        errors = check_threshold_order({k: v["value"] for k, v in new["thresholds"]["thresholds"].items()})
        if errors:
            st.error("Not applied. Please fix these first:")
            for e in errors:
                st.markdown(f"- {e}")
            return
        apply(new)
    file_buttons(kb, "thresholds", "thresholds")


def universities_tab(kb):
    c.muted(f"Data as of {kb.universities['as_of']}. One row per programme offering. Fee band must be low, medium, high or unknown.")
    rows = []
    for u in kb.universities["universities"]:
        for i, o in enumerate(u["offerings"]):
            rows.append({"uni_id": u["id"], "University": u["name"], "City": u["city"], "Field": o["field"], "_i": i,
                         "Fee band": o["fee_band"], "Min %": o.get("min_pct"), "Verified": o["verified"], "Source": o["source_url"]})
    df = pd.DataFrame(rows)
    edited = st.data_editor(df, hide_index=True, width="stretch", height=420, key="ka_uni",
                            disabled=["uni_id", "University", "City", "Field", "_i"],
                            column_config={"_i": None, "Fee band": st.column_config.SelectboxColumn(options=["low", "medium", "high", "unknown"]),
                                           "Min %": st.column_config.NumberColumn(min_value=0, max_value=100),
                                           "Source": st.column_config.LinkColumn()})
    if st.button("Apply university changes", type="primary", key="ka_uni_apply"):
        new = copy.deepcopy(kb.data)
        by_id = {u["id"]: u for u in new["universities"]["universities"]}
        for _, row in edited.iterrows():
            o = by_id[row["uni_id"]]["offerings"][int(row["_i"])]
            o["fee_band"] = row["Fee band"]
            o["min_pct"] = None if pd.isna(row["Min %"]) else float(row["Min %"])
            o["verified"] = bool(row["Verified"])
            o["source_url"] = row["Source"]
        apply(new)
    file_buttons(kb, "universities", "universities")


def market_tab(kb):
    c.muted(f"Data as of {kb.market['as_of']}. Demand words: high, medium or low.")
    rows = [{"Field": f, "Pakistan": m["pk"], "Abroad": m["abroad"], "Pakistan source": m["confidence"]["pk"],
             "Abroad source": m["confidence"]["abroad"], "Note": m["note"]} for f, m in kb.market["fields"].items()]
    lvl = st.column_config.SelectboxColumn(options=["high", "medium", "low"])
    conf = st.column_config.SelectboxColumn(options=["sourced", "estimate"])
    edited = st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch", key="ka_mk", disabled=["Field"],
                            column_config={"Pakistan": lvl, "Abroad": lvl, "Pakistan source": conf, "Abroad source": conf})
    if st.button("Apply market changes", type="primary", key="ka_mk_apply"):
        new = copy.deepcopy(kb.data)
        for _, row in edited.iterrows():
            m = new["market_data"]["fields"][row["Field"]]
            m["pk"], m["abroad"], m["note"] = row["Pakistan"], row["Abroad"], row["Note"]
            m["confidence"] = {"pk": row["Pakistan source"], "abroad": row["Abroad source"]}
        apply(new)
    file_buttons(kb, "market_data", "market data")


def rules_tab(kb):
    c.muted("Rules are shown read-only here. To change a rule, edit rules.json and upload it; the file is checked before it is used.")
    st.json(kb.data["rules"], expanded=False)
    file_buttons(kb, "rules", "rules")
