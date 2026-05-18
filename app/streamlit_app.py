"""Streamlit data platform for the local StatShift prototype."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from rag.engine import RAGEngine
from rag.ollama_client import OllamaError

st.set_page_config(
    page_title="StatShift",
    page_icon="📊",
    layout="wide",
)

st.title("StatShift")
st.caption("Local prototype — Streamlit → RAG → FastAPI (read-only) → SQLite → Ollama/Gemma")

engine = RAGEngine()

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

query = st.text_input(
    "Ask about players, teams, or league stats",
    placeholder="e.g. How did Victor Wembanyama perform in 2024-25?",
)

col1, col2 = st.columns([1, 4])
with col1:
    run = st.button("Run RAG", type="primary", use_container_width=True)
with col2:
    show_prompt = st.checkbox("Show prompt sent to Gemma")

if run and query.strip():
    with st.spinner("Retrieving context and generating answer..."):
        try:
            result = engine.ask(query.strip())
            st.session_state["last_result"] = result
        except OllamaError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"RAG failed: {exc}")

result = st.session_state.get("last_result")
if result:
    st.subheader("Answer")
    st.markdown(result.answer)

    st.subheader("Retrieved sources")
    for doc in result.sources:
        with st.expander(f"[{doc['id']}] {doc['title']} · {doc['category']}"):
            st.write(doc["content"])

    if show_prompt:
        st.subheader("Prompt")
        st.code(result.prompt)

elif run and not query.strip():
    st.warning("Enter a question first.")
