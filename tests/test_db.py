"""Unit tests for read-only SQLite access."""

from __future__ import annotations

from tests.support import DatabaseTestCase


class ReadOnlyDatabaseTests(DatabaseTestCase):
    def test_list_documents_returns_seeded_rows(self) -> None:
        docs = self.db.list_documents(limit=50)
        self.assertGreaterEqual(len(docs), 8)
        self.assertIn("title", docs[0])
        self.assertIn("category", docs[0])
        self.assertIn("content", docs[0])

    def test_list_documents_filters_by_category(self) -> None:
        players = self.db.list_documents(category="player", limit=50)
        self.assertTrue(players)
        self.assertTrue(all(doc["category"] == "player" for doc in players))

    def test_get_document_returns_row(self) -> None:
        doc = self.db.get_document(1)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["id"], 1)
        self.assertIn("McCaffrey", doc["title"])

    def test_get_document_missing_returns_none(self) -> None:
        self.assertIsNone(self.db.get_document(99999))

    def test_search_finds_relevant_document(self) -> None:
        results = self.db.search_documents("Chase", limit=5)
        self.assertTrue(results)
        self.assertTrue(
            any("Chase" in doc["title"] or "Chase" in doc["content"] for doc in results)
        )

    def test_search_team_content(self) -> None:
        results = self.db.search_documents("Bills", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_list_categories(self) -> None:
        categories = self.db.list_categories()
        self.assertIn("player", categories)
        self.assertIn("matchup", categories)


if __name__ == "__main__":
    import unittest

    unittest.main()
