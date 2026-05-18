"""Streamlit UI for mock fantasy drafts."""

from __future__ import annotations

import streamlit as st

from draft.engine import MockDraftEngine
from draft.ffanalytics_loader import load_active_players, load_player_cache
from draft.models import ROSTER_SLOTS, ScoringFormat
from draft.player_pool import cache_status, refresh_players
from draft.rpy2_setup import rpy2_session


def _init_draft_state() -> None:
    if "mock_draft" not in st.session_state:
        st.session_state["mock_draft"] = None
    if "draft_pool" not in st.session_state:
        st.session_state["draft_pool"] = None


def _ensure_player_pool(*, force_refresh: bool = False) -> list:
    if force_refresh:
        with rpy2_session():
            with st.spinner("Loading players from ffanalytics…"):
                st.session_state["draft_pool"] = refresh_players(force_refresh=True)
    elif st.session_state.get("draft_pool") is None:
        # Use JSON cache only on tab open — avoid a long R scrape until user clicks Refresh
        st.session_state["draft_pool"] = load_player_cache() or []
    return st.session_state["draft_pool"]


def _render_settings(pool_size: int) -> tuple[ScoringFormat, int, int, int] | None:
    st.subheader("League settings")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        scoring_label = st.selectbox(
            "Scoring",
            options=[s.value for s in ScoringFormat],
            index=0,
        )
    with col2:
        league_size = st.selectbox("League size", options=[8, 10, 12, 14], index=2)
    with col3:
        draft_slot = st.number_input(
            "Your draft slot",
            min_value=1,
            max_value=int(league_size),
            value=min(5, int(league_size)),
            step=1,
        )
    with col4:
        if pool_size:
            max_rounds = max(1, pool_size // max(int(league_size), 1))
        else:
            max_rounds = 15
        rounds = st.number_input(
            "Rounds",
            min_value=1,
            max_value=max(1, max_rounds),
            value=min(15, max(1, max_rounds)),
            step=1,
            disabled=pool_size == 0,
        )

    scoring = ScoringFormat(scoring_label)
    st.caption(
        f"Player pool: **{pool_size}** ranked players (QB/RB/WR/TE/K) · "
        f"up to **{max_rounds}** rounds for a **{league_size}**-team league"
    )
    return scoring, int(league_size), int(draft_slot), int(rounds)


def _render_draft_board(draft: MockDraftEngine) -> None:
    st.subheader("Draft board")
    rows = []
    for pick in draft.picks:
        team_label = (
            f"Team {pick.team_index + 1} (You)"
            if pick.team_index == draft.settings.draft_slot - 1
            else f"Team {pick.team_index + 1}"
        )
        rows.append(
            {
                "Overall": pick.overall,
                "Round": pick.round,
                "Pick": pick.pick_in_round,
                "Team": team_label,
                "Player": pick.player.name,
                "Pos": pick.player.position.value,
                "Team abbr": pick.player.team,
                "FPG": round(
                    pick.player.fantasy_points(draft.settings.scoring), 1
                ),
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No picks yet.")


def _render_user_roster(draft: MockDraftEngine) -> None:
    st.subheader("Your roster")
    roster = draft.user_roster()
    if not roster.picks:
        st.caption("No players drafted yet.")
        return

    rows = [
        {
            "Player": p.name,
            "Pos": p.position.value,
            "Team": p.team,
            "FPG": round(p.fantasy_points(draft.settings.scoring), 1),
        }
        for p in roster.picks
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    filled = []
    for slot, need in ROSTER_SLOTS.items():
        if slot == "FLEX":
            continue
        pos_key = slot
        have = sum(1 for p in roster.picks if p.position.value == pos_key)
        filled.append(f"{slot}: {have}/{need}")
    st.caption("Starters · " + " · ".join(filled))


def _render_pick_controls(draft: MockDraftEngine) -> None:
    if draft.is_complete:
        if draft.pool_exhausted and len(draft.picks) < draft.settings.league_size * draft.requested_rounds:
            st.warning(
                f"Draft stopped early: player pool ran out after **{len(draft.picks)}** picks "
                f"(round {draft.picks[-1].round if draft.picks else 0})."
            )
        else:
            st.success("Draft complete.")
        return

    st.subheader("On the clock")
    round_num = draft.current_round
    overall = draft.current_overall
    team_num = draft.current_team_index + 1

    if draft.is_user_turn:
        st.info(f"Round {round_num} · Pick {overall} — **Your pick**")
        ranked = draft.rank_available()[:25]
        if not ranked:
            st.error("No players left in the pool.")
            return
        options = {
            f"{p.name} ({p.position.value}, {p.team}) — "
            f"{p.fantasy_points(draft.settings.scoring):.1f} FPG": p
            for p in ranked
        }
        choice = st.selectbox("Select player", options=list(options.keys()))
        if st.button("Draft player", type="primary", use_container_width=True):
            draft.make_pick(options[choice])
            draft.run_cpu_picks_until_user()
            st.rerun()
    else:
        st.warning(f"Round {round_num} · Pick {overall} — Team {team_num} is picking…")
        if st.button("Simulate to your pick", use_container_width=True):
            draft.run_cpu_picks_until_user()
            st.rerun()


def render_mock_draft_tab() -> None:
    _init_draft_state()
    st.markdown(
        "Configure scoring and league size, then run a **snake mock draft** with "
        "**projections and ADP** from [ffanalytics](https://github.com/FantasyFootballAnalytics/ffanalytics) "
        "(QB/RB/WR/TE/K)."
    )

    st.caption(cache_status())

    refresh_col, _ = st.columns([1, 3])
    with refresh_col:
        if st.button("Refresh player pool from ffanalytics", use_container_width=True):
            try:
                with rpy2_session():
                    with st.spinner("Scraping projections and ADP via ffanalytics…"):
                        pool_loaded = load_active_players(force_refresh=True)
                        refresh_players(force_refresh=True)
                        st.session_state["draft_pool"] = pool_loaded
                if not pool_loaded:
                    st.error("ffanalytics returned no draftable players.")
                else:
                    st.success(f"Loaded {len(pool_loaded)} players.")
                    st.rerun()
            except Exception as exc:
                st.error(f"ffanalytics sync failed: {exc}")

    pool = _ensure_player_pool()
    pool_size = len(pool)

    if pool_size == 0:
        st.warning(
            "No player pool loaded. Click **Refresh player pool from ffanalytics** "
            "(first run may take several minutes)."
        )

    settings = _render_settings(pool_size)
    if settings is None:
        return

    scoring, league_size, draft_slot, rounds = settings

    slot_cols = st.columns([1, 1, 2])
    with slot_cols[0]:
        if st.button(
            "Start new draft",
            type="primary",
            use_container_width=True,
            disabled=pool_size == 0,
        ):
            try:
                st.session_state["mock_draft"] = MockDraftEngine.create(
                    scoring=scoring,
                    league_size=league_size,
                    draft_slot=draft_slot,
                    rounds=rounds,
                    pool=pool,
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with slot_cols[1]:
        if st.button("Reset", use_container_width=True):
            st.session_state["mock_draft"] = None
            st.rerun()

    draft: MockDraftEngine | None = st.session_state.get("mock_draft")
    if draft is None:
        st.info("Set your parameters and click **Start new draft**.")
        st.markdown(
            f"""
            **Roster slots:** {", ".join(f"{k}×{v}" for k, v in ROSTER_SLOTS.items())}

            **Player source:** ffanalytics projections + ADP (~{pool_size} players).
            First load scrapes multiple sites and may take several minutes; cached 24 hours
            in the `statshift_data` Docker volume (`data/ffanalytics_players.json`).
            """
        )
        return

    meta = draft.settings
    rounds_note = f"{meta.rounds} rounds"
    if draft.requested_rounds > meta.rounds:
        rounds_note += f" (capped from {draft.requested_rounds}; pool limit)"
    st.caption(
        f"{meta.scoring.value} · {meta.league_size} teams · "
        f"slot {meta.draft_slot} · {rounds_note} · "
        f"Pick {min(draft.current_overall, draft.total_picks)} of {draft.total_picks} · "
        f"{len(draft.available)} players left"
    )

    board_col, roster_col = st.columns([3, 2])
    with board_col:
        _render_pick_controls(draft)
        _render_draft_board(draft)
    with roster_col:
        _render_user_roster(draft)

        st.subheader("Best available")
        for player in draft.rank_available()[:8]:
            st.write(
                f"**{player.name}** ({player.position.value}, {player.team}) — "
                f"{player.fantasy_points(draft.settings.scoring):.1f} FPG"
            )
