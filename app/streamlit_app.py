"""Streamlit data platform for the local StatShift prototype."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mock_draft_tab import render_mock_draft_tab
from draft.rpy2_setup import init_rpy2_on_main_thread
from rag.engine import RAGEngine
from rag.ollama_client import OllamaError

st.set_page_config(
    page_title="StatShift",
    page_icon="📊",
    layout="wide",
)

st.title("StatShift")

engine = RAGEngine()


@st.cache_resource
def _rpy2_ready() -> bool:
    """Initialize rpy2 once on Streamlit's main thread (required for Mock Draft)."""
    init_rpy2_on_main_thread()
    return True


_rpy2_ready()

with st.sidebar:
    if st.button("Check services", use_container_width=True):
        st.session_state["health"] = engine.health()
    health = st.session_state.get("health")
    if health:
        st.write("Data", "✅" if health["api_ok"] else "❌")
        st.write("AI", "✅" if health["ollama_ok"] else "❌")

ask_tab, draft_tab = st.tabs(["Ask", "Mock Draft"])

with ask_tab:
    query = st.text_input(
        "Ask about players, matchups, injuries, or fantasy scoring",
        placeholder="e.g. How many targets did Ja'Marr Chase have in 2024?",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        run = st.button("Ask", type="primary", use_container_width=True)
    with col2:
        show_prompt = st.checkbox("Show AI prompt")

    if run and query.strip():
        with st.spinner("Routing your question..."):
            try:
                result = engine.ask(query.strip())
                st.session_state["last_result"] = result
            except OllamaError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Something went wrong: {exc}")

    result = st.session_state.get("last_result")
    if result:
        st.subheader("Answer")
        st.markdown(result.answer)

        if result.sources:
            st.subheader("Sources")
        for doc in result.sources:
            with st.expander(f"[{doc['id']}] {doc['title']} · {doc['category']}"):
                st.write(doc["content"])

        if show_prompt and result.prompt:
            st.subheader("Prompt")
            st.code(result.prompt)

    elif run and not query.strip():
        st.warning("Enter a question first.")

with draft_tab:
    render_mock_draft_tab()
