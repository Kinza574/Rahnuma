"""Session-state helpers for the wizard and the editable knowledge base."""

import streamlit as st

from knowledge_base.kb_loader import load_kb


def kb():
    """The knowledge base for this session (Knowledge Acquisition can change it)."""
    if "kb" not in st.session_state:
        st.session_state.kb = load_kb()
    return st.session_state.kb


def set_kb(new_kb):
    st.session_state.kb = new_kb
    # results built with the old knowledge base are no longer valid
    for k in ("wiz_result", "qd_result"):
        st.session_state.pop(k, None)


def wizard():
    """Wizard state: current step (0 = welcome, 1-6 steps, 7 = review, 8 = result) and answers."""
    if "wiz" not in st.session_state:
        st.session_state.wiz = {"step": 0, "answers": {}, "errors": {}}
    return st.session_state.wiz


def go(step):
    wizard()["step"] = step
    wizard()["errors"] = {}


def widget_key(prefix, qid):
    return f"{prefix}_{qid}"
