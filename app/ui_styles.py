"""Shared Streamlit UI styles for readable, non-truncated text."""

from __future__ import annotations

import streamlit as st


def inject_global_styles() -> None:
    """Apply CSS so long labels and values wrap instead of showing ellipsis."""
    st.markdown(
        """
        <style>
        /* Metric values (Draft, College, etc.) */
        [data-testid="stMetricValue"] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            word-break: break-word;
            line-height: 1.25;
            font-size: 0.95rem;
        }
        [data-testid="stMetricLabel"] {
            white-space: normal !important;
        }

        /* Dataframes and tables */
        [data-testid="stDataFrame"] div {
            white-space: normal !important;
            word-break: break-word;
        }

        /* Captions and subheaders in narrow columns */
        .stCaption, .stMarkdown p {
            overflow-wrap: anywhere;
        }

        /* Draft board pick cells */
        .statshift-pick-cell,
        .statshift-team-header,
        .statshift-on-clock {
            word-break: break-word;
            overflow-wrap: anywhere;
            white-space: normal;
            line-height: 1.2;
        }
        .statshift-pick-cell .player-name {
            font-weight: 600;
            font-size: 0.72rem;
        }
        .statshift-pick-cell .player-meta {
            font-size: 0.65rem;
            opacity: 0.9;
        }
        .statshift-team-header {
            font-size: 0.78rem;
            font-weight: 700;
            text-align: center;
            padding: 2px 0;
        }
        .statshift-on-clock {
            font-size: 0.72rem;
            font-weight: 600;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
