"""End-to-end UI tests with Streamlit's AppTest (no browser needed)."""

from streamlit.testing.v1 import AppTest

from engine.consult import complete_answers, load_samples, visible_questions


def fill_step(at, kb, step, answers):
    for q in visible_questions(answers, kb):
        if q["step"] != step:
            continue
        key, v = f"wz_{q['id']}", answers.get(q["id"])
        t = q["type"]
        if t == "tri":
            at.button_group(key=key).set_value(v)
        elif t == "select":
            at.selectbox(key=key).set_value(v)
        elif t == "multiselect":
            at.multiselect(key=key).set_value(v or [])
        elif t == "number":
            at.number_input(key=key).set_value(float(v))
        elif t == "test":
            if answers.get(f"{q['id']}_not_taken"):
                at.checkbox(key=f"{key}_not_taken").check()
            else:
                at.number_input(key=key).set_value(float(v))


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()


def test_wizard_end_to_end_hamza(kb):
    hamza = next(s for s in load_samples() if s["name"] == "Hamza")
    answers = complete_answers(hamza["answers"], kb)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    click(at, "Start")
    for step in range(1, len(kb.steps) + 1):
        fill_step(at, kb, step, answers)
        click(at, "Next")
        assert not [m for m in at.markdown if m.value.startswith('<p class="rn-error"')], f"errors on step {step}"
    click(at, "See my result")
    page = " ".join(m.value for m in at.markdown)
    assert "Counselling report" in page
    assert "Computer Science" in page and "Software Engineering" in page
    assert not at.exception


def test_wizard_blocks_next_without_answers(kb):
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    click(at, "Start")
    click(at, "Next")
    assert [m for m in at.markdown if "Please choose an answer." in m.value]
