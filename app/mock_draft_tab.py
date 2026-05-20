"""Streamlit UI for mock fantasy drafts."""

from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from draft.engine import MockDraftEngine, _snake_team_index
from draft.ffanalytics_loader import cache_is_fresh, load_active_players, load_player_cache
from draft.models import POSITION_COLORS, ROSTER_SLOTS, Position, RankingSource, ScoringFormat
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


def _position_colors(position: str) -> tuple[str, str]:
    """Return (background, text) hex colors for a position."""
    return POSITION_COLORS.get(position, ("#374151", "#FFFFFF"))


def _truncate_name(name: str, max_len: int = 14) -> str:
    return name if len(name) <= max_len else name[: max_len - 1] + "…"


def _player_pick_html(
    name: str,
    position: str,
    team: str = "",
    *,
    highlight: bool = False,
) -> str:
    """HTML for a Sleeper-style colored pick cell."""
    bg, fg = _position_colors(position)
    border = "2px solid #FBBF24" if highlight else "1px solid rgba(255,255,255,0.15)"
    team_line = f'<div style="font-size:0.75em;opacity:0.9;">{position}'
    if team:
        team_line += f" · {team}"
    team_line += "</div>"
    return (
        f'<div style="background:{bg};color:{fg};padding:6px 8px;border-radius:6px;'
        f'border:{border};margin-bottom:4px;line-height:1.25;">'
        f'<div style="font-weight:600;font-size:0.9em;">{_truncate_name(name)}</div>'
        f"{team_line}</div>"
    )


def _on_clock_html(text: str, *, is_user: bool) -> str:
    bg = "#F59E0B" if is_user else "#4B5563"
    return (
        f'<div style="background:{bg};color:#FFFFFF;padding:6px 8px;border-radius:6px;'
        f'border:2px dashed #FBBF24;font-size:0.85em;font-weight:600;text-align:center;">'
        f"{text}</div>"
    )


def _empty_cell_html(round_num: int) -> str:
    return (
        f'<div style="background:#1F2937;color:#6B7280;padding:6px 8px;border-radius:6px;'
        f'font-size:0.75em;text-align:center;border:1px solid #374151;">R{round_num}</div>'
    )


def _render_position_legend() -> None:
    chips = []
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        bg, fg = _position_colors(pos)
        chips.append(
            f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;'
            f'font-size:0.75em;font-weight:600;margin-right:6px;">{pos}</span>'
        )
    st.markdown("".join(chips), unsafe_allow_html=True)


