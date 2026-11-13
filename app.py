"""Rahnuma — University Field Advisor. Entry point: page navigation."""

import streamlit as st

from ui import theme
from views import about, consultation, knowledge_acquisition, knowledge_base_view, quick_diagnosis

st.set_page_config(page_title=f"{theme.APP_NAME} — {theme.APP_TAGLINE}", layout="centered")
theme.apply()

pages = {
    "For students": [
        st.Page(consultation.render, title="Consultation", url_path="consultation", default=True),
        st.Page(quick_diagnosis.render, title="Quick Diagnosis", url_path="quick-diagnosis"),
    ],
    "For experts": [
        st.Page(knowledge_base_view.render, title="Knowledge Base", url_path="knowledge-base"),
        st.Page(knowledge_acquisition.render, title="Knowledge Acquisition", url_path="knowledge-acquisition"),
    ],
    "Info": [
        st.Page(about.render, title="About", url_path="about"),
    ],
}

with st.sidebar:
    st.markdown(f"### {theme.APP_NAME}")
    st.caption(theme.APP_TAGLINE)

st.navigation(pages).run()
