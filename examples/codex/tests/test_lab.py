"""Offline stdlib-only tests for the Codex browser test project."""
from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import mcp_smoke  # noqa: E402


class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return
        self.send_json({"status": "ok", "service": "design-reference-browser", "browser": "chromium"})

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer test-secret":
            self.send_response(401)
            self.end_headers()
            return
        size = int(self.headers.get("Content-Length", "0"))
        packet = json.loads(self.rfile.read(size))
        method = packet.get("method")
        if method == "initialize":
            payload = {"serverInfo": {"name": "design-reference-browser"}, "protocolVersion": "2025-06-18"}
        elif method == "tools/list":
            payload = {"tools": [{"name": name} for name in sorted(mcp_smoke.REQUIRED_TOOLS)]}
        elif method == "tools/call":
            payload = {"isError": False, "structuredContent": {"sources": [{"name": "Design Everywhere", "url": "https://designeverywhere.co/"}]}}
        else:
            payload = {}
        self.send_json({"jsonrpc": "2.0", "id": packet.get("id"), "result": payload})

    def send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_mcp_full_handshake(self):
        result = mcp_smoke.smoke(self.origin, "test-secret")
        self.assertEqual(result["tool_count"], 8)
        self.assertEqual(result["reference_sources"], 1)

    def test_health_check_allows_free_render_cold_start(self):
        # Render Free wakes after idling; a 45-second health timeout is shorter
        # than its documented approximately one-minute cold start.
        original = mcp_smoke.request_json
        with patch.object(mcp_smoke, "request_json", wraps=original) as request:
            result = mcp_smoke.smoke(self.origin, "test-secret")
        self.assertEqual(result["tool_count"], 8)
        first = request.call_args_list[0]
        self.assertTrue(first.args[0].endswith("/healthz"))
        self.assertGreaterEqual(first.kwargs.get("timeout", 0), 120)

    def test_auth_rejected(self):
        with self.assertRaisesRegex(mcp_smoke.ConnectionFailure, "HTTP 401"):
            mcp_smoke.smoke(self.origin, "wrong-secret")

    def test_prefix_trimmed(self):
        self.assertEqual(mcp_smoke.normalize_token("Bearer test-secret"), "test-secret")
        self.assertEqual(mcp_smoke.normalize_token("test-secret"), "test-secret")

    def test_empty_token_rejected(self):
        with self.assertRaises(mcp_smoke.ConnectionFailure):
            mcp_smoke.normalize_token("   ")

    def test_reject_embedded_whitespace(self):
        with self.assertRaises(mcp_smoke.ConnectionFailure):
            mcp_smoke.normalize_token("Bearer bad secret")

    def test_project_toml_and_flags(self):
        import tomllib
        config = tomllib.loads((ROOT / ".codex/config.toml").read_text())
        server = config["mcp_servers"]["reference_browser"]
        self.assertEqual(server["bearer_token_env_var"], "REFERENCE_BROWSER_TOKEN")
        self.assertTrue(server["required"])
        self.assertEqual(config["approval_policy"], "never")
        self.assertEqual(config["sandbox_mode"], "workspace-write")
        self.assertFalse(config["sandbox_workspace_write"]["network_access"])
        common = (ROOT / "scripts/common.sh").read_text()
        self.assertIn("--ask-for-approval never", common)
        self.assertIn("--sandbox workspace-write", common)


    def test_exec_places_global_approval_flag_before_subcommand(self):
        # CLI --ask-for-approval is a top-level argument; placing it after
        # 'exec' causes an immediate parser failure on current Codex versions.
        script = (ROOT / "test-research.sh").read_text()
        self.assertIn('exec codex "${CODEX_FLAGS[@]}" exec ', script)
        self.assertNotIn('exec codex exec "${CODEX_FLAGS[@]}"', script)

    def test_research_mcp_has_explicit_no_prompt_approval_and_allowlist(self):
        """No-approval exec must not leave unannotated MCP tools in auto mode."""
        import tomllib
        cfg = tomllib.loads((ROOT / ".codex/config.toml").read_text())
        server = cfg["mcp_servers"]["reference_browser"]
        self.assertEqual(server["default_tools_approval_mode"], "approve")
        self.assertEqual(set(server["enabled_tools"]), mcp_smoke.REQUIRED_TOOLS)
        shell = (ROOT / "scripts/common.sh").read_text()
        self.assertIn('mcp_servers.reference_browser.default_tools_approval_mode="approve"', shell)
        self.assertIn('mcp_servers.reference_browser.enabled_tools=', shell)
        for name in mcp_smoke.REQUIRED_TOOLS:
            self.assertIn(name, shell)
        self.assertIn("--sandbox workspace-write", shell)
        self.assertIn("--ask-for-approval never", shell)

    def test_no_persistent_secrets(self):
        # The project must not contain credentials, even in config files.
        self.assertFalse((ROOT / ".env").exists())
        self.assertFalse((ROOT / ".token").exists())
        config_text = (ROOT / ".codex/config.toml").read_text()
        self.assertNotIn("http_headers", config_text)
        self.assertIn('bearer_token_env_var = "REFERENCE_BROWSER_TOKEN"', config_text)
        self.assertIn(".env", (ROOT / ".gitignore").read_text())
        self.assertIn("read -r -s", (ROOT / "scripts/common.sh").read_text())

    def test_required_tool_names(self):
        instructions = (ROOT / "AGENTS.md").read_text()
        for tool in mcp_smoke.REQUIRED_TOOLS:
            self.assertIn(tool, instructions)

    def test_research_gate_instructions(self):
        instructions = (ROOT / "prompts/02-live-research.md").read_text()
        self.assertIn("finalize_reference_research", instructions)
        self.assertIn("Do not produce any of the five designs", instructions)
        self.assertIn("28", instructions)


if __name__ == "__main__":
    unittest.main()
