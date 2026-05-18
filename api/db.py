"""Read-only SQLite access for the FastAPI layer."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config import settings


class ReadOnlyDatabase:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def list_documents(
        self,
        *,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = "SELECT id, title, category, content, created_at FROM documents"
        params: list[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, doc_id: int) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, title, category, content, created_at FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
        return dict(row) if row else None

    def search_documents(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        fts_query = query.strip()
        if fts_query:
            try:
                with self.connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT d.id, d.title, d.category, d.content, d.created_at,
                               bm25(documents_fts) AS score
                        FROM documents_fts
                        JOIN documents d ON d.id = documents_fts.rowid
                        WHERE documents_fts MATCH ?
                        ORDER BY score
                        LIMIT ?
                        """,
                        (fts_query, limit),
                    ).fetchall()
                if rows:
                    return [dict(row) for row in rows]
            except sqlite3.OperationalError:
                pass

        like = f"%{query}%"
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, category, content, created_at, 0.0 AS score
                FROM documents
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY id
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_categories(self) -> list[str]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM documents ORDER BY category"
            ).fetchall()
        return [row["category"] for row in rows]


db = ReadOnlyDatabase()
