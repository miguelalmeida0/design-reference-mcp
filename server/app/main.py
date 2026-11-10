"""Stateless MCP Streamable-HTTP endpoint plus an evidence-only research board.

MCP protocol subset: initialize, notifications/initialized, tools/list and tools/call.
The REST board is read-only and separately scoped by unpredictable viewing tokens.
"""
from __future__ import annotations
import asyncio
import base64
import hmac
import os
import secrets
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.board import render_board
from app.browsing import run_capture_job
from app.catalog import SOURCES
from app.models import Job, now
from app.report import build_report
from app.storage import get_store

app = FastAPI(title="Design References — Browser MCP", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
JOBS: dict[str, Job] = {}
STORE = get_store()
SEMAPHORE = asyncio.Semaphore(1)
STORAGE = Path(os.getenv("RESEARCH_STORAGE", "/tmp/design-references"))
MAX_JOBS = 2
MCP_VERSION = "2025-06-18"


async def persist(job: Job) -> None:
    if STORE:
        await asyncio.to_thread(STORE.save, job)


async def persist_image(job: Job, ref_id: str, data: bytes) -> None:
    if STORE:
        await asyncio.to_thread(STORE.save_image, job.id, ref_id, data)


async def capture_task(job: Job) -> None:
    await run_capture_job(job, SEMAPHORE, persist=persist, save_image=persist_image)


@app.on_event("startup")
async def restore_research_jobs() -> None:
    if STORE is None:
        return
    await asyncio.to_thread(STORE.initialize)
    jobs = await asyncio.to_thread(STORE.load_all)
    JOBS.clear()
    for job in jobs:
        JOBS[job.id] = job
        if job.state in {"queued", "running"}:
            asyncio.create_task(capture_task(job))



def schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False,
    }}


STRING = {"type": "string"}
TOOL_SCHEMAS = [
    schema("list_reference_sources", "List the fixed, user-saved public design reference seeds; this is NOT proof they were visited.", {}, []),
    schema("start_reference_research", "Start REAL Chromium browsing of 25–30 saved design references; returns a live visual research board. Research cannot pass from URLs alone.",
           {"brief": {"type": "string", "minLength": 10, "maxLength": 1000},
            "target": {"type": "integer", "minimum": 25, "maximum": 30}}, ["brief"]),
    schema("get_research_status", "Read browser attempts, captures and human/model visual review progress.", {"job_id": STRING}, ["job_id"]),
    schema("inspect_reference", "RETURN THE ACTUAL SCREENSHOT as MCP image content. Call this before recording a visual review.",
           {"job_id": STRING, "reference_id": STRING}, ["job_id", "reference_id"]),
    schema("record_visual_review", "Record a specific visual observation from a screenshot already opened using inspect_reference. Cannot automatically infer taste from URLs.",
           {"job_id": STRING, "reference_id": STRING, "visual_observation": STRING,
            "product_reason": STRING, "transferable_mechanism": STRING,
            "motion_observed": {"type": "boolean"}},
           ["job_id", "reference_id", "visual_observation", "product_reason", "transferable_mechanism"]),
    schema("finalize_reference_research", "FAIL-CLOSED pre-design gate: requires 25–30 visually inspected screenshots, 16 individual works and five source families; motion work requires five observed interactions.",
           {"job_id": STRING, "motion_required": {"type": "boolean"}}, ["job_id"]),
    schema("get_research_board", "Return a live read-only page showing actual reference captures and review status.",
           {"job_id": STRING}, ["job_id"]),
    schema("get_research_report", "Return the structured evidence manifest and incomplete-gate reasons.",
           {"job_id": STRING, "motion_required": {"type": "boolean"}}, ["job_id"]),
]


def tool_text(data: Any, error: bool = False) -> dict:
    import json
    result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
              "isError": error}
    if isinstance(data, dict):
        result["structuredContent"] = data
    return result


