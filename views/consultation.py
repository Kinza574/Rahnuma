"""Guided Counselling: step-by-step consultation and diagnosis (welcome, 6 steps, review, report)."""

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
    """Validate the shown questions of this step, then go to the next step."""
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
    """Keep what is on screen and go back one step."""
    wiz = state.wizard()
    qs = [q for q in kb.questions if q["step"] == step]
    wiz["answers"] = current_answers(kb, qs)
    state.go(step - 1)


def see_result(kb):
    """Run the engine on the saved answers and open the report."""
    wiz = state.wizard()
    st.session_state.wiz_result = run_consultation(wiz["answers"], kb)
    state.go(8)


def restart():
    """Forget all wizard answers."""
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_") or k in ("wiz", "wiz_result"):
            del st.session_state[k]


def welcome():
    """Welcome screen with the step list and a Start button."""
    c.page_title("Guided Counselling", "Step-by-step consultation and diagnosis")
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        c.step_list(state.kb().steps, 0)
    with right:
        st.markdown(
            "Rahnuma works like a careful counsellor. It asks about your studies, interests and plans, "
            "checks the admission rules (PMDC, PEC, HEC, PCATP) and then suggests up to three fields "
            "with matching universities and the reasons behind each."
        )
        c.muted("About 5 minutes. Your answers stay in this browser session.")
        st.button("Start", type="primary", on_click=state.go, args=(1,))


def step_page(kb, step):
    """One step: step list on the left, question cards on the right."""
    c.page_title("Guided Counselling", "Step-by-step consultation and diagnosis")
    wiz = state.wizard()
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        c.step_list(kb.steps, step)
    with right:
        title = kb.steps[step - 1]["title"]
        st.subheader(title)
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
        b1, b2 = st.columns(2)
        if step > 1:
            b1.button("Back", on_click=on_back, args=(kb, step), width="stretch")
        b2.button("Next", type="primary", on_click=on_next, args=(kb, step), width="stretch")


def skip_text(q, answers, kb):
    """'Skipped because you chose Pre-Engineering' when the stream decides it."""
    if "stream" in str(q.get("ask_if", "")) and answers.get("stream"):
        return f"you chose {kb.answer_label('stream', answers['stream'])}"
    return q.get("skip_reason", "it does not apply to you")


def review(kb):
    """Review screen: answers grouped by step, each with an Edit button."""
    c.page_title("Guided Counselling", "Step-by-step consultation and diagnosis")
    wiz = state.wizard()
    answers = wiz["answers"]
    shown = visible_questions(answers, kb)
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        c.step_list(kb.steps, len(kb.steps) + 1)
    with right:
        st.subheader("Check your answers")
        c.muted("Use Edit to change a group, then press 'See my result'.")
        for s in kb.steps:
            qs = [q for q in shown if q["step"] == s["n"]]
            with st.container(border=True):
                head, edit = st.columns([4, 1], vertical_alignment="center")
                head.markdown(f"**{s['n']}. {s['title']}**")
                edit.button("Edit", key=f"edit_{s['n']}", on_click=state.go, args=(s["n"],), width="stretch")
                body = "".join(f"<dt>{c.esc(q['label'])}</dt><dd><b>{c.esc(c.show_answer(q, kb, answers))}</b></dd>" for q in qs)
                st.markdown(f'<dl class="rn-dl">{body}</dl>', unsafe_allow_html=True)
        wiz["name"] = st.text_input("Name for the report (optional)", value=wiz.get("name", ""), max_chars=40)
        b1, b2 = st.columns(2)
        b1.button("Back", on_click=state.go, args=(len(kb.steps),), width="stretch")
        b2.button("See my result", type="primary", on_click=see_result, args=(kb,), width="stretch")


def render():
    """Page entry point: show the welcome, a step, the review or the report."""
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
        top = st.columns([1, 1, 3])
        top[0].button("Edit answers", on_click=state.go, args=(len(kb.steps) + 1,), width="stretch")
        top[1].button("Start again", on_click=restart, width="stretch")
        result_view.render(result, wiz["answers"], kb, "wz", on_use=use_whatif, name=wiz.get("name"))
    c.footer()


def use_whatif(new_answers):
    """'Use these answers' from the What-if panel."""
    kb = state.kb()
    state.wizard()["answers"] = new_answers
    for k in list(st.session_state):
        if k.startswith(PREFIX + "_"):
            del st.session_state[k]
    st.session_state.wiz_result = run_consultation(new_answers, kb)
