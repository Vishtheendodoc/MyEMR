"""Small in-memory login limit. It resets when the API process restarts."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

_ATTEMPTS: dict[str, deque] = defaultdict(deque)


def allow_login(key: str, limit: int = 30, window_seconds: int = 60) -> bool:
    now = datetime.utcnow()
    bucket = _ATTEMPTS[key.lower()]
    cutoff = now - timedelta(seconds=window_seconds)
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
