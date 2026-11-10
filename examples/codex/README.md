# Codex client example

An optional client harness for an image-capable Codex CLI. It performs a connection check before starting interactive or scripted research. Python 3.12+, the Codex CLI, and a running server are required.

```bash
export REFERENCE_BROWSER_ORIGIN="http://127.0.0.1:8000"
# Supply REFERENCE_BROWSER_TOKEN securely, or use the scripts' hidden prompt.
bash examples/codex/check-connection.sh
bash examples/codex/start.sh
# Or run the included 28-reference research prompt:
bash examples/codex/test-research.sh
```

All commands above run from the repository root. Scripts switch into this example's directory themselves. Set the origin to your own HTTPS deployment for remote use. Never use another operator's service without authorization.

The launch scripts pass project-scoped MCP configuration explicitly. They keep `workspace-write` sandboxing and shell network access disabled. The eight named research tools are explicitly approved for unattended operation; review that list and the server you are trusting before running. The server itself performs the constrained browsing. Normal Codex authentication and model usage costs apply.

`.codex/config.toml` is a localhost template for launching Codex manually from this directory. The launch scripts override the URL from `REFERENCE_BROWSER_ORIGIN`; direct Codex launches do not substitute that variable in the template.

| File | Purpose |
| --- | --- |
| `check-connection.sh` | Health, authenticated initialization, tools, and source discovery |
| `start.sh` | Interactive Codex session |
| `test-research.sh` | Scripted research prompt |
| `scripts/mcp_smoke.py` | Standard-library-only connection checker |
| `prompts/` | Connection and research prompts |
| `AGENTS.md` | Research evidence rules |
| `tests/` | Mock-server, authentication, configuration, and CLI argument checks |

The report output directory is ignored by Git because reports may contain private board links. A passing connection check is not a passing research run.
