"""Consultation wizard: welcome, 6 steps, review, result."""

import streamlit as st

from engine.consult import run_consultation, visible_questions
from ui import components as c
from ui import state
from views import result_view

PREFIX = "wz"


def current_answers(kb, step_questions):
    """Saved answers plus what is on screen now (so ask_if reacts immediately)."""
    answers = dict(state.wizard()["answers"])
    for q in step_questions:
        if f"{PREFIX}_{q['id']}" in st.session_state:
            c.read_into(q, PREFIX, answers)
    return answers


def on_next(kb, step):
    wiz = state.wizard()
    qs = [q for q in kb.questions if q["step"] == step]
    answers = current_answers(kb, qs)
    shown = {q["id"] for q in visible_questions(answers, kb)}
    errors = {}
    for q in qs:
        if q["id"] in shown:
            err = c.validate(q, answers)
            if err:
                errors[q["id"]] = err
    wiz["answers"] = answers
    if errors:
        wiz["errors"] = errors
    else:
        state.go(step + 1)


def on_back(kb, step):
    wiz = state.wizard()
    qs = [q for q in kb.questions if q["step"] == step]
    wiz["answers"] = current_answers(kb, qs)
    state.go(step - 1)


def see_result(kb):
    wiz = state.wizard()
    st.session_state.wiz_result = run_consultation(wiz["answers"], kb)
    state.go(8)


def restart():
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_") or k in ("wiz", "wiz_result"):
            del st.session_state[k]


def welcome():
    st.title("Find a university field that fits you")
    st.markdown(
        "- Answer a few questions about your studies, interests and plans.\n"
        "- The system checks eligibility rules (PMDC, PEC, HEC) and your strengths.\n"
        "- You get up to three fields, matching universities and the reasons behind each."
    )
    c.muted("Takes about 5 minutes. Your answers stay in this browser session.")
    st.button("Start", type="primary", on_click=state.go, args=(1,))


def step_page(kb, step):
    total = len(kb.steps)
    title = kb.steps[step - 1]["title"]
    c.step_header(step, total, title)
    st.subheader(title)
    wiz = state.wizard()
    qs = [q for q in kb.questions if q["step"] == step]
    answers = current_answers(kb, qs)
    shown = {q["id"] for q in visible_questions(answers, kb)}
    for q in qs:
        if q["id"] in shown:
            c.question(q, kb, PREFIX, wiz["answers"], wiz["errors"].get(q["id"]))
        else:
            c.skipped(skip_text(q, answers, kb))
    if wiz["errors"]:
        c.error_text("Some answers are missing. Please check the messages above.")
    left, right = st.columns(2)
    if step > 1:
        left.button("Back", on_click=on_back, args=(kb, step), width="stretch")
    right.button("Next", type="primary", on_click=on_next, args=(kb, step), width="stretch")


def skip_text(q, answers, kb):
    """'Skipped because you chose Pre-Engineering' when the stream decides it."""
    if "stream" in str(q.get("ask_if", "")) and answers.get("stream"):
        return f"you chose {kb.answer_label('stream', answers['stream'])}"
    return q.get("skip_reason", "it does not apply to you")


def review(kb):
    st.title("Check your answers")
    c.muted("Use Edit to change a group. Then press 'See my result'.")
    answers = state.wizard()["answers"]
    shown = visible_questions(answers, kb)
    for s in kb.steps:
        qs = [q for q in shown if q["step"] == s["n"]]
        head, edit = st.columns([4, 1], vertical_alignment="center")
        head.markdown(f"**{s['n']}. {s['title']}**")
        edit.button("Edit", key=f"edit_{s['n']}", on_click=state.go, args=(s["n"],), width="stretch")
        rows = "".join(f"<tr><td>{c.esc(q['label'])}</td><td><b>{c.esc(c.show_answer(q, kb, answers))}</b></td></tr>" for q in qs)
        st.markdown(f'<table style="width:100%;font-size:0.92rem">{rows}</table>', unsafe_allow_html=True)
    left, right = st.columns(2)
    left.button("Back", on_click=state.go, args=(len(kb.steps),), width="stretch")
    right.button("See my result", type="primary", on_click=see_result, args=(kb,), width="stretch")


def render():
    kb = state.kb()
    wiz = state.wizard()
    step = wiz["step"]
    if step == 0:
        welcome()
    elif 1 <= step <= len(kb.steps):
        step_page(kb, step)
    elif step == len(kb.steps) + 1:
        review(kb)
    else:
        result = st.session_state.get("wiz_result")
        if result is None:
            state.go(len(kb.steps) + 1)
            st.rerun()
        top = st.columns([1, 1, 2])
        top[0].button("Edit answers", on_click=state.go, args=(len(kb.steps) + 1,), width="stretch")
        top[1].button("Start again", on_click=restart, width="stretch")
        result_view.render(result, wiz["answers"], kb, "wz", on_use=use_whatif)
    c.footer()


def use_whatif(new_answers):
    """'Use these answers' from the What-if panel."""
    kb = state.kb()
    state.wizard()["answers"] = new_answers
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_"):
            del st.session_state[k]
    st.session_state.wiz_result = run_consultation(new_answers, kb)
