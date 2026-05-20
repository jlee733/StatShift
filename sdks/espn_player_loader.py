"""ESPN API client for player research data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

CORE_API_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
CFB_API_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
SITE_API_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
COMMON_SEARCH_URL = "https://site.api.espn.com/apis/common/v3/search"
TIMEOUT = 30.0

_COLLEGE_STAT_FIELDS: dict[str, str] = {
    "gamesPlayed": "games_played",
    "completions": "completions",
    "netPassingYards": "passing_yards",
    "passingTouchdowns": "passing_tds",
    "interceptions": "interceptions",
    "rushingAttempts": "rush_attempts",
    "rushingYards": "rushing_yards",
    "rushingTouchdowns": "rushing_tds",
    "receptions": "receptions",
    "receivingYards": "receiving_yards",
    "receivingTouchdowns": "receiving_tds",
}


@dataclass
class PlayerProfile:
    id: str
    name: str
    position: str
    team: str
    jersey: str
    height: str
    weight: str
    age: int | None
    birth_date: str
    college: str
    draft_info: str
    draft_year: int | None
    experience: int
    headshot_url: str
    status: str


@dataclass
class CollegeSeasonStats:
    season: int
    team: str
    games_played: str
    completions: str
    passing_yards: str
    passing_tds: str
    interceptions: str
    rush_attempts: str
    rushing_yards: str
    rushing_tds: str
    receptions: str
    receiving_yards: str
    receiving_tds: str


@dataclass
class SeasonStats:
    season: int
    games_played: int
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class CombineMetrics:
    year: int | None
    forty_yard: float | None
    vertical_jump: float | None
    bench_press: int | None
    broad_jump: float | None
    three_cone: float | None
    shuttle: float | None


@dataclass
class InjuryInfo:
    status: str
    injury_type: str
    details: str
    date: str


@dataclass
class NewsArticle:
    headline: str
    description: str
    published: str
    link: str
    image_url: str | None


@dataclass
class GameLogEntry:
    """Single game stats for fantasy point calculation."""
    week: int
    opponent: str
    result: str
    passing_yards: int
    passing_tds: int
    interceptions: int
    rushing_yards: int
    rushing_tds: int
    receptions: int
    receiving_yards: int
    receiving_tds: int
    fumbles_lost: int


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a GET request and return JSON response."""
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dict keys."""
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key, default)
        if data is None:
            return default
    return data


def _format_height(inches: int | None) -> str:
    """Convert height in inches to feet'inches format."""
    if not inches:
        return "—"
    feet = inches // 12
    remaining = inches % 12
    return f"{feet}'{remaining}\""


def _format_weight(pounds: int | None) -> str:
    """Format weight with lbs suffix."""
    if not pounds:
        return "—"
    return f"{pounds} lbs"


def nfl_season_has_started(season_year: int, *, now: datetime | None = None) -> bool:
    """Return True if the NFL regular season for season_year has begun."""
    now = now or datetime.now()
    if now.year > season_year:
        return True
    if now.year < season_year:
        return False
    return now.month >= 9


def is_upcoming_rookie(draft_year: int | None, *, now: datetime | None = None) -> bool:
    """True when drafted this calendar year and that NFL season has not started."""
    now = now or datetime.now()
    if draft_year is None:
        return False
    return draft_year == now.year and not nfl_season_has_started(draft_year, now=now)


def _resolve_ref_field(ref_obj: Any, *, name_keys: tuple[str, ...] = ("name", "displayName", "abbreviation")) -> str:
    """Resolve a display name from an embedded object or ESPN $ref."""
    if not ref_obj:
        return "—"
    if isinstance(ref_obj, dict):
        for key in name_keys:
            value = ref_obj.get(key)
            if value:
                return str(value)
        ref_url = ref_obj.get("$ref")
        if ref_url:
            try:
                data = _get_json(ref_url)
            except httpx.HTTPError:
                return "—"
            for key in name_keys:
                value = data.get(key)
                if value:
                    return str(value)
    return "—"


def _stat_display_value(categories: list[dict], stat_name: str) -> str:
    for cat in categories:
        for stat in cat.get("stats", []):
            if stat.get("name") == stat_name:
                return str(stat.get("displayValue", stat.get("value", "—")))
    return "—"


def _empty_college_season(season: int, team: str = "") -> CollegeSeasonStats:
    return CollegeSeasonStats(
        season=season,
        team=team,
        games_played="—",
        completions="—",
        passing_yards="—",
        passing_tds="—",
        interceptions="—",
        rush_attempts="—",
        rushing_yards="—",
        rushing_tds="—",
        receptions="—",
        receiving_yards="—",
        receiving_tds="—",
    )


