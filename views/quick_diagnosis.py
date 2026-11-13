"""Counsellor Desk (quick diagnosis): every question on one screen, plus five sample students.

Here the data-sufficiency rules (G0) decide what is missing, so an empty
submit gives 'Insufficient data'.
"""

import streamlit as st

from engine.consult import complete_answers, load_samples, run_consultation
from ui import components as c
from ui import state
from views import result_view

PREFIX = "qd"
TAB_NAMES = ["About you", "Education", "Interests", "Skills", "Tests", "Budget"]


def clear_form():
    """Empty every field of the form."""
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_") or k in ("qd_result", "qd_answers", "qd_loaded"):
            del st.session_state[k]


def load_sample(sample, kb):
    """Fill the form with one sample student."""
    clear_form()
    answers = complete_answers(sample["answers"], kb)
    for q in kb.questions:
        key = f"{PREFIX}_{q['id']}"
        v = answers.get(q["id"])
        if q["type"] in ("number", "test") and v is not None:
            v = float(v)
        if q["type"] == "multiselect":
            v = v or []
        if v is not None:
            st.session_state[key] = v
        if q["type"] == "test":
            st.session_state[f"{key}_not_taken"] = bool(answers.get(f"{q['id']}_not_taken"))
    st.session_state.qd_loaded = sample["name"]


def collect(kb):
    """Read the whole form into an answers dict."""
    answers = {}
    for q in kb.questions:
        c.read_into(q, PREFIX, answers)
        if q["type"] == "test" and answers.get(q["id"]) is None:
            answers[f"{q['id']}_not_taken"] = True  # blank test = not taken here
    return answers


def sample_cards(kb, samples):
    """The five sample-student cards with Load buttons."""
    st.markdown("**Sample students**")
    cols = st.columns(len(samples))
    for col, s in zip(cols, samples):
        with col.container(border=True):
            st.markdown(f'<div class="rn-sample"><b>{c.esc(s["name"])}</b><br>{c.esc(s["blurb"])}</div>', unsafe_allow_html=True)
            st.button("Load", key=f"qd_load_{s['name']}", on_click=load_sample, args=(s, kb), width="stretch")


def render():
    """Form in tabs on the left, the report on the right."""
    kb = state.kb()
    c.page_title("Counsellor Desk", "Quick diagnosis on one screen")
    samples = load_samples()
    sample_cards(kb, samples)
    loaded = st.session_state.get("qd_loaded")
    if loaded:
        expected = next((s["expected"] for s in samples if s["name"] == loaded), "")
        c.muted(f"Loaded: {loaded}. Expected result: {expected}")

    left, right = st.columns([1, 1.6], gap="large")
    with left:
        with st.form("qd_form", border=False):
            tabs = st.tabs(TAB_NAMES)
            for tab, s in zip(tabs, kb.steps):
                with tab:
                    for q in kb.questions:
                        if q["step"] == s["n"]:
                            c.question(q, kb, PREFIX, {}, why=False, in_form=True)
            submitted = st.form_submit_button("Run diagnosis", type="primary", width="stretch")
        st.button("Clear form", on_click=clear_form, width="stretch")
    if submitted:
        answers = collect(kb)
        st.session_state.qd_answers = answers
        st.session_state.qd_result = run_consultation(answers, kb, use_ask_if=False)
    with right:
        if st.session_state.get("qd_result"):
            result_view.render(st.session_state.qd_result, st.session_state.qd_answers, kb, "qd",
                               on_use=use_whatif, use_ask_if=False, name=st.session_state.get("qd_loaded"))
        else:
            c.muted("Fill in the form (or load a sample) and press 'Run diagnosis'. The report appears here.")
    c.footer()


def use_whatif(new_answers):
    """'Use these answers' from the What-if panel."""
    kb = state.kb()
    st.session_state.qd_answers = new_answers
    st.session_state.qd_result = run_consultation(new_answers, kb, use_ask_if=False)