def _render_settings(
    pool_size: int,
) -> tuple[ScoringFormat, int, int, int, float, RankingSource, str] | None:
    st.subheader("League settings")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

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
    with col6:
        user_team_name = st.text_input(
            "Your team name",
            value="My Team",
            max_chars=25,
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
    return scoring, int(league_size), int(draft_slot), int(rounds), float(cpu_randomness), ranking_source, user_team_name


def _render_sleeper_draft_board(draft: MockDraftEngine) -> None:
    """Render Sleeper-style grid board (teams as columns, rounds as rows)."""
    st.subheader("Draft Board")
    _render_position_legend()

    num_teams = draft.settings.league_size
    num_rounds = draft.settings.rounds
    user_team_idx = draft.settings.draft_slot - 1

    pick_grid: dict[tuple[int, int], tuple[str, str, str]] = {}
    for pick in draft.picks:
        pick_grid[(pick.round, pick.team_index)] = (
            pick.player.name,
            pick.player.position.value,
            pick.player.team,
        )

    current_round = draft.current_round
    current_team = draft.current_team_index if not draft.is_complete else -1

    header_cols = st.columns(num_teams)
    for i, col in enumerate(header_cols):
        team_name = draft.get_team_name(i)
        short_name = _truncate_name(team_name, 16)
        if i == user_team_idx:
            col.markdown(f"**{short_name}** 🏈")
        else:
            col.markdown(f"**{short_name}**")

    for round_num in range(1, num_rounds + 1):
        row_cols = st.columns(num_teams)

        for pick_in_round in range(1, num_teams + 1):
            team_idx = _snake_team_index(round_num, pick_in_round, num_teams)
            col = row_cols[team_idx]

            pick_data = pick_grid.get((round_num, team_idx))
            is_current_pick = round_num == current_round and team_idx == current_team
            is_user_team = team_idx == user_team_idx

            if pick_data:
                name, position, team = pick_data
                html = _player_pick_html(
                    name,
                    position,
                    team,
                    highlight=is_user_team,
                )
                col.markdown(html, unsafe_allow_html=True)
            elif is_current_pick:
                remaining = draft.time_remaining()
                if draft.is_user_turn:
                    text = f"⏱️ YOUR PICK ({remaining}s)"
                else:
                    text = f"⏱️ On Clock ({remaining}s)"
                col.markdown(
                    _on_clock_html(text, is_user=draft.is_user_turn),
                    unsafe_allow_html=True,
                )
            else:
                col.markdown(_empty_cell_html(round_num), unsafe_allow_html=True)


def _render_user_roster(draft: MockDraftEngine) -> None:
    st.subheader("Your roster")
    roster = draft.user_roster()
    if not roster.picks:
        st.caption("No players drafted yet.")
        return

    pos_order = {p: i for i, p in enumerate(Position)}
    sorted_picks = sorted(roster.picks, key=lambda p: pos_order.get(p.position, 99))

    for p in sorted_picks:
        fpg = round(p.fantasy_points(draft.settings.scoring), 1)
        bg, fg = _position_colors(p.position.value)
        st.markdown(
            f'<div style="display:flex;align-items:stretch;margin-bottom:6px;border-radius:6px;'
            f'overflow:hidden;border:1px solid rgba(255,255,255,0.1);">'
            f'<div style="background:{bg};color:{fg};padding:8px 10px;min-width:36px;'
            f'font-weight:700;font-size:0.85em;display:flex;align-items:center;">'
            f"{p.position.value}</div>"
            f'<div style="flex:1;background:#1F2937;color:#F9FAFB;padding:8px 10px;">'
            f'<div style="font-weight:600;">{p.name}</div>'
            f'<div style="font-size:0.8em;color:#9CA3AF;">{p.team} · {fpg} FPG</div>'
            f"</div></div>",
            unsafe_allow_html=True,
        )

    filled = []
    for slot, need in ROSTER_SLOTS.items():
        if slot == "FLEX":
            continue
        pos_key = slot
        have = sum(1 for p in roster.picks if p.position.value == pos_key)
        filled.append(f"{slot}: {have}/{need}")
    st.caption("Starters · " + " · ".join(filled))


def _render_pick_timer(draft: MockDraftEngine) -> None:
    """Render the countdown timer for the current pick."""
    remaining = draft.time_remaining()
    
    if remaining <= 10:
        st.error(f"⏱️ **{remaining}** seconds remaining!")
    elif remaining <= 20:
        st.warning(f"⏱️ **{remaining}** seconds remaining")
    else:
        st.info(f"⏱️ **{remaining}** seconds remaining")


def _handle_timer_expiration(draft: MockDraftEngine) -> bool:
    """Auto-draft for the team on the clock when their 30s expires. One pick per timeout."""
    if draft.is_timer_expired() and not draft.is_complete:
        draft.auto_pick()
        if not draft.is_complete:
            draft.start_pick_timer()
        return True
    return False


def _render_pick_controls(draft: MockDraftEngine) -> None:
    if draft.is_complete:
        if draft.pool_exhausted and len(draft.picks) < draft.settings.league_size * draft.requested_rounds:
            st.warning(
                f"Draft stopped early: player pool ran out after **{len(draft.picks)}** picks "
                f"(round {draft.picks[-1].round if draft.picks else 0})."
            )
        else:
            st.success("Draft complete!")
        return

    if _handle_timer_expiration(draft):
        st.rerun()

    st.subheader("On the clock")
    round_num = draft.current_round
    overall = draft.current_overall
    team_name = draft.get_team_name(draft.current_team_index)

    _render_pick_timer(draft)
    st.caption(f"Each team has **{draft.pick_time_limit}** seconds to pick.")

    if draft.is_user_turn:
        st.info(f"Round {round_num} · Pick {overall} — **{team_name} (You)**")
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
            if not draft.is_complete:
                draft.start_pick_timer()
            st.rerun()
    else:
        st.warning(
            f"Round {round_num} · Pick {overall} — **{team_name}** is on the clock "
            f"({draft.time_remaining()}s left)"
        )
        if st.button("Skip to your pick", use_container_width=True):
            while not draft.is_complete and not draft.is_user_turn:
                draft.auto_pick()
            if not draft.is_complete:
                draft.start_pick_timer()
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

    scoring, league_size, draft_slot, rounds, cpu_randomness, ranking_source, user_team_name = settings

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
                    user_team_name=user_team_name,
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

    st_autorefresh(interval=1000, key="draft_timer_refresh")

    meta = draft.settings
    st.caption(
        f"{meta.scoring.value} · {draft.ranking_source.value} rankings · "
        f"{meta.league_size} teams · pick {meta.draft_slot} · "
        f"round {draft.current_round} · "
        f"#{min(draft.current_overall, draft.total_picks)} of {draft.total_picks}"
    )

    _render_pick_controls(draft)
    
    st.divider()
    
    _render_sleeper_draft_board(draft)
    
    st.divider()
    
    roster_col, best_col = st.columns([1, 1])
    with roster_col:
        _render_user_roster(draft)
    with best_col:
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
