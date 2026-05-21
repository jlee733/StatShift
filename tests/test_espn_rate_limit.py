"""Tests for ESPN API rate limiting."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from espn.rate_limit import reset_espn_rate_limit, wait_before_espn_request


class EspnRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_espn_rate_limit()

    def tearDown(self) -> None:
        reset_espn_rate_limit()

    @patch("espn.rate_limit.time.sleep")
    @patch("espn.rate_limit.time.monotonic")
    def test_second_call_waits(self, mock_monotonic, mock_sleep) -> None:
        # First call: now=0, stamp=5. Second call: now=10, sleep 30-(10-5)=25.
        mock_monotonic.side_effect = [0.0, 5.0, 10.0, 10.0]

        with patch("espn.rate_limit.settings.espn_api_delay_seconds", 30.0):
            wait_before_espn_request()
            wait_before_espn_request()

        mock_sleep.assert_called_once_with(25.0)

    @patch("espn.rate_limit.time.sleep")
    def test_zero_delay_skips_sleep(self, mock_sleep) -> None:
        with patch("espn.rate_limit.settings.espn_api_delay_seconds", 0.0):
            wait_before_espn_request()
            wait_before_espn_request()

        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
