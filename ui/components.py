"""Small reusable UI pieces: question widgets, headers, cards, footer."""

import html

import streamlit as st

from engine.explanation import why_asking
from ui import theme
from ui.state import widget_key

TRI = ["yes", "no", "notsure"]
TRI_LABEL = {"yes": "Yes", "no": "No", "notsure": "Not sure"}


def esc(text):
    return html.escape(str(text))


def footer():
    st.markdown(f'<div class="rn-footer">{esc(theme.FOOTER)}</div>', unsafe_allow_html=True)


def expert_note():
    st.markdown('<p class="rn-muted">This page is for experts and the knowledge engineer.</p>', unsafe_allow_html=True)


def step_header(n, total, title):
    st.markdown(f'<div class="rn-step">Step {n} of {total} — {esc(title)}</div>', unsafe_allow_html=True)
    st.progress(n / total)


def muted(text):
    st.markdown(f'<p class="rn-muted">{esc(text)}</p>', unsafe_allow_html=True)


def skipped(text):
    st.markdown(f'<p class="rn-skip">Skipped because {esc(text)}.</p>', unsafe_allow_html=True)


def error_text(text):
    st.markdown(f'<p class="rn-error">{esc(text)}</p>', unsafe_allow_html=True)


def warning_box(text):
    st.markdown(f'<div class="rn-warn">{esc(text)}</div>', unsafe_allow_html=True)


def summary_box(text):
    st.markdown(f'<div class="rn-summary">{esc(text)}</div>', unsafe_allow_html=True)


def label_chip(word, soft=False):
    return f'<span class="rn-label{" soft" if soft else ""}">{esc(word)}</span>'


def tags(items):
    return "".join(f'<span class="rn-tag">{esc(t)}</span>' for t in items)


def card(title_html, body_html):
    st.markdown(f'<div class="rn-card"><h4>{title_html}</h4>{body_html}</div>', unsafe_allow_html=True)


# ---- question widgets ----

def _seed(key, answers, qid):
    """Put a saved answer into the widget before it is drawn (keeps answers across steps)."""
    if key not in st.session_state and answers.get(qid) is not None:
        v = answers[qid]
        st.session_state[key] = float(v) if isinstance(v, int) and not isinstance(v, bool) else v


def _set_pct(target, obt_key, tot_key):
    obt, tot = st.session_state.get(obt_key), st.session_state.get(tot_key)
    if obt is not None and tot:
        st.session_state[target] = round(obt / tot * 100, 2)


def question(q, kb, prefix, answers, error=None, why=True, in_form=False):
    """Draw one question. Returns nothing; read values with read_value()."""
    qid, key = q["id"], widget_key(prefix, q["id"])
    t = q["type"]
    _seed(key, answers, qid)
    kwargs = {} if key in st.session_state else {"index": None}
    if t == "tri":
        st.radio(q["label"], TRI, format_func=TRI_LABEL.get, horizontal=True, key=key, help=q.get("help"), **kwargs)
    elif t == "select":
        opts = kb.options(qid)
        labels = {o["value"]: o["label"] for o in opts}
        st.selectbox(q["label"], list(labels), format_func=labels.get, key=key, help=q.get("help"),
                     placeholder="Choose an option", **kwargs)
    elif t == "multiselect":
        st.multiselect(q["label"], [o["value"] for o in kb.options(qid)], key=key, help=q.get("help"),
                       placeholder="None chosen")
    elif t == "number":
        nk = {} if key in st.session_state else {"value": None}
        st.number_input(q["label"], min_value=float(q["min"]), max_value=float(q["max"]), step=0.5,
                        format="%.2f", key=key, help=q.get("help"), placeholder="e.g. 72.5", **nk)
        if q.get("helper") and not in_form:
            with st.expander("Work out the % from obtained / total marks"):
                c1, c2, c3 = st.columns([2, 2, 1.4], vertical_alignment="bottom")
                c1.number_input("Obtained", min_value=0.0, step=1.0, value=None, key=f"{key}_obt")
                c2.number_input("Total", min_value=1.0, step=1.0, value=None, key=f"{key}_tot")
                c3.button("Use this", key=f"{key}_use", on_click=_set_pct, args=(key, f"{key}_obt", f"{key}_tot"))
    elif t == "test":
        nt_key = f"{key}_not_taken"
        _seed(nt_key, answers, f"{qid}_not_taken")
        not_taken = st.session_state.get(nt_key, False)
        nk = {} if key in st.session_state else {"value": None}
        c1, c2 = st.columns([3, 1.3], vertical_alignment="bottom")
        c1.number_input(q["label"], min_value=float(q["min"]), max_value=float(q["max"]), step=1.0,
                        key=key, help=q.get("help"), disabled=not_taken, placeholder="Score", **nk)
        c2.checkbox("Not taken yet", key=nt_key)
    if error:
        error_text(error)
    if why:
        with st.expander("Why are you asking?"):
            muted(why_asking(qid, kb))


def read_value(q, prefix):
    key = widget_key(prefix, q["id"])
    return st.session_state.get(key)


def read_into(q, prefix, answers):
    """Copy a widget value into the answers dict."""
    answers[q["id"]] = read_value(q, prefix)
    if q["type"] == "test":
        nt = st.session_state.get(f"{widget_key(prefix, q['id'])}_not_taken", False)
        answers[f"{q['id']}_not_taken"] = nt
        if nt:
            answers[q["id"]] = None


def validate(q, answers):
    """Plain error text, or None when the answer is fine."""
    v = answers.get(q["id"])
    if q["type"] == "multiselect" or not q.get("required"):
        return None
    if q["type"] == "test":
        if v is None and not answers.get(f"{q['id']}_not_taken"):
            return "Enter your score or tick 'Not taken yet'."
        return None
    if v is None or v == "":
        return "Please enter your marks." if q["type"] == "number" else "Please choose an answer."
    return None


def show_answer(q, kb, answers):
    """Answer text for the review screen."""
    v = answers.get(q["id"])
    if q["type"] == "test" and answers.get(f"{q['id']}_not_taken"):
        return "Not taken yet"
    if v is None or v == [] or v == "":
        return "—"
    if q["type"] == "tri":
        return TRI_LABEL[v]
    if q["type"] == "multiselect":
        return ", ".join(v)
    if q["type"] in ("number", "test"):
        return f"{v:g}" + ("" if q["id"] == "sat_score" else "%")
    return kb.answer_label(q["id"], v)
