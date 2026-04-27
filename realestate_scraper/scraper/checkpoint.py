"""Resumable-run checkpoint store.

At 55k+ domains a single run will inevitably be interrupted. The
checkpoint records which domains have been *completed* (successfully or
with an authoritative error) so the next invocation skips them. The
file is a tiny JSON document; we use the stdlib `json` module to keep
the runtime dependency surface minimal.
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


class Checkpoint:
    """Atomic, lock-protected JSON checkpoint of completed domains."""

    def __init__(self, path: Path, *, enabled: bool) -> None:
        self._path = path
        self._enabled = enabled
        self._lock = asyncio.Lock()
        self._completed: set[str] = set()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    async def load(self) -> None:
        if not self._enabled:
            self._completed = set()
            return
        if not self._path.exists():
            self._completed = set()
            return
        try:
            raw = await asyncio.to_thread(self._path.read_text, "utf-8")
            payload = json.loads(raw or "{}")
        except (OSError, ValueError) as exc:
            log.warning("checkpoint unreadable, starting fresh: %s", exc)
            self._completed = set()
            return
        completed = payload.get("completed", []) if isinstance(payload, dict) else []
        self._completed = {str(item).lower() for item in completed if item}
        log.info("checkpoint loaded: %d completed domains", len(self._completed))

    async def reset(self) -> None:
        async with self._lock:
            self._completed.clear()
            if self._path.exists():
                try:
                    self._path.unlink()
                except OSError as exc:
                    log.debug("could not delete checkpoint: %s", exc)

    def has(self, domain: str) -> bool:
        if not self._enabled:
            return False
        return (domain or "").lower() in self._completed

    def filter_pending(self, domains: Iterable[str]) -> list[str]:
        if not self._enabled:
            return list(domains)
        return [d for d in domains if (d or "").lower() not in self._completed]

    async def mark(self, domain: str) -> None:
        if not self._enabled:
            return
        domain = (domain or "").lower()
        if not domain:
            return
        async with self._lock:
            if domain in self._completed:
                return
            self._completed.add(domain)
            await asyncio.to_thread(self._flush)

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"completed": sorted(self._completed)}
        # Atomic write via temp-file + rename, so an interrupted flush
        # never leaves a half-written checkpoint behind.
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=str(self._path.parent),
            prefix=self._path.name + ".",
            suffix=".tmp",
            encoding="utf-8",
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self._path)
