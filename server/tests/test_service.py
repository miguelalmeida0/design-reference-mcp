import base64
import os
from pathlib import Path
import secrets
import pytest
from fastapi.testclient import TestClient

os.environ["MCP_API_KEY"] = "dev-test-key"
from app.main import app, JOBS
from app.models import Job, Capture, now
from app.validation import validate_job
from app.catalog import SOURCES, is_allowed_reference_url

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test-key", "Accept": "application/json, text/event-stream"}


def rpc(method, params=None, headers=None, id=1):
    return client.post("/mcp", headers=AUTH if headers is None else headers,
                       json={"jsonrpc": "2.0", "id": id, "method": method,
                             **({"params": params} if params is not None else {})})


def tool(name, args=None):
    return rpc("tools/call", {"name": name, "arguments": args or {}}).json()["result"]


def mk_job(tmp_path, count=28, reviewed=True, motion=False):
    d = tmp_path / "jobs"; d.mkdir(exist_ok=True)
    j = Job(brief="An agent reviews a meeting move without sending messages", target=28, directory=d)
    j.state = "complete"
    for n in range(count):
        path = d / f"r{n:02d}.png"
        path.write_bytes(bytes([n % 256]))
        c = Capture(id=f"r{n:02d}", url=f"https://recent.design/i/artifact-{n:02d}",
                    title=f"Reference {n}", source_id=f"collection-{n%7}",
                    source_category="discovered_project" if n < 19 else "gallery",
                    screenshot=str(path), sha256=f"sha-{n:02d}",captured_at=now(),
                    motion_probe={"measured": n < 6})
        if reviewed:
            c.inspection = {"visual_observation": "A considered visual observation with clear hierarchy, layout detail and real content.",
                            "product_reason": "This interaction belongs to the application because its hierarchy reveals the action's consequence.",
                            "transferable_mechanism": "Use the spatial response to make the decision readable before approval rather than relying on a separate notification.",
                            "motion_observed": motion and n < 6}
        j.captures.append(c)
    return j


def test_mcp_requires_auth():
    r = rpc("initialize", headers={})
    assert r.status_code == 401
    assert r.json()["error"] == "Authentication required"


def test_mcp_initialize_and_tools_list():
    r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
    assert r.status_code == 200
    assert r.json()["result"]["protocolVersion"] == "2025-06-18"
    tools = rpc("tools/list").json()["result"]["tools"]
    assert len(tools) == 8
    assert any(x["name"] == "inspect_reference" for x in tools)
    assert client.post("/mcp", headers=AUTH, json={"jsonrpc":"2.0", "method":"notifications/initialized"}).status_code == 202


def test_api_rejects_untrusted_origins():
    assert rpc("tools/list",headers={**AUTH,"Origin":"https://evil.example"}).status_code == 403


def test_domain_is_fixed():
    assert is_allowed_reference_url("https://recent.design/i/screen-3")
    assert not is_allowed_reference_url("http://recent.design/i/screen-3")
    assert not is_allowed_reference_url("https://127.0.0.1:8000/evil")
    assert not is_allowed_reference_url("https://recent.design.evil.com/")
    assert not is_allowed_reference_url("https://evil.com@recent.design:8000/")


def test_research_gate_blocks_24_and_unreviewed(tmp_path):
    assert any("25" in x for x in validate_job(mk_job(tmp_path, count=24), False))
    assert any("visually reviewed" in x for x in validate_job(mk_job(tmp_path, count=28,reviewed=False),False))


def test_research_gate_accepts_real_reviewed_shape(tmp_path):
    job = mk_job(tmp_path, motion=True)
    assert validate_job(job, True) == []
    job.captures[0].inspection["visual_observation"] = "generic"
    assert any("visual_observation" in x for x in validate_job(job,True))


def test_inspection_requires_image_served(tmp_path):
    j=mk_job(tmp_path)
    JOBS[j.id]=j
    args={"job_id": j.id,"reference_id":"r00",
          "visual_observation":"I inspected an intentional layout with a clear control and visible release feedback.",
          "product_reason":"The original project uses the physical control to protect a decision boundary.",
          "transferable_mechanism":"Translate that physical control into direct manipulation of the user's permission boundary."}
    assert tool("record_visual_review",args)["isError"] is True
    screenshot=tool("inspect_reference",{"job_id":j.id,"reference_id":"r00"})
    assert screenshot["content"][1]["type"]=="image"
    assert base64.b64decode(screenshot["content"][1]["data"]) == bytes([0])
    assert tool("record_visual_review",args)["isError"] is False
    del JOBS[j.id]


