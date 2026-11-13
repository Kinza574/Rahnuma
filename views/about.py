"""About page: components, requirements, sources and limitations."""

import pandas as pd
import streamlit as st

from ui import components as c
from ui import state, theme


def render():
    """About page: components, requirements, sources and limitations."""
    kb = state.kb()
    c.page_title("About Rahnuma", "University Field Advisor — a rule-based expert system")
    st.write("Rahnuma is a rule-based expert system that helps Pakistani Matric, Inter and O/A-Level students "
             "choose a university field and then lists matching universities in Pakistan.")
    if theme.APP_URL:
        st.markdown(f"Live app: [{theme.APP_URL}]({theme.APP_URL})")
    else:
        c.muted("Live app URL: added after deployment on Streamlit Community Cloud (see README).")

    c.section("Expert-system components")
    comps = [
        ("Knowledge base", "Rules, thresholds, questions, fields, universities and market data as JSON", "knowledge_base/*.json, kb_loader.py"),
        ("Working memory", "The facts known during one consultation, each with a certainty factor", "engine/working_memory.py"),
        ("Inference engine", "Forward chaining with an agenda, conflict resolution, refraction and a cycle cap", "engine/inference.py, conditions.py, actions.py"),
        ("Explanation facility", "'Why are you asking?', the step-by-step trace and plain reasons", "engine/explanation.py"),
        ("Knowledge acquisition", "Edit thresholds and data, check them, download/upload JSON", "views/knowledge_acquisition.py"),
        ("User interface", "Streamlit pages: Guided Counselling (wizard), Counsellor Desk (quick diagnosis), report, expert pages", "app.py, views/, ui/"),
    ]
    st.dataframe(pd.DataFrame(comps, columns=["Component", "What it does", "Files"]), hide_index=True, width="stretch")

    c.section("How the requirements are met")
    counts = kb.counts()
    req = [
        ("Inferencing", "Our own forward-chaining engine (engine/inference.py) with MYCIN certainty factors; see 'How the system reached this' on the result page."),
        ("Diagnosis", "Rule groups G1-G4 turn answers into an aptitude profile and eligibility gaps: the 'Diagnosis' section of the counselling report."),
        ("Decision making", "G8 picks the top 3 fields with confidence words, 'Insufficient data' (DS06), strict not-eligible verdicts (G4) and university filtering (G7)."),
        ("Decision support", "University table with filters, job outlook with sources, action plans, alternatives and the 'What if?' panel."),
        ("Minimum 50 conditions", f"{counts['total']} rules ({counts['compute']} compute / {counts['decision']} decision) with {counts['leaf_conditions']} leaf conditions."),
        ("Unique niche", "Field and university advice for Pakistani students using PMDC, PEC, HEC and PCATP rules and MDCAT / LAT / ECAT."),
        ("Streamlit UI on WAN", "Streamlit app deployed on Streamlit Community Cloud."),
    ]
    st.dataframe(pd.DataFrame(req, columns=["Requirement", "Where it appears"]), hide_index=True, width="stretch")

    c.section("Knowledge sources")
    offs = [o for u in kb.universities["universities"] for o in u["offerings"]]
    m = st.columns(3)
    m[0].metric("Universities", len(kb.universities["universities"]))
    m[1].metric("Programme offerings", len(offs))
    m[2].metric("Verified offerings", f"{sum(o['verified'] for o in offs)} of {len(offs)}")
    st.markdown(
        f"- Admission thresholds: PMDC, PNMC, HEC (LAT), PCATP and university admission pages — as of {kb.data['thresholds']['as_of']}. Each threshold lists its source on the Knowledge Base page.\n"
        f"- Universities: {len(kb.universities['universities'])} institutions, {len(offs)} programme offerings, "
        f"{sum(o['verified'] for o in offs)} verified on an official page — as of {kb.universities['as_of']}.\n"
        f"- Job market: SBP, PBS, Bureau of Emigration & Overseas Employment and news reports — as of {kb.market['as_of']}. {kb.market.get('context', '')}"
    )

    c.section("Limitations")
    st.markdown(
        "- The rules simplify real admission policies; each university has its own extra conditions.\n"
        "- Merit cut-offs change every year and are not predicted here.\n"
        "- University data may change, and many rows could not be verified online.\n"
        "- The job-market data is broad and partly estimated."
    )
    c.footer()
