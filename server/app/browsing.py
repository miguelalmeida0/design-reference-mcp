"""One-at-a-time real Chromium captures from a constrained public reference library."""
from __future__ import annotations
import asyncio
import hashlib
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
from playwright.async_api import async_playwright, TimeoutError as PwTimeout

from app.catalog import SOURCES, Source, is_allowed_reference_url
from app.models import Capture, Job, now
from app.security import is_private_subrequest, publicly_routable_host, safe_navigation
from app.memory_budget import BrowserMemoryGuard, CaptureMemoryExceeded, wait_for_headroom

PAGE_TIMEOUT = 12000
MAX_ATTEMPTS = 95
AGENT = "ReferenceBrowserResearch/0.1 (+public design inspiration; rate-limited)"


async def check_robots(url: str, cache: dict[str, RobotFileParser | None]) -> bool:
    host = urlparse(url).hostname or ""
    if host not in cache:
        robot_url = f"https://{host}/robots.txt"
        parser = RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                r = await client.get(robot_url, headers={"User-Agent": AGENT})
            if r.status_code == 200:
                parser.parse(r.text.splitlines())
                cache[host] = parser
            elif r.status_code == 404:
                cache[host] = None  # No published robots restrictions.
            else:
                cache[host] = RobotFileParser()
                cache[host].parse(["User-agent: *", "Disallow: /"])
        except Exception:
            cache[host] = RobotFileParser()
            cache[host].parse(["User-agent: *", "Disallow: /"])
    rp = cache[host]
    return rp is None or rp.can_fetch(AGENT, url)


async def route_guard(route, dns_cache: dict[str, bool]) -> None:
    url = route.request.url
    if route.request.resource_type in {"media", "websocket"}:
        await route.abort()
        return
    if is_private_subrequest(url):
        await route.abort()
        return
    host = urlparse(url).hostname or ""
    if host not in dns_cache:
        dns_cache[host] = await asyncio.to_thread(publicly_routable_host, host)
    if not dns_cache[host]:
        await route.abort()
        return
    await route.continue_()


def looks_like_project(url: str) -> bool:
    p = urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return False
    bad = {"login", "signup", "pricing", "contact", "about", "terms", "privacy",
           "category", "categories", "tag", "tags", "collection", "collections",
           "search", "archive", "page", "browse", "journal", "shop", "newsletter",
           "dashboard", "support", "help", "index"}
    if parts[0].lower() in bad:
        return False
    return (len(parts) >= 2 or (len(parts) == 1 and len(parts[0]) > 7))


async def links_from_page(page, source: Source) -> list[Source]:
    if source.category not in {"gallery", "archive"}:
        return []
    try:
        hrefs = await page.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({url:e.href,label:(e.innerText||e.getAttribute('aria-label')||'').trim()}))"
        )
    except Exception:
        return []
    out, seen = [], set()
    base_host = urlparse(source.url).hostname
    for item in hrefs:
        href = (item.get("url") or "").split("#")[0]
        if (not is_allowed_reference_url(href) or urlparse(href).hostname != base_host
                or not looks_like_project(href) or href in seen):
            continue
        seen.add(href)
        label = (item.get("label") or "").replace("\n", " ")[:90].strip()
        out.append(Source(f"{source.id}-project", label or urlparse(href).path.strip("/")[:60], href, "discovered_project"))
        if len(out) >= 20:
            break
    return out


async def measure_motion(page) -> dict:
    """Only a heuristic. Reviewers still must see the actual screenshots to claim motion."""
    try:
        el = page.locator("a[href], button").first
        if await el.count() == 0:
            return {"measured": False, "trigger": None, "running_animations": 0}
        await el.hover(timeout=1600)
        await page.wait_for_timeout(100)
        animations = await page.evaluate("() => document.getAnimations().filter(a=>a.playState === 'running').length")
        return {"measured": animations > 0, "trigger": "hover", "running_animations": animations}
    except Exception:
        return {"measured": False, "trigger": None, "running_animations": 0}


