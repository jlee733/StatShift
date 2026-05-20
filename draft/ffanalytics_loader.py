"""Load fantasy player projections and ADP via R ffanalytics (rpy2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config import settings
from draft.models import Player, Position
from draft.sleeper_loader import get_sleeper_rankings, lookup_sleeper_rank

CACHE_PATH = settings.project_root / "data" / "ffanalytics_players.json"
CACHE_MAX_AGE_HOURS = 24

DRAFT_POSITIONS = ("QB", "RB", "WR", "TE", "K")
DEFAULT_SCRAPE_SOURCES = ("FantasyPros", "ESPN", "CBS", "Yahoo")
DEFAULT_ADP_SOURCES = ("ESPN", "Yahoo", "CBS", "NFL")

POSITION_MAP: dict[str, Position] = {
    "QB": Position.QB,
    "RB": Position.RB,
    "WR": Position.WR,
    "TE": Position.TE,
    "K": Position.K,
    "PK": Position.K,
}


def _cache_path(path: Any = None) -> Any:
    return path or CACHE_PATH


def current_nfl_season() -> int:
    """Season year used by ffanalytics scrape_data (Mar+ = current calendar year)."""
    now = datetime.now()
    return now.year if now.month >= 3 else now.year - 1


def _require_rpy2():
    try:
        import rpy2.robjects as ro  # noqa: F401
        from rpy2.robjects.packages import importr  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "rpy2 is not installed. Run: pip install rpy2"
        ) from exc
    return ro, importr


def _to_python_scalar(value: Any) -> Any:
    """Coerce pandas/numpy scalars to plain Python types for merge logic."""
    if value is None:
        return None
    type_name = type(value).__module__
    if type_name == "numpy":
        return value.item() if hasattr(value, "item") else value
    try:
        if value != value:  # NaN
            return None
    except (TypeError, ValueError):
        pass
    return value


def _r_dataframe_to_records(r_df: Any) -> list[dict[str, Any]]:
    import rpy2.robjects as ro

    pdf = ro.conversion.rpy2py(r_df)
    if pdf is None or len(pdf) == 0:
        return []
    records = pdf.to_dict(orient="records")
    return [
        {key: _to_python_scalar(val) for key, val in row.items()}
        for row in records
    ]


def _pick_column(row: dict[str, Any], *candidates: str) -> Any:
    for key in candidates:
        if key in row and row[key] is not None:
            val = row[key]
            try:
                if val != val:  # NaN
                    continue
            except TypeError:
                pass
            return val
    return None


def _float_or(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _player_name_from_row(row: dict[str, Any]) -> str | None:
    name = _pick_column(row, "player_name", "player", "name", "Player")
    if name:
        return str(name).strip()
    first = _pick_column(row, "first_name")
    last = _pick_column(row, "last_name")
    if first or last:
        return f"{first or ''} {last or ''}".strip()
    return None


def _adp_from_row(row: dict[str, Any]) -> float | None:
    """ADP from ffanalytics get_adp (avg column or adp_<source> columns)."""
    avg = _pick_column(row, "avg", "average", "mean")
    if avg is not None:
        val = _float_or(avg, 0.0)
        return val if val > 0 else None
    values: list[float] = []
    for key, raw in row.items():
        if not str(key).startswith("adp_"):
            continue
        val = _float_or(raw, 0.0)
        if val > 0:
            values.append(val)
    if not values:
        return None
    return sum(values) / len(values)


def _per_source_adp_from_row(row: dict[str, Any]) -> dict[str, float]:
    """Extract per-source ADP values from ffanalytics get_adp row."""
    result: dict[str, float] = {}
    
    for key, raw in row.items():
        key_lower = str(key).lower()
        if key_lower.startswith("adp_"):
            source = key_lower[4:]
            val = _float_or(raw, 0.0)
            if val > 0:
                result[source] = val
    
    return result


def parse_projection_row(
    row: dict[str, Any],
    *,
    points: float,
    adp_by_id: dict[str, float],
    adp_by_name: dict[str, float],
    espn_adp_by_id: dict[str, float] | None = None,
    espn_adp_by_name: dict[str, float] | None = None,
    yahoo_adp_by_id: dict[str, float] | None = None,
    yahoo_adp_by_name: dict[str, float] | None = None,
) -> Player | None:
    pos_raw = _pick_column(row, "pos", "position")
    if pos_raw is None:
        return None
    position = POSITION_MAP.get(str(pos_raw).upper())
    if position is None:
        return None

    name = _player_name_from_row(row)
    if not name:
        return None

    team = str(_pick_column(row, "team", "nfl_team") or "").strip()
    player_id = _pick_column(row, "id", "player_id")
    pid_str = str(player_id) if player_id is not None else None
    name_lower = name.lower()
    
    adp = 999.0
    if pid_str is not None:
        adp = adp_by_id.get(pid_str, adp)
    if adp >= 999.0:
        adp = adp_by_name.get(name_lower, adp)

    rank_espn = 999.0
    if espn_adp_by_id and pid_str:
        rank_espn = espn_adp_by_id.get(pid_str, rank_espn)
    if rank_espn >= 999.0 and espn_adp_by_name:
        rank_espn = espn_adp_by_name.get(name_lower, rank_espn)

    rank_yahoo = 999.0
    if yahoo_adp_by_id and pid_str:
        rank_yahoo = yahoo_adp_by_id.get(pid_str, rank_yahoo)
    if rank_yahoo >= 999.0 and yahoo_adp_by_name:
        rank_yahoo = yahoo_adp_by_name.get(name_lower, rank_yahoo)

    pts = round(points, 1)
    return Player(
        name=name,
        position=position,
        fp_ppr=pts,
        fp_half=pts,
        fp_std=pts,
        team=team,
        adp=adp,
        rank_espn=rank_espn,
        rank_yahoo=rank_yahoo,
        rank_sleeper=999.0,
    )


def merge_projection_tables(
    std_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    ppr_rows: list[dict[str, Any]],
    adp_rows: list[dict[str, Any]],
) -> list[Player]:
    """Combine standard, half-PPR, and PPR projection rows into Player models."""
    adp_by_id: dict[str, float] = {}
    adp_by_name: dict[str, float] = {}
    espn_adp_by_id: dict[str, float] = {}
    espn_adp_by_name: dict[str, float] = {}
    yahoo_adp_by_id: dict[str, float] = {}
    yahoo_adp_by_name: dict[str, float] = {}
    
    for row in adp_rows:
        pid = _pick_column(row, "id", "player_id")
        adp_val = _adp_from_row(row)
        per_source = _per_source_adp_from_row(row)
        
        pid_str = str(pid) if pid is not None else None
        name = _player_name_from_row(row)
        name_lower = name.lower() if name else None
        
        if adp_val is not None:
            if pid_str:
                adp_by_id[pid_str] = adp_val
            if name_lower:
                adp_by_name[name_lower] = adp_val
        
        espn_val = per_source.get("espn")
        if espn_val is not None:
            if pid_str:
                espn_adp_by_id[pid_str] = espn_val
            if name_lower:
                espn_adp_by_name[name_lower] = espn_val
        
        yahoo_val = per_source.get("yahoo")
        if yahoo_val is not None:
            if pid_str:
                yahoo_adp_by_id[pid_str] = yahoo_val
            if name_lower:
                yahoo_adp_by_name[name_lower] = yahoo_val

    def index_by_id(rows: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], float]]:
        out: dict[str, tuple[dict[str, Any], float]] = {}
        for row in rows:
            pid = _pick_column(row, "id", "player_id")
            if pid is None:
                continue
            pts = _float_or(_pick_column(row, "points", "avg_points", "fpts"))
            if pts <= 0:
                continue
            out[str(pid)] = (row, pts)
        return out

    std_idx = index_by_id(std_rows)
    half_idx = index_by_id(half_rows)
    ppr_idx = index_by_id(ppr_rows)

    all_ids = set(std_idx) | set(half_idx) | set(ppr_idx)
    players: list[Player] = []

    for pid in all_ids:
        base_row, _ = std_idx.get(pid) or half_idx.get(pid) or ppr_idx.get(pid) or ({}, 0.0)
        if not base_row:
            continue
        fp_std = std_idx.get(pid, (base_row, 0.0))[1]
        fp_half = half_idx.get(pid, (base_row, fp_std))[1]
        fp_ppr = ppr_idx.get(pid, (base_row, fp_std))[1]
        if fp_std <= 0 and fp_half <= 0 and fp_ppr <= 0:
            continue

        player = parse_projection_row(
            base_row,
            points=fp_ppr or fp_half or fp_std,
            adp_by_id=adp_by_id,
            adp_by_name=adp_by_name,
            espn_adp_by_id=espn_adp_by_id,
            espn_adp_by_name=espn_adp_by_name,
            yahoo_adp_by_id=yahoo_adp_by_id,
            yahoo_adp_by_name=yahoo_adp_by_name,
        )
        if player is None:
            continue
        player.fp_std = round(fp_std or fp_half or fp_ppr, 1)
        player.fp_half = round(fp_half or fp_std or fp_ppr, 1)
        player.fp_ppr = round(fp_ppr or fp_half or fp_std, 1)
        players.append(player)

    players.sort(key=lambda p: p.adp if p.adp < 999 else 9999)
    for rank, player in enumerate(players, start=1):
        if player.adp >= 999:
            player.adp = float(rank)
    return players


def fetch_ffanalytics_players(
    *,
    season: int | None = None,
    scrape_sources: tuple[str, ...] = DEFAULT_SCRAPE_SOURCES,
    adp_sources: tuple[str, ...] = DEFAULT_ADP_SOURCES,
) -> list[Player]:
    """Scrape projections (3 scoring formats) and ADP from ffanalytics."""
    from draft.rpy2_setup import rpy2_session

    with rpy2_session():
        return _fetch_ffanalytics_players_impl(
            season=season,
            scrape_sources=scrape_sources,
            adp_sources=adp_sources,
        )


def _run_ffanalytics_pipeline_r(
    ro: Any,
    *,
    season: int,
    scrape_sources: tuple[str, ...],
    adp_sources: tuple[str, ...],
) -> tuple[Any, Any, Any, Any]:
    """
    Run scrape → projections (3 formats) → ADP entirely in R.

    Intermediate objects must not round-trip through rpy2; that drops attributes
    (e.g. season/year) and breaks projections_table().
    """
    from rpy2.robjects.vectors import IntVector, StrVector

    ro.globalenv[".statshift_src"] = StrVector(list(scrape_sources))
    ro.globalenv[".statshift_adp_src"] = StrVector(list(adp_sources))
    ro.globalenv[".statshift_season"] = IntVector([season])
    ro.globalenv[".statshift_pos"] = StrVector(list(DRAFT_POSITIONS))

    ro.r(
        """
        {
          library(ffanalytics)
          build_scoring <- function(rec_pts) {
            s <- unserialize(serialize(ffanalytics::scoring, NULL))
            s$rec$rec <- rec_pts
            s
          }
          scraped <- scrape_data(
            src = .statshift_src,
            pos = .statshift_pos,
            season = .statshift_season,
            week = 0L
          )
          .statshift_proj_std <<- add_player_info(
            projections_table(scraped, scoring_rules = build_scoring(0))
          )
          .statshift_proj_half <<- add_player_info(
            projections_table(scraped, scoring_rules = build_scoring(0.5))
          )
          .statshift_proj_ppr <<- add_player_info(
            projections_table(scraped, scoring_rules = build_scoring(1))
          )
          .statshift_adp <<- get_adp(sources = .statshift_adp_src)
          invisible(NULL)
        }
        """
    )
    return (
        ro.globalenv[".statshift_proj_std"],
        ro.globalenv[".statshift_proj_half"],
        ro.globalenv[".statshift_proj_ppr"],
        ro.globalenv[".statshift_adp"],
    )


def _fetch_ffanalytics_players_impl(
    *,
    season: int | None,
    scrape_sources: tuple[str, ...],
    adp_sources: tuple[str, ...],
) -> list[Player]:
    ro, _importr = _require_rpy2()
    season = season or current_nfl_season()

    proj_std, proj_half, proj_ppr, adp_df = _run_ffanalytics_pipeline_r(
        ro,
        season=season,
        scrape_sources=scrape_sources,
        adp_sources=adp_sources,
    )

    players = merge_projection_tables(
        _r_dataframe_to_records(proj_std),
        _r_dataframe_to_records(proj_half),
        _r_dataframe_to_records(proj_ppr),
        _r_dataframe_to_records(adp_df),
    )
    
    _populate_sleeper_rankings(players)
    
    players.sort(key=lambda p: p.fp_ppr, reverse=True)
    return players


def _populate_sleeper_rankings(players: list[Player]) -> None:
    """Fetch Sleeper rankings and populate rank_sleeper for each player."""
    try:
        sleeper_rankings = get_sleeper_rankings()
    except Exception:
        return
    
    for player in players:
        player.rank_sleeper = lookup_sleeper_rank(player.name, sleeper_rankings)


def save_player_cache(players: list[Player], path: Any = None) -> Any:
    target = _cache_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "season": current_nfl_season(),
        "source": "ffanalytics",
        "count": len(players),
        "players": [
            {
                "name": p.name,
                "position": p.position.value,
                "fp_ppr": p.fp_ppr,
                "fp_half": p.fp_half,
                "fp_std": p.fp_std,
                "team": p.team,
                "adp": p.adp,
                "rank_espn": p.rank_espn,
                "rank_yahoo": p.rank_yahoo,
                "rank_sleeper": p.rank_sleeper,
            }
            for p in players
        ],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def load_player_cache(path: Any = None) -> list[Player] | None:
    target = _cache_path(path)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    players: list[Player] = []
    for row in payload.get("players", []):
        try:
            players.append(
                Player(
                    name=row["name"],
                    position=Position(row["position"]),
                    fp_ppr=float(row["fp_ppr"]),
                    fp_half=float(row["fp_half"]),
                    fp_std=float(row["fp_std"]),
                    team=row.get("team", ""),
                    adp=float(row.get("adp", 999)),
                    rank_espn=float(row.get("rank_espn", 999)),
                    rank_yahoo=float(row.get("rank_yahoo", 999)),
                    rank_sleeper=float(row.get("rank_sleeper", 999)),
                )
            )
        except (KeyError, ValueError):
            continue
    return players if players else None


def cache_is_fresh(path: Any = None, max_age_hours: int = CACHE_MAX_AGE_HOURS) -> bool:
    target = _cache_path(path)
    if not target.exists():
        return False
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return age_hours < max_age_hours
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return False


def load_active_players(
    *,
    force_refresh: bool = False,
    cache_path: Any = None,
) -> list[Player]:
    path = _cache_path(cache_path)
    if not force_refresh and cache_is_fresh(path):
        cached = load_player_cache(path)
        if cached:
            return cached

    players = fetch_ffanalytics_players()
    save_player_cache(players, path)
    return players
