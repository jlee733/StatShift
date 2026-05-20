"""Streamlit UI for NFL player research."""

from __future__ import annotations

import html

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from sdks.distribution_fit import fit_best_distribution, format_params_string
from sdks.espn_player_loader import (
    CollegeSeasonStats,
    CombineMetrics,
    GameLogEntry,
    InjuryInfo,
    NewsArticle,
    PlayerProfile,
    SeasonStats,
    calculate_fantasy_points,
    get_available_seasons,
    get_player_college_stats,
    get_player_combine,
    get_player_gamelog,
    get_player_injuries,
    get_player_news,
    get_player_profile,
    get_player_seasons,
    get_player_stats,
    is_upcoming_rookie,
    search_players,
)


def _init_research_state() -> None:
    if "research_selected_player" not in st.session_state:
        st.session_state["research_selected_player"] = None
    if "research_search_results" not in st.session_state:
        st.session_state["research_search_results"] = []


def _render_search() -> None:
    """Render the player search section."""
    st.subheader("Search Players")

    if not st.session_state.get("research_selected_player"):
        st.info("Search for a player below to view their profile, stats, and news.")

    with st.form("research_player_search", clear_on_submit=False):
        col1, col2 = st.columns([4, 1])
        with col1:
            query = st.text_input(
                "Enter player name",
                placeholder="e.g. Patrick Mahomes",
                label_visibility="collapsed",
            )
        with col2:
            search_clicked = st.form_submit_button(
                "Search", type="primary", use_container_width=True
            )

    if search_clicked and query.strip():
        with st.spinner("Searching..."):
            results = search_players(query.strip())
            st.session_state["research_search_results"] = results
            if not results:
                st.warning("No players found. Try a different search term.")
    
    results = st.session_state.get("research_search_results", [])
    if results and not st.session_state.get("research_selected_player"):
        st.caption(f"Found {len(results)} active player(s)")
        
        for player in results:
            img_col, info_col, btn_col = st.columns([1, 5, 1])
            with img_col:
                headshot = player.get("headshot", "")
                if headshot:
                    st.image(headshot, width=72)
                else:
                    st.markdown("—")
            with info_col:
                display = f"**{player['name']}** — {player['position']}, {player['team']}"
                st.markdown(display)
            with btn_col:
                if st.button("Select", key=f"select_{player['id']}", use_container_width=True):
                    st.session_state["research_selected_player"] = player["id"]
                    st.session_state["research_search_results"] = []
                    st.rerun()


def _college_stats_to_rows(seasons: list[CollegeSeasonStats]) -> list[dict]:
    """Convert college season stats to dataframe rows, omitting empty columns."""
    columns = [
        ("Season", "season"),
        ("Team", "team"),
        ("GP", "games_played"),
        ("Cmp", "completions"),
        ("Pass Yds", "passing_yards"),
        ("Pass TD", "passing_tds"),
        ("INT", "interceptions"),
        ("Rush Att", "rush_attempts"),
        ("Rush Yds", "rushing_yards"),
        ("Rush TD", "rushing_tds"),
        ("Rec", "receptions"),
        ("Rec Yds", "receiving_yards"),
        ("Rec TD", "receiving_tds"),
    ]
    raw_rows = []
    for season in seasons:
        raw_rows.append({label: getattr(season, attr) for label, attr in columns})

    active_labels = ["Season"]
    for label, _ in columns[1:]:
        if any(row.get(label, "—") not in ("—", "0", "0.0", "") for row in raw_rows):
            active_labels.append(label)

    return [{label: row[label] for label in active_labels} for row in raw_rows]


def _render_college_stats(profile: PlayerProfile) -> None:
    """Show college stats table for pre-season rookies."""
    with st.spinner("Loading college stats..."):
        seasons = get_player_college_stats(profile.id)

    if not seasons:
        st.info("No college statistics available for this player.")
        return

    st.subheader("College stats")
    rows = _college_stats_to_rows(seasons)
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_profile_card(profile: PlayerProfile) -> None:
    """Render the player profile card."""
    st.divider()
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if profile.headshot_url:
            st.image(profile.headshot_url, width=150)
        else:
            st.markdown("*No photo available*")
    
    with col2:
        rookie = is_upcoming_rookie(profile.draft_year)
        name_line = f"## {profile.name}"
        if rookie:
            name_line += ' <span style="background:#F59E0B;color:#111;padding:2px 10px;border-radius:12px;font-size:0.45em;vertical-align:middle;margin-left:8px;">Rookie</span>'
        st.markdown(name_line, unsafe_allow_html=True)
        st.markdown(f"**{profile.position}** | #{profile.jersey} | {profile.team}")
        
        info_col1, info_col2, info_col3 = st.columns(3)
        with info_col1:
            st.metric("Height", profile.height)
            st.metric("College", profile.college)
        with info_col2:
            st.metric("Weight", profile.weight)
            st.metric("Draft", profile.draft_info)
        with info_col3:
            if profile.age:
                st.metric("Age", profile.age)
            st.metric("Experience", f"{profile.experience} yrs")
    
    status_color = "green" if profile.status == "Active" else "orange"
    st.markdown(f"**Status:** :{status_color}[{profile.status}]")

    if is_upcoming_rookie(profile.draft_year):
        _render_college_stats(profile)


