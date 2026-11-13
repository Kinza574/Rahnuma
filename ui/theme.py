"""Colours, spacing and the small amount of custom CSS."""

import streamlit as st

ACCENT = "#1F5F5B"
ACCENT_SOFT = "#E8F0EF"
GREY_TEXT = "#5F6B6A"
BORDER = "#DDE2E1"
WARN_BG = "#FBF6EA"
WARN_BORDER = "#C9A64A"

APP_NAME = "Rahnuma"
APP_TAGLINE = "University Field Advisor"
APP_URL = ""  # public Streamlit Cloud URL, filled in after deployment
FOOTER = "For guidance only — always confirm admission criteria with the university."

CSS = f"""
<style>
.block-container {{ max-width: 980px; padding-top: 2rem; padding-bottom: 3rem; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.rn-muted {{ color: {GREY_TEXT}; font-size: 0.9rem; }}
.rn-skip {{ color: {GREY_TEXT}; font-size: 0.88rem; margin: 0.1rem 0 0.9rem 0; }}
.rn-error {{ color: #A3322B; font-size: 0.88rem; margin: -0.4rem 0 0.8rem 0; }}
.rn-card {{ border: 1px solid {BORDER}; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.9rem; background: #FFFFFF; }}
.rn-card h4 {{ margin: 0 0 0.3rem 0; font-size: 1.08rem; }}
.rn-summary {{ border-left: 4px solid {ACCENT}; background: {ACCENT_SOFT}; padding: 0.9rem 1.1rem; border-radius: 4px; margin-bottom: 1rem; }}
.rn-warn {{ border-left: 4px solid {WARN_BORDER}; background: {WARN_BG}; padding: 0.6rem 0.9rem; border-radius: 4px; margin-bottom: 0.5rem; font-size: 0.93rem; }}
.rn-tag {{ display: inline-block; border: 1px solid {BORDER}; border-radius: 4px; padding: 0 0.4rem; margin-right: 0.3rem; font-size: 0.8rem; color: {GREY_TEXT}; }}
.rn-label {{ display: inline-block; background: {ACCENT}; color: #FFFFFF; border-radius: 4px; padding: 0.05rem 0.5rem; font-size: 0.8rem; margin-left: 0.4rem; vertical-align: middle; }}
.rn-label.soft {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
.rn-footer {{ border-top: 1px solid {BORDER}; margin-top: 3rem; padding-top: 0.8rem; color: {GREY_TEXT}; font-size: 0.85rem; }}
.rn-step {{ color: {GREY_TEXT}; font-size: 0.9rem; margin-bottom: 0.2rem; }}
div[data-testid="stRadio"] > label p {{ font-weight: 500; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 1rem; }}
}}
</style>
"""


def apply():
    st.markdown(CSS, unsafe_allow_html=True)
