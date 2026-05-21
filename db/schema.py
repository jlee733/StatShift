"""SQLite schema definitions for StatShift."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
USING fts5(title, content, content='documents', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
    INSERT INTO documents_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    player_count INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'espn'
);

CREATE TABLE IF NOT EXISTS players (
    espn_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    last_name_initial TEXT NOT NULL,
    position TEXT,
    team TEXT,
    experience INTEGER,
    draft_year INTEGER,
    status TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_injuries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    espn_id TEXT NOT NULL REFERENCES players(espn_id) ON DELETE CASCADE,
    status TEXT,
    injury_type TEXT,
    details TEXT,
    injury_date TEXT
);

CREATE TABLE IF NOT EXISTS player_game_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    espn_id TEXT NOT NULL REFERENCES players(espn_id) ON DELETE CASCADE,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    opponent TEXT,
    result TEXT,
    passing_yards INTEGER DEFAULT 0,
    passing_tds INTEGER DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    rushing_yards INTEGER DEFAULT 0,
    rushing_tds INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    receiving_yards INTEGER DEFAULT 0,
    receiving_tds INTEGER DEFAULT 0,
    fumbles_lost INTEGER DEFAULT 0,
    UNIQUE(espn_id, season, week)
);

CREATE INDEX IF NOT EXISTS idx_players_last_name_initial
    ON players(last_name_initial);
CREATE INDEX IF NOT EXISTS idx_players_last_name ON players(last_name);
CREATE INDEX IF NOT EXISTS idx_players_display_name ON players(display_name);
CREATE INDEX IF NOT EXISTS idx_player_game_logs_player_season
    ON player_game_logs(espn_id, season);
"""
