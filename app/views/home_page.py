"""Home page - Mock Draft."""

from __future__ import annotations

import streamlit as st

from app.mock_draft_tab import render_mock_draft_tab

st.title("StatShift")

render_mock_draft_tab()