def find_job(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if job is None and STORE:
        job = STORE.load(job_id)
        if job:
            JOBS[job_id] = job
    if job is None:
        raise ValueError("Research job not found or expired")
    return job


def find_capture(job: Job, reference_id: str):
    return next((c for c in job.captures if c.id == reference_id), None)


async def run_tool(name: str, args: dict, request: Request) -> dict:
    if name == "list_reference_sources":
        return tool_text({"count": len(SOURCES), "sources": [vars(s) for s in SOURCES]})
    if name == "start_reference_research":
        brief = str(args.get("brief", "")).strip()
        target = args.get("target", 28)
        if not (10 <= len(brief) <= 1000) or isinstance(target, bool) or not isinstance(target, int) or not 25 <= target <= 30:
            raise ValueError("Provide a brief of 10–1000 characters and a target of 25–30")
        if any(j.state in {"queued", "running"} for j in JOBS.values()):
            raise ValueError("A browser research job is already running. Poll its status first.")
        # Bounded cache and durable history. Never discard an active job.
        while len(JOBS) >= MAX_JOBS:
            completed = [j for j in JOBS.values() if j.state not in {"queued", "running"}]
            if not completed:
                raise ValueError("No capacity for another concurrent research job")
            old = min(completed, key=lambda j: j.created_at)
            JOBS.pop(old.id, None)
        job = Job(brief=brief, target=target, directory=STORAGE / secrets.token_urlsafe(12))
        job.directory.mkdir(parents=True, exist_ok=True)
        JOBS[job.id] = job
        await persist(job)
        if STORE:
            await asyncio.to_thread(STORE.prune, set(JOBS))
        asyncio.create_task(capture_task(job))
        return tool_text({"job_id": job.id, "state": job.state, "board_url": board_url(request, job),
                          "note": "Captured != visually reviewed. Generate no concepts until finalize_reference_research passes."})
    job = find_job(str(args.get("job_id", "")))
    if name == "get_research_status":
        return tool_text({**job.status(), "captures": [c.to_public() for c in job.captures], "attempts": job.attempts[-35:]})
    if name == "get_research_board":
        return tool_text({"board_url": board_url(request, job), "job": job.status()})
    if name == "inspect_reference":
        reference_id = str(args.get("reference_id", ""))
        cap = find_capture(job, reference_id)
        if cap is None:
            raise ValueError("Reference screenshot not found")
        data = (await asyncio.to_thread(STORE.get_image, job.id, reference_id)) if STORE else None
        if data is None:
            data = await asyncio.to_thread(Path(cap.screenshot).read_bytes)
        job.served_images.add(reference_id)
        await persist(job)
        return {"content": [
            {"type": "text", "text": __import__("json").dumps(cap.to_public(), ensure_ascii=False)},
            {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/jpeg" if cap.screenshot.endswith(".jpg") else "image/png"}
        ], "isError": False}
    if name == "record_visual_review":
        ref_id = str(args.get("reference_id", ""))
        cap = find_capture(job, ref_id)
        if cap is None:
            raise ValueError("Reference not found")
        if ref_id not in job.served_images:
            raise ValueError("Call inspect_reference and inspect the actual screenshot before writing a review")
        if job.finalized:
            raise ValueError("This report is finalized")
        strings = {}
        for field in ("visual_observation", "product_reason", "transferable_mechanism"):
            value = str(args.get(field, "")).strip()
            if len(value) < 45 or len(value) > 1800:
                raise ValueError(f"{field} must contain a specific 45–1800-character observation")
            strings[field] = value
        motion = args.get("motion_observed", False)
        if not isinstance(motion, bool):
            raise ValueError("motion_observed must be boolean")
        if motion and not cap.motion_probe.get("measured"):
            raise ValueError("Cannot claim observed animation; browser motion probe did not measure any")
        cap.inspection = {**strings, "motion_observed": motion, "reviewed_at": now(),
                          "inspection_basis": "screenshot_served_by_mcp"}
        await persist(job)
        return tool_text({"reference_id": ref_id, "reviewed": True, "reviewed_total": job.status()["reviewed"]})
    if name in {"finalize_reference_research", "get_research_report"}:
        motion = args.get("motion_required", True)
        if not isinstance(motion, bool):
            raise ValueError("motion_required must be boolean")
        report = build_report(job, motion)
        if name == "finalize_reference_research":
            if report["allow_generation"]:
                job.finalized = True
                await persist(job)
            return tool_text({"allow_generation": report["allow_generation"], "reasons": report["reasons"],
                              "counts": job.status(), "report": report if report["allow_generation"] else None},
                             error=not report["allow_generation"])
        return tool_text(report)
    raise ValueError("Unknown MCP tool")


def board_url(request: Request, job: Job) -> str:
    root = os.getenv("SERVICE_PUBLIC_ORIGIN", str(request.base_url).rstrip("/"))
    return f"{root}/boards/{job.id}/{job.view_token}"


def mcp_ok(rpc_id: Any, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result}, media_type="application/json")


def mcp_error(rpc_id: Any, code: int, message: str, http_status=200) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                         "error": {"code": code, "message": message}}, status_code=http_status)


