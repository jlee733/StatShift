"""Shared helpers for StatShift unit tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.read import ReadOnlyDatabase  # noqa: E402
from scripts.init_db import init_database  # noqa: E402


class DatabaseTestCase(unittest.TestCase):
    """Provides a seeded temporary SQLite database."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "statshift_test.db"
        init_database(self.db_path)
        self.db = ReadOnlyDatabase(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()
