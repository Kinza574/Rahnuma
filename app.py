"""Rahnuma — University Field Advisor. Entry point: page navigation."""

import streamlit as st

from ui import theme
from views import about, consultation, knowledge_acquisition, knowledge_base_view, quick_diagnosis

st.set_page_config(page_title=f"{theme.APP_NAME} — {theme.APP_TAGLINE}", layout="centered")
theme.apply()

pages = {
    "Students": [
        st.Page(consultation.render, title="Guided Counselling", url_path="guided-counselling", default=True),
        st.Page(quick_diagnosis.render, title="Counsellor Desk", url_path="counsellor-desk"),
    ],
    "Experts": [
        st.Page(knowledge_base_view.render, title="Knowledge Base", url_path="knowledge-base"),
        st.Page(knowledge_acquisition.render, title="Knowledge Acquisition", url_path="knowledge-acquisition"),
    ],
    "": [
        st.Page(about.render, title="About", url_path="about"),
    ],
}

st.navigation(pages, position="top").run()