def _create_timeseries_chart(gamelog: list[GameLogEntry], scoring_key: str, scoring_label: str) -> plt.Figure:
    """Create time series chart of fantasy points by week."""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    
    if not gamelog:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)
        ax.set_xlabel("Week")
        ax.set_ylabel("Fantasy Points")
        return fig
    
    weeks = []
    points = []
    
    for game in gamelog:
        fp = calculate_fantasy_points(game, scoring_key)
        weeks.append(game.week)
        points.append(fp)
    
    if weeks:
        ax.plot(weeks, points, marker='o', linestyle='-', linewidth=2, markersize=6, 
                color='#2E86AB', markerfacecolor='#2E86AB', markeredgecolor='white', markeredgewidth=1.5)
        ax.fill_between(weeks, points, alpha=0.2, color='#2E86AB')
        
        max_week = max(weeks)
        ax.set_xlim(0.5, max_week + 0.5)
        ax.set_xticks(range(1, max_week + 1))
        
        if points:
            y_max = max(points) * 1.1 if max(points) > 0 else 10
            ax.set_ylim(0, y_max)
    
    ax.set_xlabel("Week", fontsize=10)
    ax.set_ylabel(f"Fantasy Points ({scoring_label})", fontsize=10)
    ax.set_title("Weekly Performance", fontsize=11, fontweight='bold')
    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    
    return fig


def _create_histogram_with_fit(fp_data: list[float], scoring_label: str) -> plt.Figure:
    """Create histogram with fitted distribution overlay."""
    nonzero = [x for x in fp_data if x > 0]
    
    fig, ax = plt.subplots(figsize=(6, 3.5))
    
    if not nonzero:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", transform=ax.transAxes)
        ax.set_xlabel("Fantasy Points")
        ax.set_ylabel("Density")
        return fig
    
    ax.hist(nonzero, bins="auto", density=True, alpha=0.7, color="steelblue", edgecolor="white", label="Data")
    
    if len(nonzero) >= 5:
        dist_name, params, pdf_fn = fit_best_distribution(nonzero)
        x = np.linspace(min(nonzero), max(nonzero), 100)
        ax.plot(x, pdf_fn(x), "r-", lw=2, label=dist_name)
        
        param_str = format_params_string(params)
        ax.set_title(f"{dist_name} Distribution\n({param_str})", fontsize=10, fontweight='bold')
    else:
        ax.set_title(f"Fantasy Points Distribution\n(Need 5+ games for model fit, have {len(nonzero)})", fontsize=9, fontweight='bold')
    
    ax.set_xlabel(f"Fantasy Points ({scoring_label})", fontsize=10)
    ax.set_ylabel("Density", fontsize=10)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    
    return fig


def _build_stats_table(gamelog: list[GameLogEntry], scoring_key: str) -> list[dict]:
    """Build stats table rows from game log."""
    rows = []
    for game in gamelog:
        fp = calculate_fantasy_points(game, scoring_key)
        rows.append({
            "Week": game.week,
            "Pass Yds": game.passing_yards,
            "Pass TD": game.passing_tds,
            "INT": game.interceptions,
            "Rush Yds": game.rushing_yards,
            "Rush TD": game.rushing_tds,
            "Rec": game.receptions,
            "Rec Yds": game.receiving_yards,
            "Rec TD": game.receiving_tds,
            "Fum": game.fumbles_lost,
            "FP": fp,
        })
    return rows


