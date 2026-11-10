#!/usr/bin/env python3
"""Verify the deployed Design References MCP service without starting research.

Only Python's standard library is used; no secret is logged or saved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_ORIGIN = os.environ.get("REFERENCE_BROWSER_ORIGIN", "http://127.0.0.1:8000")
REQUIRED_TOOLS = frozenset({
    "list_reference_sources",
    "start_reference_research",
    "get_research_status",
    "inspect_reference",
    "record_visual_review",
    "finalize_reference_research",
    "get_research_board",
    "get_research_report",
})


class ConnectionFailure(RuntimeError):
    """A trustworthy failure message with no credential material."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectionFailure("Unexpected redirect; refusing to forward credentials")


OPENER = urllib.request.build_opener(NoRedirect())


def normalize_token(text: str) -> str:
    """Accept an Authorization header value or a raw bearer token."""
    value = text.strip()
    if value.startswith("Bearer "):
        value = value.removeprefix("Bearer ")
    if not value or any(ch.isspace() for ch in value):
        raise ConnectionFailure("Invalid MCP token. Use a single raw token value.")
    return value


def request_json(url: str, *, token: str | None = None, payload: dict | None = None, timeout: int = 45) -> dict[str, Any]:
    headers = {"User-Agent": "DesignReferencesCodexLab/1.0", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + normalize_token(token)
        headers["MCP-Protocol-Version"] = "2025-06-18"
    encoded = None
    if payload is not None:
        encoded = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=encoded, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with OPENER.open(req, timeout=timeout) as response:
            if response.status != 200:
                raise ConnectionFailure(f"Unexpected HTTP {response.status}")
            body = response.read(2_000_000)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ConnectionFailure(f"HTTP {exc.code}: MCP authentication rejected. Check the server MCP_API_KEY.") from None
        raise ConnectionFailure(f"HTTP {exc.code}: server rejected request") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionFailure(f"MCP network connection failed ({type(exc).__name__}). Check the service origin and deployment.") from None
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ConnectionFailure("Endpoint returned non-JSON content; check its URL.") from None
    if not isinstance(obj, dict):
        raise ConnectionFailure("Endpoint returned an invalid JSON object.")
    return obj


def rpc(origin: str, token: str, method: str, params: dict | None = None, rpc_id: int = 1) -> dict:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        payload["params"] = params
    result = request_json(origin.rstrip("/") + "/mcp", token=token, payload=payload)
    if result.get("error"):
        message = str(result.get("error", {}).get("message", "unknown JSON-RPC error"))
        raise ConnectionFailure("MCP " + method + " returned error: " + message[:160])
    if result.get("jsonrpc") != "2.0" or "result" not in result:
        raise ConnectionFailure("Invalid MCP response for " + method)
    return result["result"]


def smoke(origin: str, token: str) -> dict[str, Any]:
    # Render Free can cold-start for approximately a minute after going idle.
    # Allow the public, unauthenticated health check to wake the service before
    # attempting any authenticated MCP calls (which keep their shorter timeout).
    health = request_json(origin.rstrip("/") + "/healthz", timeout=150)
    if health.get("status") != "ok" or health.get("service") != "design-reference-browser":
        raise ConnectionFailure("Health response is not the expected browser MCP service")
    initial = rpc(origin, token, "initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "reference-browser-codex-lab", "version": "1.0.0"},
    })
    if not initial.get("serverInfo", {}).get("name") == "design-reference-browser":
        raise ConnectionFailure("MCP initialize server identity mismatch")
    catalogue = rpc(origin, token, "tools/list")
    exposed = {tool.get("name") for tool in catalogue.get("tools", []) if isinstance(tool, dict)}
    missing = REQUIRED_TOOLS - exposed
    if missing:
        raise ConnectionFailure("Missing required MCP tools: " + ", ".join(sorted(missing)))
    call = rpc(origin, token, "tools/call", {"name": "list_reference_sources", "arguments": {}})
    if call.get("isError"):
        raise ConnectionFailure("MCP list_reference_sources returned a tool error")
    data = call.get("structuredContent")
    if not isinstance(data, dict):
        try:
            data = json.loads(call["content"][0]["text"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise ConnectionFailure("MCP source list result has no readable data") from None
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ConnectionFailure("Browser MCP listed no saved reference sources")
    return {
        "service": health["service"],
        "mcp_version": initial.get("protocolVersion"),
        "tool_count": len(exposed),
        "reference_sources": len(sources),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="MCP service origin (default: REFERENCE_BROWSER_ORIGIN or localhost)")
    parser.add_argument("--quiet", action="store_true", help="Compact output")
    args = parser.parse_args(argv)
    try:
        token = normalize_token(os.environ.get("REFERENCE_BROWSER_TOKEN", ""))
        result = smoke(args.origin, token)
    except ConnectionFailure as exc:
        print("MCP CHECK FAILED: " + str(exc), file=sys.stderr)
        return 1
    print(f"MCP OK · {result['tool_count']} tools · {result['reference_sources']} sources")
    if not args.quiet:
        print("Authenticated initialization, tools/list and list_reference_sources succeeded. No browsing job started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