def authorized(request: Request) -> bool:
    expected = os.getenv("MCP_API_KEY", "")
    supplied = request.headers.get("authorization", "")
    return bool(expected) and supplied.startswith("Bearer ") and hmac.compare_digest(supplied[7:], expected)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "mcp_endpoint": "/mcp", "browser": "chromium", "service": "design-reference-browser"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    if not authorized(request):
        return JSONResponse({"error": "Authentication required"}, status_code=401,
                            headers={"WWW-Authenticate": 'Bearer realm="reference-browser"'})
    origin = request.headers.get("origin")
    allowed_origins = {"https://chatgpt.com", "https://chat.openai.com"}
    if origin and origin not in allowed_origins and not origin.startswith(("http://localhost:", "http://127.0.0.1:")):
        return JSONResponse({"error": "Origin not permitted"}, status_code=403)
    if int(request.headers.get("content-length", 0)) > 250_000:
        return JSONResponse({"error": "Request too large"}, status_code=413)
    try:
        payload = await request.json()
    except Exception:
        return mcp_error(None, -32700, "Malformed JSON", 400)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return mcp_error(payload.get("id") if isinstance(payload, dict) else None, -32600, "Invalid JSON-RPC request")
    method = payload.get("method")
    rpc_id = payload.get("id")
    if method == "notifications/initialized":
        return Response(status_code=202)
    if method == "initialize":
        return mcp_ok(rpc_id, {"protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "design-reference-browser", "version": "0.1.0"},
            "instructions": "Inspect screenshots and record specific findings before finalizing. Browsing only the URL catalog does not pass the research gate."})
    if method == "ping":
        return mcp_ok(rpc_id, {})
    if method == "tools/list":
        return mcp_ok(rpc_id, {"tools": TOOL_SCHEMAS})
    if method == "tools/call":
        params = payload.get("params") or {}
        name, arguments = params.get("name"), params.get("arguments") or {}
        if name not in {t["name"] for t in TOOL_SCHEMAS}:
            return mcp_error(rpc_id, -32601, "Tool not found")
        if not isinstance(arguments, dict):
            return mcp_error(rpc_id, -32602, "Tool arguments must be an object")
        try:
            return mcp_ok(rpc_id, await run_tool(name, arguments, request))
        except ValueError as err:
            return mcp_ok(rpc_id, tool_text({"error": str(err)}, error=True))
        except Exception:
            return mcp_ok(rpc_id, tool_text({"error": "An internal error occurred"}, error=True))
    return mcp_error(rpc_id, -32601, "Method not found")


@app.get("/mcp")
async def mcp_get():
    return Response(status_code=405)


def board_job(job_id: str, token: str) -> Job | None:
    try:
        j = find_job(job_id)
    except ValueError:
        return None
    return j if hmac.compare_digest(j.view_token, token) else None


@app.get("/boards/{job_id}/{token}")
async def view_board(job_id: str, token: str):
    job = board_job(job_id, token)
    if not job:
        return Response(status_code=404)
    return HTMLResponse(render_board(job.id, token), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.get("/boards/{job_id}/{token}/state")
async def board_state(job_id: str, token: str):
    job = board_job(job_id, token)
    if not job:
        return Response(status_code=404)
    return JSONResponse({"status": job.status(), "captures": [c.to_public() for c in job.captures]},
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.get("/boards/{job_id}/{token}/image/{reference_id}")
async def board_image(job_id: str, token: str, reference_id: str):
    job = board_job(job_id, token)
    if not job:
        return Response(status_code=404)
    cap = find_capture(job, reference_id)
    if not cap:
        return Response(status_code=404)
    data = (await asyncio.to_thread(STORE.get_image, job.id, reference_id)) if STORE else None
    if data is None:
        data = await asyncio.to_thread(Path(cap.screenshot).read_bytes)
    return Response(content=data, media_type="image/jpeg" if cap.screenshot.endswith(".jpg") else "image/png", headers={"Cache-Control": "private, max-age=120", "Referrer-Policy": "no-referrer"})