def _render_stats_tab(player_id: str) -> None:
    """Render the statistics sub-tab with season checkboxes and histogram."""
    scoring_options = ["PPR", "Half-PPR", "Standard"]
    scoring_label = st.selectbox("Scoring Format", options=scoring_options, index=0)
    scoring_key = scoring_label.lower().replace("-", "_")
    
    with st.spinner("Loading available seasons..."):
        seasons = get_player_seasons(player_id)
    
    if not seasons:
        st.info("No season data available for this player.")
        return
    
    selected_seasons = st.multiselect(
        "Select Seasons",
        options=seasons,
        default=[seasons[0]] if seasons else [],
    )
    
    if not selected_seasons:
        st.info("Select one or more seasons above to view stats.")
        return
    
    for season in selected_seasons:
        st.subheader(f"{season} Season")
        
        with st.spinner(f"Loading {season} game log..."):
            gamelog = get_player_gamelog(player_id, season)
        
        if not gamelog:
            st.warning(f"No game data available for {season}.")
            continue
        
        fp_list = [calculate_fantasy_points(g, scoring_key) for g in gamelog]
        
        col_table, col_charts = st.columns(2)
        
        with col_table:
            st.caption(f"Games: {len(gamelog)}")
            rows = _build_stats_table(gamelog, scoring_key)
            st.dataframe(rows, use_container_width=True, hide_index=True)
        
        with col_charts:
            nonzero_count = len([x for x in fp_list if x > 0])
            st.caption(f"Games with stats: {nonzero_count}")
            
            fig_ts = _create_timeseries_chart(gamelog, scoring_key, scoring_label)
            st.pyplot(fig_ts)
            plt.close(fig_ts)
            
            fig_hist = _create_histogram_with_fit(fp_list, scoring_label)
            st.pyplot(fig_hist)
            plt.close(fig_hist)
        
        st.divider()


def _render_combine_tab(player_id: str) -> None:
    """Render the combine metrics sub-tab."""
    with st.spinner("Loading combine data..."):
        combine = get_player_combine(player_id)
    
    if not combine:
        st.info("No combine data available for this player.")
        return
    
    if combine.year:
        st.caption(f"NFL Combine {combine.year}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("40-Yard Dash", f"{combine.forty_yard}s" if combine.forty_yard else "—")
        st.metric("Bench Press", f"{combine.bench_press} reps" if combine.bench_press else "—")
        st.metric("3-Cone Drill", f"{combine.three_cone}s" if combine.three_cone else "—")
    
    with col2:
        st.metric("Vertical Jump", f'{combine.vertical_jump}"' if combine.vertical_jump else "—")
        st.metric("Broad Jump", f'{combine.broad_jump}"' if combine.broad_jump else "—")
        st.metric("20-Yard Shuttle", f"{combine.shuttle}s" if combine.shuttle else "—")
    
    all_none = all([
        combine.forty_yard is None,
        combine.vertical_jump is None,
        combine.bench_press is None,
        combine.broad_jump is None,
        combine.three_cone is None,
        combine.shuttle is None,
    ])
    
    if all_none:
        st.info("Combine metrics not available. Player may not have participated in the NFL Combine or data is not publicly available.")


def _render_injuries_tab(player_id: str) -> None:
    """Render the injuries sub-tab."""
    with st.spinner("Loading injury data..."):
        injuries = get_player_injuries(player_id)
    
    if not injuries:
        st.success("No injuries reported.")
        return
    
    for injury in injuries:
        status_color = "green" if injury.status == "Active" else "red"
        
        st.markdown(f"### :{status_color}[{injury.status}]")
        
        if injury.injury_type and injury.injury_type != "—":
            st.markdown(f"**Type:** {injury.injury_type}")
        
        if injury.details and injury.details != "—":
            st.markdown(f"**Details:** {injury.details}")
        
        if injury.date and injury.date != "—":
            st.caption(f"Date: {injury.date}")
        
        st.divider()


def _render_news_tab(player_id: str) -> None:
    """Render the news sub-tab."""
    with st.spinner("Loading news..."):
        articles = get_player_news(player_id)
    
    if not articles:
        st.info("No recent news articles found.")
        return
    
    for article in articles:
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if article.image_url:
                st.image(article.image_url, width=120)
        
        with col2:
            if article.link:
                st.markdown(f"### [{article.headline}]({article.link})")
            else:
                st.markdown(f"### {article.headline}")
            
            if article.description:
                st.markdown(
                    f'<p style="font-size:0.9rem;line-height:1.4;word-break:break-word;">'
                    f"{html.escape(article.description)}</p>",
                    unsafe_allow_html=True,
                )
            
            st.caption(article.published)
        
        st.divider()


def render_research_tab() -> None:
    """Main entry point for the Research tab."""
    _init_research_state()
    
    _render_search()
    
    player_id = st.session_state.get("research_selected_player")
    
    if not player_id:
        return
    
    with st.spinner("Loading player profile..."):
        profile = get_player_profile(player_id)
    
    if not profile:
        st.error("Could not load player profile. Please try again.")
        st.session_state["research_selected_player"] = None
        return
    
    if st.button("← Back to Search"):
        st.session_state["research_selected_player"] = None
        st.session_state["research_search_results"] = []
        st.rerun()
    
    _render_profile_card(profile)
    
    st.divider()
    
    stats_tab, combine_tab, injuries_tab, news_tab = st.tabs([
        "Stats", "Combine", "Injuries", "News"
    ])
    
    with stats_tab:
        _render_stats_tab(player_id)
    
    with combine_tab:
        _render_combine_tab(player_id)
    
    with injuries_tab:
        _render_injuries_tab(player_id)
    
    with news_tab:
        _render_news_tab(player_id)