async def capture(browser_context, job: Job, source: Source, dns_cache: dict[str, bool], robots, save_image=None) -> list[Source]:
    if not is_allowed_reference_url(source.url):
        raise ValueError("Reference URL is not in the fixed allowlist")
    if not await asyncio.to_thread(safe_navigation, source.url):
        raise ValueError("Reference DNS is not publicly routable")
    if not await check_robots(source.url, robots):
        raise PermissionError("robots.txt disallows automated access or is unavailable")

    page = await browser_context.new_page()
    try:
        await page.route("**/*", lambda r: route_guard(r, dns_cache))
        await page.goto(source.url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        await page.wait_for_timeout(350)
        final_url = page.url.split("#")[0]
        if not is_allowed_reference_url(final_url) or not await asyncio.to_thread(safe_navigation, final_url):
            raise PermissionError("Redirect left the permitted public reference set")
        links = await links_from_page(page, source)
        title = (await page.title() or source.title)[:180]
        headings = await page.locator("h1,h2").all_text_contents()
        headings = [x.strip()[:140] for x in headings if x.strip()][:6]
        interactions = await page.locator("button,a[href],[role='button']").count()
        motion = await measure_motion(page)
        # JPEG reduces database payloads and response memory. No need to wait for
        # expensive long-running animations to finish a static visual inspection.
        shot = await page.screenshot(type="jpeg", quality=72, full_page=False,
                                     animations="disabled", timeout=15000, caret="hide")
        sha = hashlib.sha256(shot).hexdigest()
        if any(x.sha256 == sha or x.url == final_url for x in job.captures):
            raise ValueError("Duplicate URL or screenshot")
        rid = f"r{len(job.captures)+1:02d}"
        path = job.directory / f"{rid}.jpg"
        if save_image:
            await save_image(job, rid, shot)
        else:
            await asyncio.to_thread(path.write_bytes, shot)
        job.captures.append(Capture(
            id=rid, url=final_url, title=title, source_id=source.id,
            source_category=source.category, screenshot=str(path),
            sha256=sha, captured_at=now(), headings=headings,
            detected_interactions=[f"{interactions} visible links/buttons"], motion_probe=motion
        ))
        return links
    finally:
        await page.close()


async def visit_reference(pw, job: Job, source: Source, dns_cache, robots, save_image=None) -> list[Source]:
    """Each source gets an isolated Chromium process with active cgroup monitoring.

    Reusing even a three-page Chromium session produced a 512 MiB OOM kill.
    A fresh process and a memory guard prevent one expensive public site from
    taking down the API and erasing other in-flight client requests.
    """
    if not await wait_for_headroom():
        raise CaptureMemoryExceeded("Container did not recover enough memory for another browser")

    browser = None
    context = None
    guard = BrowserMemoryGuard(source.id)
    async with guard:
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-accelerated-2d-canvas", "--disable-webgl",
                      "--disable-background-networking", "--renderer-process-limit=1",
                      "--no-zygote", "--js-flags=--max-old-space-size=96"])
            if guard.exceeded:
                raise guard.failure()
            context = await browser.new_context(
                viewport={"width": 1024, "height": 700}, device_scale_factor=1,
                user_agent=AGENT, accept_downloads=False, service_workers="block")
            if guard.exceeded:
                raise guard.failure()
            return await capture(context, job, source, dns_cache, robots, save_image)
        except Exception:
            if guard.exceeded:
                raise guard.failure() from None
            raise
        finally:
            # Browser processes must not accumulate, even after page exceptions.
            if context is not None:
                try:
                    await asyncio.wait_for(context.close(), timeout=4)
                except Exception:
                    pass
            if browser is not None:
                try:
                    await asyncio.wait_for(browser.close(), timeout=4)
                except Exception:
                    pass


async def run_capture_job(job: Job, semaphore: asyncio.Semaphore, persist=None, save_image=None) -> None:
    """Continue from durable checkpoints; an interrupted URL is never retried blindly."""
    async def checkpoint():
        if persist:
            await persist(job)

    async with semaphore:
        job.state = "running"
        job.completed_at = None
        robots: dict = {}
        dns_cache: dict = {}
        if job.pending:
            queue = deque(Source(**item) for item in job.pending)
        elif not job.attempts:
            ordered = [s for s in SOURCES if s.category in {"specific", "project"}]
            ordered += [s for s in SOURCES if s.category in {"gallery", "archive"}]
            queue = deque(ordered)
            job.pending = [vars(item).copy() for item in queue]
        else:
            queue = deque()

        await checkpoint()
        try:
            async with async_playwright() as pw:
                while queue and len(job.captures) < job.target and len(job.attempts) < MAX_ATTEMPTS:
                    source = queue[0]
                    key = source.url.split("#")[0]
                    if key in job.seen_urls:
                        # If a process was killed mid-capture, its URL remains
                        # marked in the durable in-flight checkpoint. Don't
                        # replay the same memory spike after the next restart.
                        if not any(a.get("url") == source.url for a in job.attempts):
                            job.attempts.append({
                                "url": source.url, "status": "blocked",
                                "reason": "Previous Chromium capture interrupted by service restart",
                            })
                        queue.popleft()
                        job.pending = [vars(x).copy() for x in queue]
                        await checkpoint()
                        continue

                    # Save the in-flight URL BEFORE launching Chromium. A hard
                    # cgroup kill cannot erase this checkpoint.
                    job.seen_urls.add(key)
                    await checkpoint()
                    try:
                        discovered = await visit_reference(
                            pw, job, source, dns_cache, robots, save_image)
                        job.attempts.append({"url": source.url, "status": "captured"})
                        for link in discovered:
                            if link.url not in job.seen_urls and all(x.url != link.url for x in queue):
                                queue.append(link)
                    except Exception as err:
                        job.attempts.append({
                            "url": source.url, "status": "blocked",
                            "reason": str(err)[:160],
                        })
                    queue.popleft()
                    job.pending = [vars(x).copy() for x in queue]
                    await checkpoint()
                    await asyncio.sleep(0.45)
            job.state = "complete"
        except Exception as err:
            job.state = "failed"
            job.last_error = f"Browser startup or session failed: {str(err)[:350]}"
        finally:
            job.completed_at = now()
            await checkpoint()