def test_finalize_blocks_unreviewed_and_board_private(tmp_path):
    j=mk_job(tmp_path,reviewed=False)
    JOBS[j.id]=j
    assert tool("finalize_reference_research",{"job_id":j.id,"motion_required":False})["isError"] is True
    assert not j.finalized
    assert client.get(f"/boards/{j.id}/{j.view_token}").status_code == 200
    assert client.get(f"/boards/{j.id}/wrong-token").status_code == 404
    assert client.get(f"/boards/{j.id}/{j.view_token}/state").status_code == 200
    del JOBS[j.id]


def test_start_refuses_invalid_target():
    assert tool("start_reference_research",{"brief":"Research these references first", "target":24})["isError"] is True


def test_unknown_tool_and_method():
    assert rpc("tools/call",{"name":"delete_everything","arguments":{}}).json()["error"]["code"]==-32601
    assert rpc("madeup").json()["error"]["code"]==-32601


def test_job_snapshot_roundtrip_preserves_progress_and_reviews(tmp_path):
    from app.storage import job_to_dict, job_from_dict
    job = mk_job(tmp_path, count=3, reviewed=True)
    job.state = "running"
    job.served_images.update({"r00", "r01"})
    job.seen_urls.update({"https://recent.design/i/artifact-00"})
    job.pending = [{"id": "next", "title": "Next Project",
                    "url": "https://recent.design/i/next-work", "category": "specific"}]
    job.attempts.append({"url": "https://recent.design/i/artifact-00", "status": "captured"})
    restored = job_from_dict(job_to_dict(job))
    assert restored.status() == job.status()
    assert restored.view_token == job.view_token
    assert restored.captures[0].inspection == job.captures[0].inspection
    assert restored.pending == job.pending
    assert restored.served_images == job.served_images
    assert restored.seen_urls == job.seen_urls


def test_recovery_loads_jobs_and_queues_unfinished_work(tmp_path, monkeypatch):
    import asyncio
    from app import main
    from app.storage import job_to_dict, job_from_dict

    job = mk_job(tmp_path, count=2, reviewed=True)
    job.state = "running"
    job.pending = [{"id": "next", "title": "Project",
                    "url": "https://recent.design/i/next", "category": "specific"}]
    called = []
    class Store:
        def initialize(self):
            called.append("init")
        def load_all(self):
            called.append("load")
            return [job_from_dict(job_to_dict(job))]
    async def resumed(value):
        called.append(("resume", value.id, len(value.captures), len(value.pending)))
    monkeypatch.setattr(main, "STORE", Store())
    monkeypatch.setattr(main, "capture_task", resumed)
    main.JOBS.clear()
    async def restart():
        await main.restore_research_jobs()
        await asyncio.sleep(0)
    asyncio.run(restart())
    assert called == ["init", "load", ("resume", job.id, 2, 1)]
    assert main.JOBS[job.id].status()["reviewed"] == 2
    main.JOBS.clear()


def test_review_and_image_survive_cache_replacement(tmp_path, monkeypatch):
    import asyncio
    from app import main
    from app.storage import job_to_dict, job_from_dict

    job = mk_job(tmp_path, count=1, reviewed=False)
    screenshot = b"real captured image bytes"
    job.captures[0].screenshot = str(job.directory / "r00.jpg")
    job.served_images.add("r00")
    job.captures[0].inspection = {
        "visual_observation": "Specific hierarchy and typography in the screenshot, with clear page-level structure.",
        "product_reason": "The site gives the most important action a distinct visual region and clear context.",
        "transferable_mechanism": "Separate pending decisions from irreversible actions with visibly distinct controls.",
        "motion_observed": False,
    }
    data = job_to_dict(job)
    class Store:
        def load(self, key):
            return job_from_dict(data) if key == job.id else None
        def get_image(self, key, ref):
            return screenshot if key == job.id and ref == "r00" else None
        def save(self, value):
            pass
    monkeypatch.setattr(main, "STORE", Store())
    main.JOBS.clear()
    image = tool("inspect_reference", {"job_id": job.id, "reference_id": "r00"})
    assert image["content"][1]["type"] == "image"
    assert image["content"][1]["mimeType"] == "image/jpeg"
    assert base64.b64decode(image["content"][1]["data"]) == screenshot
    assert main.find_job(job.id).status()["reviewed"] == 1
    main.JOBS.clear()


def test_production_requires_database(monkeypatch):
    from app.storage import get_store
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REQUIRE_DURABLE_STORAGE", "1")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_store()

