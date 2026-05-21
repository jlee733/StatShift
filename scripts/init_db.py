"""Create and seed the local SQLite database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from db.schema import SCHEMA_SQL
from db.seed import DOCUMENTS


def init_database(db_path: Path | None = None) -> Path:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA_SQL)

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
