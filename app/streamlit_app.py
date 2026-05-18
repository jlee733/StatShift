"""Streamlit data platform for the local StatShift prototype."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mock_draft_tab import render_mock_draft_tab
from config import settings
from draft.rpy2_setup import init_rpy2_on_main_thread
from rag.engine import RAGEngine
from rag.ollama_client import OllamaError

st.set_page_config(
    page_title="StatShift",
    page_icon="📊",
    layout="wide",
)

st.title("StatShift")
st.caption(
    "Fantasy football stats — Streamlit → RAG → FastAPI (read-only) → SQLite → Ollama/Gemma"
)

engine = RAGEngine()


@st.cache_resource
def _rpy2_ready() -> bool:
    """Initialize rpy2 once on Streamlit's main thread (required for Mock Draft)."""
    init_rpy2_on_main_thread()
    return True


_rpy2_ready()

with st.sidebar:
    st.header("System status")
    if st.button("Check health", use_container_width=True):
        st.session_state["health"] = engine.health()
    health = st.session_state.get("health")
    if health:
        st.write("API", "✅" if health["api_ok"] else "❌", health.get("api_detail", ""))
        st.write("Ollama", "✅" if health["ollama_ok"] else "❌")
        if health.get("ollama_models"):
            st.caption("Models: " + ", ".join(health["ollama_models"][:5]))
        st.caption(f"Configured model: {health['configured_model']}")

    st.divider()
    st.markdown(
        """
        **Docker**
        `docker compose up --build` → open http://localhost:8501

        **Local**
        1. `python scripts/init_db.py`
        2. `uvicorn api.main:app --reload`
        3. `ollama pull gemma2:2b`
        4. `streamlit run app/streamlit_app.py`
        """
    )
    st.caption(f"API: {settings.api_base_url}")
    st.caption(f"Ollama: {settings.ollama_base_url}")

ask_tab, draft_tab = st.tabs(["Ask StatShift", "Mock Draft"])

with ask_tab:
    query = st.text_input(
        "Ask about players, matchups, injuries, or fantasy scoring",
        placeholder="e.g. How many targets did Ja'Marr Chase have in 2024?",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        run = st.button("Run RAG", type="primary", use_container_width=True)
    with col2:
        show_prompt = st.checkbox("Show prompt sent to Gemma")

    if run and query.strip():
        with st.spinner("Routing your question..."):
            try:
                result = engine.ask(query.strip())
                st.session_state["last_result"] = result
            except OllamaError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"RAG failed: {exc}")

    result = st.session_state.get("last_result")
    if result:
        route_label = "API (database)" if result.route == "api" else "Gemma (chat)"
        st.caption(
            f"Route: **{route_label}** · intent: `{result.intent.value}` — {result.intent_reason}"
        )

        st.subheader("Answer")
        st.markdown(result.answer)

        st.subheader("Retrieved sources")
        if not result.sources:
            st.caption("No API retrieval for this route.")
        for doc in result.sources:
            with st.expander(f"[{doc['id']}] {doc['title']} · {doc['category']}"):
                st.write(doc["content"])

        if show_prompt and result.prompt:
            st.subheader("Prompt")
            st.code(result.prompt)
        elif show_prompt and result.route == "api":
            st.caption("No Gemma prompt — this answer came directly from API search results.")

    elif run and not query.strip():
        st.warning("Enter a question first.")

with draft_tab:
    render_mock_draft_tab()
