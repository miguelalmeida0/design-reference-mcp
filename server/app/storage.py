"""Durable, bounded research snapshots and screenshot bytes in dedicated PostgreSQL.

No secrets are serialized. Database access uses Render's DATABASE_URL only.
The in-process JOBS cache remains an optimization, never the source of truth.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import Capture, Job

MAX_PERSISTED_JOBS = 2


def job_to_dict(job: Job) -> dict:
    return {
        "brief": job.brief, "target": job.target, "directory": str(job.directory),
        "id": job.id, "view_token": job.view_token, "state": job.state,
        "created_at": job.created_at, "completed_at": job.completed_at,
        "last_error": job.last_error, "captures": [vars(c).copy() for c in job.captures],
        "attempts": job.attempts, "seen_urls": sorted(job.seen_urls),
        "served_images": sorted(job.served_images), "finalized": job.finalized,
        "pending": job.pending,
    }


def job_from_dict(data: dict) -> Job:
    job = Job(brief=data["brief"], target=data["target"],
              directory=Path(data["directory"]), id=data["id"],
              view_token=data["view_token"], state=data.get("state", "queued"),
              created_at=data["created_at"], completed_at=data.get("completed_at"),
              last_error=data.get("last_error"),
              captures=[Capture(**c) for c in data.get("captures", [])],
              attempts=data.get("attempts", []),
              seen_urls=set(data.get("seen_urls", [])),
              served_images=set(data.get("served_images", [])),
              finalized=bool(data.get("finalized", False)),
              pending=data.get("pending", []))
    return job


class PostgresStore:
    def __init__(self, url: str):
        if not url.startswith(("postgres://", "postgresql://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        self.url = url

    def connect(self):
        import psycopg
        return psycopg.connect(self.url, connect_timeout=12, sslmode="require")

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reference_jobs (
                    job_id TEXT PRIMARY KEY,
                    view_token TEXT NOT NULL,
                    snapshot JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reference_images (
                    job_id TEXT NOT NULL REFERENCES reference_jobs(job_id) ON DELETE CASCADE,
                    reference_id TEXT NOT NULL,
                    image_data BYTEA NOT NULL,
                    PRIMARY KEY (job_id, reference_id)
                )
            """)

    def save(self, job: Job) -> None:
        snapshot = json.dumps(job_to_dict(job), separators=(",", ":"), ensure_ascii=False)
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO reference_jobs (job_id, view_token, snapshot, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (job_id) DO UPDATE
                SET snapshot = EXCLUDED.snapshot, view_token = EXCLUDED.view_token,
                    updated_at = NOW()
            """, (job.id, job.view_token, snapshot))

    def load_all(self) -> list[Job]:
        with self.connect() as conn:
            rows = conn.execute("SELECT snapshot FROM reference_jobs ORDER BY updated_at DESC LIMIT %s",
                                (MAX_PERSISTED_JOBS,)).fetchall()
        return [job_from_dict(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
                for row in rows]

    def load(self, job_id: str) -> Job | None:
        with self.connect() as conn:
            row = conn.execute("SELECT snapshot FROM reference_jobs WHERE job_id=%s",
                               (job_id,)).fetchone()
        if not row:
            return None
        return job_from_dict(row[0] if isinstance(row[0], dict) else json.loads(row[0]))

    def save_image(self, job_id: str, reference_id: str, data: bytes) -> None:
        # Only store images for an existing, already persisted job.
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO reference_images (job_id, reference_id, image_data)
                VALUES (%s, %s, %s)
                ON CONFLICT (job_id, reference_id) DO UPDATE SET image_data=EXCLUDED.image_data
            """, (job_id, reference_id, data))

    def get_image(self, job_id: str, reference_id: str) -> bytes | None:
        with self.connect() as conn:
            row = conn.execute("""
                SELECT image_data FROM reference_images
                WHERE job_id=%s AND reference_id=%s
            """, (job_id, reference_id)).fetchone()
        return bytes(row[0]) if row else None

    def prune(self, keep_ids: set[str]) -> None:
        # Keep the newest two jobs only. Never remove an active job.
        with self.connect() as conn:
            rows = conn.execute("SELECT job_id FROM reference_jobs ORDER BY updated_at DESC").fetchall()
            stale = [row[0] for row in rows if row[0] not in keep_ids]
            if stale:
                conn.execute("DELETE FROM reference_jobs WHERE job_id=ANY(%s)", (stale,))


def get_store() -> PostgresStore | None:
    url = os.getenv("DATABASE_URL", "")
    if url:
        return PostgresStore(url)
    if os.getenv("RENDER") or os.getenv("REQUIRE_DURABLE_STORAGE"):
        raise RuntimeError("DATABASE_URL is required: refusing to run an ephemeral research service")
    # Local tests may intentionally run with process-local state.
    return None

