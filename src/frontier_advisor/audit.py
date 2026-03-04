"""Append-only JSONL audit log for advisory consultations."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_PATH = Path.home() / ".config" / "frontier-advisor" / "audit.jsonl"


class AdvisoryAuditLog:
    def __init__(self, path: Path | None = None):
        self._path = path or DEFAULT_AUDIT_PATH

    def log(self, entry: dict) -> None:
        """Append an audit entry with timestamp and optional question hash."""
        entry["logged_at"] = datetime.now(timezone.utc).isoformat()
        if "question_preview" in entry:
            entry["question_hash"] = hashlib.sha256(
                entry["question_preview"].encode()
            ).hexdigest()[:16]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            logger.exception("Failed to write audit log")

    def recent(self, n: int = 10) -> list[dict]:
        """Return the last n audit entries."""
        if not self._path.exists():
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").strip().split("\n")
            return [json.loads(line) for line in lines[-n:] if line]
        except Exception:
            logger.exception("Failed to read audit log")
            return []
