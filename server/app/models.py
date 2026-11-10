"""Small, explicit research state model."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import secrets


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Capture:
    id: str
    url: str
    title: str
    source_id: str
    source_category: str
    screenshot: str
    sha256: str
    captured_at: str
    inspection: dict[str, Any] | None = None
    motion_probe: dict[str, Any] = field(default_factory=dict)
    detected_interactions: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)

    def to_public(self) -> dict:
        d = vars(self).copy()
        d.pop("screenshot")
        return d


@dataclass
class Job:
    brief: str
    target: int
    directory: Path
    id: str = field(default_factory=lambda: secrets.token_urlsafe(15))
    view_token: str = field(default_factory=lambda: secrets.token_urlsafe(18))
    state: str = "queued"
    created_at: str = field(default_factory=now)
    completed_at: str | None = None
    last_error: str | None = None
    captures: list[Capture] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    seen_urls: set[str] = field(default_factory=set)
    served_images: set[str] = field(default_factory=set)
    finalized: bool = False
    pending: list[dict[str, str]] = field(default_factory=list)

    def status(self) -> dict:
        return {
            "job_id": self.id,
            "state": self.state,
            "brief": self.brief,
            "target": self.target,
            "captured": len(self.captures),
            "reviewed": sum(1 for c in self.captures if c.inspection is not None),
            "attempted": len(self.attempts),
            "finished": self.completed_at,
            "last_error": self.last_error,
            "finalized": self.finalized,
        }

