"""Exports a traceable research receipt without claiming unreviewed captures were inspected."""
import json
from app.models import Job
from app.validation import validate_job


def build_report(job: Job, motion_required: bool) -> dict:
    reasons = validate_job(job, motion_required)
    return {
        "status": "passed" if not reasons else "blocked",
        "allow_generation": not reasons,
        "reasons": reasons,
        "job": job.status(),
        "references": [c.to_public() for c in job.captures],
        "sources_attempted": job.attempts,
        "reviewed_urls": [c.url for c in job.captures if c.inspection],
    }

