"""Thread-safe local session storage with a replaceable persistence boundary."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class SessionRecord:
    value: dict[str, Any]
    touched_at: float


class InMemorySessionStore:
    """Small localhost session store safe for ThreadingHTTPServer.

    A future shared-server deployment can replace this class with a disk or
    database adapter without changing route handlers.
    """

    def __init__(
        self,
        ttl_seconds: int = 1800,
        max_sessions: int = 10,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def create(self, value: dict[str, Any]) -> str:
        with self._lock:
            self._cleanup_locked()
            token = secrets.token_urlsafe(32)
            self._records[token] = SessionRecord(value=value, touched_at=self._clock())
            self._enforce_limit_locked()
            return token

    def get(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            record = self._records.get(token)
            if record is None:
                return None
            record.touched_at = self._clock()
            return record.value

    def delete(self, token: str) -> bool:
        with self._lock:
            return self._records.pop(token, None) is not None

    def cleanup(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def __len__(self) -> int:
        with self._lock:
            self._cleanup_locked()
            return len(self._records)

    def _cleanup_locked(self) -> None:
        cutoff = self._clock() - self.ttl_seconds
        expired = [token for token, record in self._records.items() if record.touched_at < cutoff]
        for token in expired:
            del self._records[token]

    def _enforce_limit_locked(self) -> None:
        overflow = len(self._records) - self.max_sessions
        if overflow <= 0:
            return
        oldest = sorted(self._records, key=lambda token: self._records[token].touched_at)
        for token in oldest[:overflow]:
            del self._records[token]
