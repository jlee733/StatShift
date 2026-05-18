"""Create and seed the local SQLite database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings

DOCUMENTS = [
    {
        "title": "2024-25 Lakers team overview",
        "category": "team",
        "content": (
            "The Los Angeles Lakers finished the 2024-25 regular season 50-32. "
            "They ranked 8th in offensive rating (115.4) and 12th in defensive rating (112.1). "
            "Anthony Davis averaged 24.7 PPG, 12.6 RPG, and 2.4 BPG. "
            "LeBron James averaged 25.3 PPG, 7.4 RPG, and 8.1 APG at age 40."
        ),
    },
    {
        "title": "Stephen Curry shooting splits",
        "category": "player",
        "content": (
            "Stephen Curry shot 45.2% from the field, 40.8% from three, and 92.1% from the line "
            "in 2024-25. He attempted 11.8 threes per game and led the Warriors with 26.4 PPG. "
            "His true shooting percentage was 62.8%."
        ),
    },
    {
        "title": "Celtics defensive profile",
        "category": "team",
        "content": (
            "Boston held opponents to 108.9 points per 100 possessions, 3rd in the league. "
            "Jrue Holiday and Derrick White anchored perimeter defense. "
            "Boston forced the 5th-most turnovers per game (15.2)."
        ),
    },
    {
        "title": "Victor Wembanyama sophomore season",
        "category": "player",
        "content": (
            "Victor Wembanyama averaged 22.1 PPG, 10.8 RPG, 3.6 BPG, and 1.2 SPG in 2024-25. "
            "San Antonio improved defensively when he was on the floor (+8.2 net rating swing). "
            "He shot 48.9% inside the arc and 34.2% from three on low volume."
        ),
    },
    {
        "title": "League pace and efficiency leaders",
        "category": "league",
        "content": (
            "League average pace was 99.2 possessions per 48 minutes in 2024-25. "
            "Indiana played the fastest pace (102.4); New York played the slowest (96.1). "
            "Denver led offensive rating (119.8); Charlotte ranked last defensively (118.4 DRtg)."
        ),
    },
    {
        "title": "Nikola Jokic playmaking",
        "category": "player",
        "content": (
            "Nikola Jokic recorded 9.2 APG with a 42.1% assist rate, highest among centers. "
            "He posted a 31.8 PER and 14.2 win shares. Denver's offense was +12.4 per 100 with him on court."
        ),
    },
    {
        "title": "Injury report: March 2025",
        "category": "injury",
        "content": (
            "Kawhi Leonard missed 18 games with knee management. "
            "Joel Embiid was limited to 35 games due to knee soreness. "
            "Ja Morant returned in late February after a shoulder strain."
        ),
    },
    {
        "title": "Trade deadline summary",
        "category": "transaction",
        "content": (
            "At the 2025 deadline, Milwaukee acquired a two-way wing for second-round picks. "
            "Phoenix moved a veteran point guard for cap flexibility. "
            "No blockbuster deals moved the title odds more than 3% in consensus models."
        ),
    },
]


def init_database(db_path: Path | None = None) -> Path:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(
            """
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
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO documents (title, category, content) VALUES (?, ?, ?)",
                [(d["title"], d["category"], d["content"]) for d in DOCUMENTS],
            )
            conn.commit()
            print(f"Seeded {len(DOCUMENTS)} documents into {path}")
        else:
            print(f"Database already has {count} documents at {path}")
    finally:
        conn.close()

    return path


if __name__ == "__main__":
    init_database()
