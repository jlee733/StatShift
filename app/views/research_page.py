"""Research page - NFL player research."""

from __future__ import annotations

import streamlit as st

from app.research_tab import render_research_tab

st.title("StatShift")

render_research_tab()
