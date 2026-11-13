"""Quick Diagnosis: every question on one form, plus five sample students.

Here the data-sufficiency rules (G0) decide what is missing, so an empty
submit gives 'Insufficient data'.
"""

import streamlit as st

from engine.consult import complete_answers, load_samples, run_consultation
from ui import components as c
from ui import state
from views import result_view

PREFIX = "qd"


def clear_form():
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_") or k in ("qd_result", "qd_answers"):
            del st.session_state[k]


def load_sample(sample, kb):
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
    answers = {}
    for q in kb.questions:
        c.read_into(q, PREFIX, answers)
        if q["type"] == "test" and answers.get(q["id"]) is None:
            answers[f"{q['id']}_not_taken"] = True  # blank test = not taken here
    return answers


def render():
    kb = state.kb()
    st.title("Quick Diagnosis")
    c.muted("All questions on one page. Leave anything blank to see how the system handles missing data.")
    samples = load_samples()
    cols = st.columns(len(samples) + 1)
    for col, s in zip(cols, samples):
        col.button(f"Load sample: {s['name']}", key=f"qd_load_{s['name']}", on_click=load_sample, args=(s, kb), width="stretch")
    cols[-1].button("Clear form", on_click=clear_form, width="stretch")
    if st.session_state.get("qd_loaded"):
        name = st.session_state.qd_loaded
        expected = next((s["expected"] for s in samples if s["name"] == name), "")
        c.muted(f"Loaded sample: {name}. Expected: {expected}")

    with st.form("qd_form"):
        for s in kb.steps:
            st.subheader(f"{s['n']}. {s['title']}")
            for q in kb.questions:
                if q["step"] == s["n"]:
                    c.question(q, kb, PREFIX, {}, why=False, in_form=True)
        submitted = st.form_submit_button("Run diagnosis", type="primary")
    if submitted:
        answers = collect(kb)
        st.session_state.qd_answers = answers
        st.session_state.qd_result = run_consultation(answers, kb, use_ask_if=False)
    if st.session_state.get("qd_result"):
        st.divider()
        result_view.render(st.session_state.qd_result, st.session_state.qd_answers, kb, "qd",
                           on_use=use_whatif, use_ask_if=False)
    c.footer()


def use_whatif(new_answers):
    kb = state.kb()
    st.session_state.qd_answers = new_answers
    st.session_state.qd_result = run_consultation(new_answers, kb, use_ask_if=False)
