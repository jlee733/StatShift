"""Unit tests for the FastAPI read-only service."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as main_module
from api.main import app
from tests.support import DatabaseTestCase


class APITests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.settings_patcher = patch.object(main_module.settings, "db_path", self.db_path)
        # main.py imports `db` by value; patch the name bound in api.main
        self.db_patcher = patch.object(main_module, "db", self.db)
        self.settings_patcher.start()
        self.db_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.settings_patcher.stop()
        super().tearDown()

    def test_health_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["db_path"], str(self.db_path))

    def test_list_documents(self) -> None:
        response = self.client.get("/documents", params={"limit": 3})
        self.assertEqual(response.status_code, 200)
        docs = response.json()
        self.assertEqual(len(docs), 3)

    def test_get_document(self) -> None:
        response = self.client.get("/documents/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 1)

    def test_get_document_not_found(self) -> None:
        response = self.client.get("/documents/99999")
        self.assertEqual(response.status_code, 404)

    def test_search(self) -> None:
        response = self.client.get("/search", params={"q": "Chase", "limit": 5})
        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertTrue(results)
        self.assertIn("Chase", results[0]["title"])

    def test_categories(self) -> None:
        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 200)
        categories = response.json()["categories"]
        self.assertIn("matchup", categories)

    def test_write_methods_blocked(self) -> None:
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)("/documents")
            self.assertEqual(response.status_code, 405)
            self.assertIn("Write operations are disabled", response.json()["detail"])

    def test_health_missing_database(self) -> None:
        missing = self.db_path.parent / "missing.db"
        with patch.object(main_module.settings, "db_path", missing):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
