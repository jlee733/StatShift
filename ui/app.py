"""Streamlit data platform for the local StatShift prototype."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from draft.rpy2_setup import init_rpy2_on_main_thread
from ui.styles import inject_global_styles

st.set_page_config(
    page_title="StatShift",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _rpy2_ready() -> bool:
    """Initialize rpy2 once on Streamlit's main thread (required for Mock Draft)."""
    init_rpy2_on_main_thread()
    return True


_rpy2_ready()
inject_global_styles()

VIEWS_DIR = Path(__file__).parent / "views"

home_page = st.Page(
    str(VIEWS_DIR / "mock_draft.py"),
    title="Home",
    icon="🏠",
    default=True,
)
ask_page = st.Page(
    str(VIEWS_DIR / "ask.py"),
    title="Ask",
    icon="💬",
)
research_page = st.Page(
    str(VIEWS_DIR / "research.py"),
    title="Research",
    icon="🔍",
)

pg = st.navigation(
    [home_page, ask_page, research_page],
    position="sidebar",
    expanded=True,
)
pg.run()
