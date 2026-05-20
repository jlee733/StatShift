"""Ask page - RAG-powered Q&A."""

from __future__ import annotations

import streamlit as st

from rag.engine import RAGEngine
from rag.ollama_client import OllamaClient, OllamaError

st.title("StatShift")

# Model selection
model_options = {
    "Gemma 2": "gemma2:latest",
    "Llama 3": "llama3:latest",
}

model_col, _ = st.columns([1, 3])
with model_col:
    selected_model_name = st.selectbox(
        "AI Model",
        options=list(model_options.keys()),
        index=0,
    )
selected_model = model_options[selected_model_name]

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
            ollama_client = OllamaClient(model=selected_model)
            engine = RAGEngine(ollama=ollama_client)
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
