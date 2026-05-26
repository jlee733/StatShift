"""Ask page - MCP Agent-powered Q&A with tool calling."""

from __future__ import annotations

import json

import streamlit as st

from llm.mcp_agent import MCPAgent
from llm.ollama_client import OllamaClient, OllamaError

st.title("StatShift")

query = st.text_input(
    "Ask about players, matchups, injuries, or fantasy scoring",
    placeholder="e.g. What are Patrick Mahomes' stats this season?",
)

col1, col2 = st.columns([1, 4])
with col1:
    run = st.button("Ask", type="primary", use_container_width=True)
with col2:
    show_tools = st.checkbox("Show tool calls")

if run and query.strip():
    with st.spinner("Thinking... (Gemma can take up to a minute on CPU)"):
        try:
            ollama_client = OllamaClient()
            agent = MCPAgent(ollama=ollama_client)
            result = agent.ask(query.strip())
            st.session_state["last_result"] = result
        except OllamaError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

result = st.session_state.get("last_result")
if result:
    st.subheader("Answer")
    if getattr(result, "route", None) == "conversational":
        st.caption("Answered from the model (general knowledge). Ask for specific stats to query StatShift.")
    elif getattr(result, "route", None) == "database":
        st.caption("Answered using StatShift data.")
    st.markdown(result.answer)

    if result.tool_executions and show_tools:
        st.subheader("Tool Calls")
        for i, execution in enumerate(result.tool_executions, 1):
            status = "error" if execution.error else "success"
            icon = "❌" if execution.error else "✅"
            with st.expander(f"{icon} {execution.name}({', '.join(f'{k}={v!r}' for k, v in execution.arguments.items())})"):
                if execution.error:
                    st.error(execution.error)
                elif execution.result:
                    if isinstance(execution.result, list):
                        st.write(f"Returned {len(execution.result)} results")
                        if execution.result:
                            st.json(execution.result[:3] if len(execution.result) > 3 else execution.result)
                            if len(execution.result) > 3:
                                st.caption(f"... and {len(execution.result) - 3} more")
                    elif isinstance(execution.result, dict):
                        st.json(execution.result)
                    else:
                        st.write(execution.result)

        st.caption(f"Model: {result.model} · Iterations: {result.iterations}")

elif run and not query.strip():
    st.warning("Enter a question first.")
