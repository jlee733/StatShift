"""Global throttle between consecutive ESPN API HTTP requests."""

from __future__ import annotations

import threading
import time

from config import settings

_lock = threading.Lock()
_last_request_at: float = 0.0


def wait_before_espn_request() -> None:
    """Block until at least ``settings.espn_api_delay_seconds`` since the last ESPN call."""
    global _last_request_at

    delay = settings.espn_api_delay_seconds
    if delay <= 0:
        return

    with _lock:
        now = time.monotonic()
        if _last_request_at > 0:
            sleep_for = delay - (now - _last_request_at)
            if sleep_for > 0:
                time.sleep(sleep_for)
        _last_request_at = time.monotonic()


def reset_espn_rate_limit() -> None:
    """Reset throttle state (for tests)."""
    global _last_request_at
    with _lock:
        _last_request_at = 0.0