def _college_season_from_categories(season: int, team: str, categories: list[dict]) -> CollegeSeasonStats:
    row = _empty_college_season(season, team)
    for stat_name, attr in _COLLEGE_STAT_FIELDS.items():
        value = _stat_display_value(categories, stat_name)
        if value != "—":
            setattr(row, attr, value)
    return row


def _team_from_search_item(item: dict[str, Any]) -> str:
    for rel in item.get("teamRelationships", []) or []:
        if rel.get("type") == "team":
            return (
                rel.get("displayName")
                or _safe_get(rel, "core", "displayName", default="Free Agent")
            )
    return "Free Agent"


def _headshot_from_search_item(item: dict[str, Any]) -> str:
    headshot = item.get("headshot")
    if isinstance(headshot, dict):
        return headshot.get("href", "") or ""
    player_id = item.get("id")
    if player_id:
        return f"https://a.espncdn.com/i/headshots/nfl/players/full/{player_id}.png"
    return ""


def _position_for_player_id(player_id: str) -> str:
    try:
        data = _get_json(f"{CORE_API_BASE}/athletes/{player_id}")
        return _safe_get(data, "position", "abbreviation", default="—")
    except httpx.HTTPError:
        return "—"


def search_players(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search active NFL players by name via ESPN common search API."""
    if not query or len(query.strip()) < 2:
        return []

    try:
        data = _get_json(
            COMMON_SEARCH_URL,
            params={
                "query": query.strip(),
                "limit": max(limit * 3, 25),
                "type": "player",
                "sport": "football",
                "league": "nfl",
            },
        )
    except httpx.HTTPError:
        return []

    results: list[dict[str, Any]] = []

    for item in data.get("items", []):
        if len(results) >= limit:
            break
        if not item.get("isActive") or item.get("isRetired"):
            continue

        player_id = str(item.get("id", ""))
        if not player_id:
            continue

        results.append({
            "id": player_id,
            "name": item.get("displayName", "Unknown"),
            "position": _position_for_player_id(player_id),
            "team": _team_from_search_item(item),
            "headshot": _headshot_from_search_item(item),
            "active": True,
            "status": "Active",
        })

    return results


def get_player_profile(player_id: str) -> PlayerProfile | None:
    """Get detailed player profile information."""
    url = f"{CORE_API_BASE}/athletes/{player_id}"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return None
    
    height_inches = data.get("height")
    weight_pounds = data.get("weight")
    
    birth_date = data.get("dateOfBirth", "")
    age = None
    if birth_date:
        try:
            dob = datetime.fromisoformat(birth_date.replace("Z", "+00:00"))
            age = (datetime.now(dob.tzinfo) - dob).days // 365
        except (ValueError, TypeError):
            pass
    
    draft = data.get("draft", {})
    draft_info = "—"
    draft_year: int | None = None
    if draft:
        draft_year = draft.get("year")
        year = draft.get("year", "")
        round_num = draft.get("round", "")
        pick = draft.get("selection", "")
        if year and round_num and pick:
            draft_info = f"{year} Round {round_num}, Pick {pick}"
    
    return PlayerProfile(
        id=str(data.get("id", "")),
        name=data.get("displayName", "Unknown"),
        position=_safe_get(data, "position", "displayName", default="—"),
        team=_safe_get(data, "team", "displayName", default="Free Agent"),
        jersey=str(data.get("jersey", "—")),
        height=_format_height(height_inches),
        weight=_format_weight(weight_pounds),
        age=age,
        birth_date=birth_date[:10] if birth_date else "—",
        college=_resolve_ref_field(data.get("college")),
        draft_info=draft_info,
        draft_year=int(draft_year) if draft_year else None,
        experience=data.get("experience", {}).get("years", 0),
        headshot_url=_safe_get(data, "headshot", "href", default=""),
        status=_safe_get(data, "status", "name", default="Active"),
    )


def get_player_college_stats(player_id: str) -> list[CollegeSeasonStats]:
    """Fetch season-by-season college statistics for an NFL player."""
    try:
        athlete = _get_json(f"{CORE_API_BASE}/athletes/{player_id}")
    except httpx.HTTPError:
        return []

    college_athlete_ref = _safe_get(athlete, "collegeAthlete", "$ref", default="")
    if not college_athlete_ref:
        return []

    athlete_id = college_athlete_ref.rstrip("/").split("/athletes/")[-1].split("?")[0]
    try:
        log_data = _get_json(f"{CFB_API_BASE}/athletes/{athlete_id}/statisticslog")
    except httpx.HTTPError:
        return []

    seasons: list[CollegeSeasonStats] = []
    for entry in log_data.get("entries", []):
        season_ref = _safe_get(entry, "season", "$ref", default="")
        if not season_ref or "/seasons/" not in season_ref:
            continue
        try:
            season_year = int(season_ref.split("/seasons/")[1].split("?")[0])
        except (IndexError, ValueError):
            continue

        stats_ref = ""
        team_name = ""
        for stat_entry in entry.get("statistics", []):
            if stat_entry.get("type") == "total":
                stats_ref = _safe_get(stat_entry, "statistics", "$ref", default="")
            elif stat_entry.get("type") == "team" and not team_name:
                team_ref = _safe_get(stat_entry, "team", "$ref", default="")
                if team_ref:
                    team_name = _resolve_ref_field({"$ref": team_ref}, name_keys=("abbreviation", "displayName", "name"))

        if not stats_ref:
            continue

        try:
            stats_data = _get_json(stats_ref)
        except httpx.HTTPError:
            continue

        categories = _safe_get(stats_data, "splits", "categories", default=[])
        if not categories:
            continue

        seasons.append(_college_season_from_categories(season_year, team_name, categories))

    seasons.sort(key=lambda s: s.season, reverse=True)
    return seasons


def get_player_stats(player_id: str, season: int | None = None) -> list[SeasonStats]:
    """Get player statistics for a season or career."""
    url = f"{CORE_API_BASE}/athletes/{player_id}/statistics"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return []
    
    results = []
    splits = data.get("splits", {})
    categories = splits.get("categories", [])
    
    if not categories:
        return []
    
    stats_dict: dict[str, Any] = {}
    games_played = 0
    
    for category in categories:
        cat_name = category.get("displayName", "")
        for stat in category.get("stats", []):
            stat_name = stat.get("displayName", stat.get("name", ""))
            stat_value = stat.get("displayValue", stat.get("value", "—"))
            if stat_name:
                stats_dict[f"{cat_name} - {stat_name}"] = stat_value
            if stat_name.lower() in ("games played", "gp"):
                try:
                    games_played = int(stat_value)
                except (ValueError, TypeError):
                    pass
    
    current_year = datetime.now().year
    results.append(SeasonStats(
        season=season or current_year,
        games_played=games_played,
        stats=stats_dict,
    ))
    
    return results


def get_player_combine(player_id: str) -> CombineMetrics | None:
    """Get NFL Combine metrics for a player."""
    profile = get_player_profile(player_id)
    if not profile:
        return None
    
    url = f"{CORE_API_BASE}/athletes/{player_id}"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return CombineMetrics(
            year=None,
            forty_yard=None,
            vertical_jump=None,
            bench_press=None,
            broad_jump=None,
            three_cone=None,
            shuttle=None,
        )
    
    draft = data.get("draft", {})
    combine_year = draft.get("year") if draft else None
    
    return CombineMetrics(
        year=combine_year,
        forty_yard=None,
        vertical_jump=None,
        bench_press=None,
        broad_jump=None,
        three_cone=None,
        shuttle=None,
    )


def get_player_injuries(player_id: str) -> list[InjuryInfo]:
    """Get injury information for a player."""
    url = f"{CORE_API_BASE}/athletes/{player_id}"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return []
    
    injuries = data.get("injuries", [])
    results = []
    
    for injury in injuries:
        results.append(InjuryInfo(
            status=_safe_get(injury, "status", "type", default="Unknown"),
            injury_type=injury.get("type", {}).get("text", "—"),
            details=injury.get("details", {}).get("detail", "—"),
            date=injury.get("date", "—")[:10] if injury.get("date") else "—",
        ))
    
    status_info = data.get("status", {})
    if status_info and not injuries:
        results.append(InjuryInfo(
            status=status_info.get("name", "Active"),
            injury_type="—",
            details="No current injuries reported",
            date="—",
        ))
    
    return results if results else [InjuryInfo(
        status="Active",
        injury_type="—",
        details="No injury information available",
        date="—",
    )]


def get_player_news(player_id: str, limit: int = 10) -> list[NewsArticle]:
    """Get recent news articles about a player."""
    url = f"{SITE_API_BASE}/news"
    
    try:
        data = _get_json(url, params={"player": player_id, "limit": limit})
    except httpx.HTTPError:
        return []
    
    results = []
    articles = data.get("articles", [])
    
    for article in articles[:limit]:
        published = article.get("published", "")
        if published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                published = dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                published = published[:10]
        
        images = article.get("images", [])
        image_url = images[0].get("url") if images else None
        
        links = article.get("links", {})
        web_link = links.get("web", {}).get("href", "")
        
        results.append(NewsArticle(
            headline=article.get("headline", "No headline"),
            description=article.get("description", ""),
            published=published,
            link=web_link,
            image_url=image_url,
        ))
    
    return results


def get_available_seasons(player_id: str) -> list[int]:
    """Get list of seasons with available statistics for a player."""
    current_year = datetime.now().year
    return list(range(current_year, current_year - 5, -1))


def get_player_seasons(player_id: str) -> list[int]:
    """Fetch actual seasons with game data from ESPN statisticslog."""
    url = f"{CORE_API_BASE}/athletes/{player_id}/statisticslog"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return []
    
    seasons: list[int] = []
    entries = data.get("entries", [])
    
    for entry in entries:
        season_ref = _safe_get(entry, "season", "$ref", default="")
        if season_ref and "/seasons/" in season_ref:
            try:
                year_str = season_ref.split("/seasons/")[1].split("?")[0]
                year = int(year_str)
                if year not in seasons:
                    seasons.append(year)
            except (IndexError, ValueError):
                continue
    
    seasons.sort(reverse=True)
    return seasons


def _extract_stat_value(categories: list[dict], category_name: str, stat_name: str) -> float:
    """Extract a specific stat value from ESPN categories structure."""
    for cat in categories:
        if cat.get("name") == category_name:
            for stat in cat.get("stats", []):
                if stat.get("name") == stat_name:
                    try:
                        return float(stat.get("value", 0))
                    except (TypeError, ValueError):
                        return 0.0
    return 0.0


def get_player_gamelog(player_id: str, season: int) -> list[GameLogEntry]:
    """Fetch week-by-week game stats for a season."""
    url = f"{CORE_API_BASE}/seasons/{season}/athletes/{player_id}/eventlog"
    
    try:
        data = _get_json(url)
    except httpx.HTTPError:
        return []
    
    events = data.get("events", {})
    items = events.get("items", [])
    
    results: list[GameLogEntry] = []
    
    for idx, item in enumerate(items):
        if not item.get("played"):
            continue
        
        stats_ref = _safe_get(item, "statistics", "$ref", default="")
        if not stats_ref:
            continue
        
        try:
            stats_data = _get_json(stats_ref)
        except httpx.HTTPError:
            continue
        
        categories = _safe_get(stats_data, "splits", "categories", default=[])
        if not categories:
            continue
        
        entry = GameLogEntry(
            week=idx + 1,
            opponent="",
            result="",
            passing_yards=int(_extract_stat_value(categories, "passing", "passingYards")),
            passing_tds=int(_extract_stat_value(categories, "passing", "passingTouchdowns")),
            interceptions=int(_extract_stat_value(categories, "passing", "interceptions")),
            rushing_yards=int(_extract_stat_value(categories, "rushing", "rushingYards")),
            rushing_tds=int(_extract_stat_value(categories, "rushing", "rushingTouchdowns")),
            receptions=int(_extract_stat_value(categories, "receiving", "receptions")),
            receiving_yards=int(_extract_stat_value(categories, "receiving", "receivingYards")),
            receiving_tds=int(_extract_stat_value(categories, "receiving", "receivingTouchdowns")),
            fumbles_lost=int(_extract_stat_value(categories, "general", "fumblesLost")),
        )
        results.append(entry)
    
    return results


def calculate_fantasy_points(game: GameLogEntry, scoring: str) -> float:
    """Calculate fantasy points for a game.
    
    Args:
        game: GameLogEntry with stats
        scoring: 'ppr', 'half_ppr', or 'standard'
    
    Returns:
        Fantasy points as float
    """
    points = 0.0
    
    # Passing: 0.04 per yard, 4 per TD, -2 per INT
    points += game.passing_yards * 0.04
    points += game.passing_tds * 4
    points -= game.interceptions * 2
    
    # Rushing: 0.1 per yard, 6 per TD
    points += game.rushing_yards * 0.1
    points += game.rushing_tds * 6
    
    # Receiving: 0.1 per yard, 6 per TD
    points += game.receiving_yards * 0.1
    points += game.receiving_tds * 6
    
    # Reception bonus based on scoring format
    if scoring == "ppr":
        points += game.receptions * 1.0
    elif scoring == "half_ppr":
        points += game.receptions * 0.5
    
    # Fumbles lost: -2
    points -= game.fumbles_lost * 2
    
    return round(points, 2)
