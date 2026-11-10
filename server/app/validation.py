"""Fail-closed pre-design research validation."""
from collections import Counter
from datetime import datetime, timezone
from app.models import Job

MIN_REFERENCES = 25
MAX_REFERENCES = 30
MIN_PROJECTS = 16
MIN_SOURCES = 5
MIN_MOTION = 5


def validate_job(job: Job, motion_required: bool) -> list[str]:
    errors: list[str] = []
    if job.state != "complete":
        errors.append("Browser capture job has not completed")
    reviewed = [c for c in job.captures if c.inspection]
    if not MIN_REFERENCES <= len(reviewed) <= MAX_REFERENCES:
        errors.append(f"Need 25–30 visually reviewed references; found {len(reviewed)}")
    if len({c.url for c in reviewed}) != len(reviewed):
        errors.append("Duplicate URLs in reviewed set")
    if len({c.sha256 for c in reviewed}) != len(reviewed):
        errors.append("Duplicate screenshot content in reviewed set")
    projects = [c for c in reviewed if c.source_category in {"project", "specific", "discovered_project"}]
    if len(projects) < MIN_PROJECTS:
        errors.append(f"Need at least 16 individual projects; found {len(projects)}")
    if len({c.source_id for c in reviewed}) < MIN_SOURCES:
        errors.append("Need five distinct source families")
    motion = [c for c in reviewed if c.inspection.get("motion_observed") is True and c.motion_probe.get("measured")]
    if motion_required and len(motion) < MIN_MOTION:
        errors.append(f"Need five observed motion examples; found {len(motion)}")
    for c in reviewed:
        report = c.inspection or {}
        for key in ("visual_observation", "product_reason", "transferable_mechanism"):
            if len(str(report.get(key, "")).strip()) < 45:
                errors.append(f"{c.id}: missing substantive {key}")
        if not c.screenshot:
            errors.append(f"{c.id}: missing screenshot")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(job.created_at)).total_seconds()
        if age > 60 * 60 * 12:
            errors.append("Research run is older than 12 hours")
    except ValueError:
        errors.append("Invalid research timestamp")
    return errors

