"""Protect a small Render instance from runaway Chromium page memory.

Monitor cgroup memory (not just the Python process), since Chromium renders in
separate child processes. Kill only Chromium descendants when the safety
threshold is reached. Fail the individual capture rather than killing Uvicorn.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import psutil

LOGGER = logging.getLogger(__name__)
MIB = 1024 * 1024
POLL_SECONDS = 0.075
# 512 MiB instance => stop Chromium near 384 MiB, leaving 128 MiB headroom.
MIN_HEADROOM = 128 * MIB
MAX_FRACTION = 0.75


class CaptureMemoryExceeded(RuntimeError):
    """The container memory guard stopped a resource-heavy Chromium page."""


def container_memory() -> tuple[int, int] | None:
    """Return current cgroup usage and limit, or None outside a bounded cgroup."""
    candidates = (
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"),
        ("/sys/fs/cgroup/memory/memory.usage_in_bytes",
         "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    for used_file, limit_file in candidates:
        try:
            used = int(Path(used_file).read_text().strip())
            limit = int(Path(limit_file).read_text().strip())
        except (OSError, ValueError):
            continue
        # cgroup v1 uses enormous integers when the controller is unlimited.
        if 128 * MIB <= limit < 1 << 50 and used >= 0:
            return used, limit
    return None


def over_budget(used: int, limit: int) -> bool:
    if limit <= 0:
        return False
    threshold = min(int(limit * MAX_FRACTION), limit - MIN_HEADROOM)
    return used >= max(0, threshold)


def kill_chromium_descendants() -> int:
    """Kill browser descendants only; never kill the API, Playwright driver or unrelated apps."""
    killed = 0
    try:
        descendants = psutil.Process(os.getpid()).children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0
    for proc in reversed(descendants):
        try:
            name = proc.name().lower()
            if any(word in name for word in ("chrome", "chromium", "headless_shell")):
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return killed


class BrowserMemoryGuard:
    def __init__(self, source_id: str):
        self.source_id = source_id
        self.exceeded = False
        self.last_used = 0
        self.last_limit = 0
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        self._task = asyncio.create_task(self._watch())
        return self

    async def __aexit__(self, *_exc):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch(self):
        while True:
            reading = container_memory()
            if reading:
                used, limit = reading
                if over_budget(used, limit):
                    self.exceeded = True
                    self.last_used, self.last_limit = used, limit
                    killed = kill_chromium_descendants()
                    LOGGER.warning(
                        "Chromium memory budget reached for source=%s: "
                        "cgroup=%sMiB/%sMiB; killed %s Chromium descendants",
                        self.source_id, used // MIB, limit // MIB, killed,
                    )
                    return
            await asyncio.sleep(POLL_SECONDS)

    def failure(self) -> CaptureMemoryExceeded:
        return CaptureMemoryExceeded(
            f"Chromium memory guard stopped the page at "
            f"{self.last_used // MIB}MiB/{self.last_limit // MIB}MiB"
        )


async def wait_for_headroom(max_seconds: float = 8.0) -> bool:
    """Avoid reopening Chromium while a previous browser is still releasing RAM."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_seconds
    while True:
        reading = container_memory()
        if reading is None or not over_budget(*reading):
            return True
        if loop.time() >= deadline:
            return False
        await asyncio.sleep(0.15)

