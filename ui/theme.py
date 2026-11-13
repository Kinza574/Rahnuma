"""Colours, spacing and the small amount of custom CSS."""

import streamlit as st

ACCENT = "#7A2E3A"        # deep maroon, the one accent colour
ACCENT_SOFT = "#F3E9E8"
PAPER = "#FAF8F5"
CARD = "#FFFFFF"
INK = "#1F1F1F"
GREY_TEXT = "#6B645C"
GREY_LIGHT = "#A79F95"
BORDER = "#E4DED6"
NOTE_BG = "#F4EFE7"

APP_NAME = "Rahnuma"
APP_TAGLINE = "University Field Advisor"
APP_URL = ""  # public Streamlit Cloud URL, filled in after deployment
FOOTER = "For guidance only — always confirm admission criteria with the university."

SERIF = 'Georgia, "Times New Roman", serif'

CSS = f"""
<style>
.block-container {{ max-width: 1240px; padding-top: 4.2rem; padding-bottom: 3rem; }}
h1, h2, h3, h4 {{ font-family: {SERIF}; color: {INK}; letter-spacing: 0; }}
.rn-sub {{ color: {GREY_TEXT}; margin: -0.6rem 0 1.4rem 0; font-size: 0.98rem; }}
.rn-muted {{ color: {GREY_TEXT}; font-size: 0.9rem; }}
.rn-skip {{ color: {GREY_LIGHT}; font-size: 0.86rem; margin: 0.1rem 0 0.8rem 0; font-style: italic; }}
.rn-error {{ color: #9B2C2C; font-size: 0.86rem; margin: 0.2rem 0 0 0; }}
.rn-help {{ color: {GREY_TEXT}; font-size: 0.86rem; margin: -0.2rem 0 0.5rem 0; }}
.rn-qlabel {{ font-weight: 600; font-size: 0.98rem; margin-bottom: 0.25rem; }}

/* step list (desktop) and compact step line (phone) */
.rn-steps {{ list-style: none; padding: 0; margin: 0.3rem 0 0 0; }}
.rn-steps li {{ padding: 0.55rem 0.8rem; border-left: 3px solid transparent; color: {GREY_LIGHT}; font-size: 0.93rem; }}
.rn-steps li.done {{ color: {INK}; }}
.rn-steps li.done .mark {{ color: {ACCENT}; }}
.rn-steps li.current {{ border-left-color: {ACCENT}; color: {ACCENT}; font-weight: 600; background: {ACCENT_SOFT}; }}
.rn-steps .mark {{ display: inline-block; width: 1.4rem; }}
.rn-step-compact {{ display: none; color: {GREY_TEXT}; font-size: 0.9rem; margin-bottom: 0.6rem; }}

/* report */
.rn-report-head {{ border-bottom: 2px solid {ACCENT}; padding-bottom: 0.5rem; margin-bottom: 1.2rem; }}
.rn-report-head .who {{ font-family: {SERIF}; font-size: 1.7rem; }}
.rn-report-head .meta {{ color: {GREY_TEXT}; font-size: 0.9rem; }}
.rn-summary {{ font-family: {SERIF}; font-size: 1.08rem; line-height: 1.55; margin: 0 0 1.2rem 0; }}
.rn-section {{ font-family: {SERIF}; font-size: 1.25rem; margin: 1.6rem 0 0.6rem 0; padding-bottom: 0.25rem; border-bottom: 1px solid {BORDER}; }}
.rn-dl {{ display: grid; grid-template-columns: 30% 70%; gap: 0.35rem 1rem; font-size: 0.93rem; }}
.rn-dl dt {{ color: {GREY_TEXT}; }}
.rn-dl dd {{ margin: 0; }}
.rn-rec {{ display: grid; grid-template-columns: 2.2rem 1fr; gap: 0 0.6rem; padding: 0.9rem 0; border-bottom: 1px solid {BORDER}; }}
.rn-rec .num {{ font-family: {SERIF}; font-size: 1.6rem; color: {ACCENT}; line-height: 1.1; }}
.rn-rec .name {{ font-weight: 600; font-size: 1.05rem; }}
.rn-bar {{ display: flex; align-items: center; gap: 0.7rem; margin: 0.35rem 0 0.4rem 0; }}
.rn-bar .track {{ flex: 0 0 220px; height: 8px; background: {BORDER}; border-radius: 2px; overflow: hidden; }}
.rn-bar .fill {{ height: 100%; background: {ACCENT}; }}
.rn-bar .word {{ font-size: 0.88rem; color: {ACCENT}; font-weight: 600; }}
.rn-cond {{ font-size: 0.82rem; border: 1px solid {ACCENT}; color: {ACCENT}; border-radius: 3px; padding: 0 0.35rem; margin-left: 0.4rem; }}
.rn-note {{ background: {NOTE_BG}; border-left: 3px solid {GREY_LIGHT}; padding: 0.55rem 0.85rem; margin-bottom: 0.5rem; font-size: 0.92rem; }}
.rn-tag {{ display: inline-block; border: 1px solid {BORDER}; border-radius: 3px; padding: 0 0.35rem; margin-right: 0.3rem; font-size: 0.78rem; color: {GREY_TEXT}; }}
.rn-sample {{ font-size: 0.88rem; line-height: 1.35; min-height: 3.9em; }}
.rn-sample b {{ font-family: {SERIF}; font-size: 1rem; }}
.rn-footer {{ border-top: 1px solid {BORDER}; margin-top: 3rem; padding-top: 0.8rem; color: {GREY_TEXT}; font-size: 0.84rem; }}

@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 3.6rem; }}
  .rn-steps {{ display: none; }}
  .rn-step-compact {{ display: block; }}
  .rn-dl {{ grid-template-columns: 1fr; }}
  .rn-dl dd {{ margin-bottom: 0.4rem; }}
  .rn-bar .track {{ flex-basis: 120px; }}
  h1 {{ font-size: 2.1rem !important; }}
}}
</style>
"""


def apply():
    """Inject the small custom CSS."""
    st.markdown(CSS, unsafe_allow_html=True)
