"""Streamlit UI for mock fantasy drafts."""

from __future__ import annotations

import streamlit as st

from draft.engine import MockDraftEngine
from draft.ffanalytics_loader import cache_is_fresh, load_active_players, load_player_cache
from draft.models import ROSTER_SLOTS, RankingSource, ScoringFormat
from draft.player_pool import refresh_players
from draft.rpy2_setup import rpy2_session


def _init_draft_state() -> None:
    if "mock_draft" not in st.session_state:
        st.session_state["mock_draft"] = None
    if "draft_pool" not in st.session_state:
        st.session_state["draft_pool"] = None


def _ensure_player_pool(*, force_refresh: bool = False) -> list:
    if force_refresh:
        with rpy2_session():
            with st.spinner("Loading players…"):
                st.session_state["draft_pool"] = refresh_players(force_refresh=True)
    elif st.session_state.get("draft_pool") is None:
        # Use JSON cache only on tab open — avoid a long R scrape until user clicks Refresh
        st.session_state["draft_pool"] = load_player_cache() or []
    return st.session_state["draft_pool"]


def _render_settings(
    pool_size: int,
) -> tuple[ScoringFormat, int, int, int, float, RankingSource] | None:
    st.subheader("League settings")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        scoring_label = st.selectbox(
            "Scoring",
            options=[s.value for s in ScoringFormat],
            index=0,
        )
    with col2:
        ranking_options = [r.value for r in RankingSource]
        ranking_label = st.selectbox(
            "Rankings",
            options=ranking_options,
            index=0,
            help="Consensus rankings source for CPU picks and best available.",
        )
    with col3:
        league_size = st.selectbox("League size", options=[8, 10, 12, 14], index=2)
    with col4:
        draft_slot = st.number_input(
            "Your draft slot",
            min_value=1,
            max_value=int(league_size),
            value=min(5, int(league_size)),
            step=1,
        )
    with col5:
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

    cpu_randomness = st.slider(
        "Draft unpredictability",
        min_value=0.0,
        max_value=1.0,
        value=0.35,
        step=0.05,
        help="Higher values make other teams less predictable.",
    )

    scoring = ScoringFormat(scoring_label)
    ranking_source = RankingSource(ranking_label)
    if pool_size:
        st.caption(f"{pool_size} players · up to {max_rounds} rounds")
    return scoring, int(league_size), int(draft_slot), int(rounds), float(cpu_randomness), ranking_source


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
        options = {}
        for p in ranked:
            rank = p.rank_for_source(draft.ranking_source)
            rank_str = f"#{int(rank)}" if rank < 999 else "—"
            label = (
                f"{rank_str} {p.name} ({p.position.value}, {p.team}) — "
                f"{p.fantasy_points(draft.settings.scoring):.1f} FPG"
            )
            options[label] = p
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

    # Auto-load players if cache is missing or stale and not already attempted
    if "auto_load_attempted" not in st.session_state:
        st.session_state["auto_load_attempted"] = False
    
    if not st.session_state["auto_load_attempted"]:
        if not cache_is_fresh():
            st.session_state["auto_load_attempted"] = True
            try:
                with rpy2_session():
                    with st.spinner("Loading player pool…"):
                        pool_loaded = load_active_players(force_refresh=True)
                        refresh_players(force_refresh=True)
                        st.session_state["draft_pool"] = pool_loaded
                        st.session_state["players_loaded_successfully"] = True
            except Exception as exc:
                st.error(f"Could not auto-load players: {exc}")
                st.session_state["players_loaded_successfully"] = False
        else:
            # Cache is fresh, just load from cache
            st.session_state["auto_load_attempted"] = True
            cached = load_player_cache()
            if cached:
                st.session_state["draft_pool"] = cached
                st.session_state["players_loaded_successfully"] = True

    pool = _ensure_player_pool()
    pool_size = len(pool)

    load_col, _ = st.columns([1, 3])
    with load_col:
        if st.button("Load players", use_container_width=True):
            try:
                with rpy2_session():
                    with st.spinner("Loading player pool…"):
                        pool_loaded = load_active_players(force_refresh=True)
                        refresh_players(force_refresh=True)
                        st.session_state["draft_pool"] = pool_loaded
                        st.session_state["players_loaded_successfully"] = True
                if not pool_loaded:
                    st.error("No players were returned. Try again in a few minutes.")
                    st.session_state["players_loaded_successfully"] = False
                else:
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not load players: {exc}")
                st.session_state["players_loaded_successfully"] = False
                pool = _ensure_player_pool()
                pool_size = len(pool)
    
    if st.session_state.get("players_loaded_successfully"):
        st.success("Players successfully loaded!", icon="✅")

    if pool_size == 0:
        st.info("Load players to start a mock draft.")

    settings = _render_settings(pool_size)
    if settings is None:
        return

    scoring, league_size, draft_slot, rounds, cpu_randomness, ranking_source = settings

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
                    cpu_randomness=cpu_randomness,
                    ranking_source=ranking_source,
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
        return

    meta = draft.settings
    st.caption(
        f"{meta.scoring.value} · {draft.ranking_source.value} rankings · "
        f"{meta.league_size} teams · pick {meta.draft_slot} · "
        f"round {draft.current_round} · "
        f"#{min(draft.current_overall, draft.total_picks)} of {draft.total_picks}"
    )

    board_col, roster_col = st.columns([3, 2])
    with board_col:
        _render_pick_controls(draft)
        _render_draft_board(draft)
    with roster_col:
        _render_user_roster(draft)

        st.subheader("Best available")
        for player in draft.rank_available()[:8]:
            rank = player.rank_for_source(draft.ranking_source)
            rank_str = f"#{int(rank)}" if rank < 999 else "—"
            st.write(
                f"**{player.name}** ({player.position.value}, {player.team}) — "
                f"{player.fantasy_points(draft.settings.scoring):.1f} FPG · {rank_str}"
            )

        _render_monte_carlo_lookahead(draft)


def _render_monte_carlo_lookahead(draft: MockDraftEngine) -> None:
    if draft.is_complete or draft.pool_exhausted or not draft.is_user_turn:
        return

    num_sims = 40
    with st.spinner("Calculating pick outlook…"):
        probabilities = draft.simulate_availability_at_next_user_pick(num_sims=num_sims)

    ranked = draft.rank_available()[:10]
    if not ranked:
        return

    rows = []
    for player in ranked:
        pct = probabilities.get(player.name, 0.0) * 100
        rank = player.rank_for_source(draft.ranking_source)
        rows.append(
            {
                "Player": player.name,
                "Pos": player.position.value,
                "Team": player.team,
                "Rank": int(rank) if rank < 999 else "—",
                "FPG": round(player.fantasy_points(draft.settings.scoring), 1),
                "Avail next pick": f"{pct:.0f}%",
                "_pct": pct,
            }
        )
    
    rows.sort(key=lambda r: r["_pct"], reverse=True)
    for row in rows:
        del row["_pct"]

    st.subheader("Likely available next pick")
    st.dataframe(rows, use_container_width=True, hide_index=True)
