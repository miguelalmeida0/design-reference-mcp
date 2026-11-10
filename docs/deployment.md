# Run and deploy

## Environment

| Variable | Meaning |
| --- | --- |
| `MCP_API_KEY` | Required to authenticate tool requests; generate a random secret |
| `SERVICE_PUBLIC_ORIGIN` | Public HTTPS origin used to generate board URLs |
| `DATABASE_URL` | Dedicated PostgreSQL URL; the store enforces `sslmode=require` |
| `REQUIRE_DURABLE_STORAGE` | Set to `1` in deployments; leave unset locally without a database |
| `RESEARCH_STORAGE` | Temporary local capture directory; defaults to `/tmp/design-references` |
| `PORT` | Docker serving port; defaults to `10000` |
| `REFERENCE_BROWSER_ORIGIN` | Client-side service origin; defaults to localhost |
| `REFERENCE_BROWSER_TOKEN` | Client-side raw bearer token matching `MCP_API_KEY` |

The server reads environment variables directly. It does not automatically source `.env`. Any nonempty `REQUIRE_DURABLE_STORAGE` value requires a database, including `0`. A Render environment also requires it.

## Docker

Build from the repository root:

```bash
docker build -t design-reference-mcp ./server
```

The image uses the Playwright Python base image matching the pinned Python package, runs contract tests in a build stage, and starts one Uvicorn worker as `pwuser`.

Provide `MCP_API_KEY`, `DATABASE_URL`, and `SERVICE_PUBLIC_ORIGIN` securely through your deployment platform or exported environment:

```bash
docker run --rm -p 10000:10000   -e MCP_API_KEY -e DATABASE_URL -e SERVICE_PUBLIC_ORIGIN   design-reference-mcp
```

Terminate HTTPS at your platform proxy. Configure `/healthz` as the liveness path, and set the public origin to the deployed HTTPS URL. This repository does not provision infrastructure or connect to the author's private deployment.

## Operational boundaries

- Deploy one worker/replica; in-memory coordination is not shared across processes.
- Give Chromium enough memory for the reference sites you need. The guard can fail expensive captures; it is not proof that a small instance can complete a full run.
- The database user needs permission to create the two service tables. Use a dedicated database and a minimally scoped account.
- Only two recent jobs are retained in the database. This is a short-lived research workspace, not an archive.
- Health checks indicate that the API responds. They do not verify database writes, Chromium startup, or reference availability.
- Protect the service at the network layer as well as in application code. Review [SECURITY.md](../SECURITY.md).

## Connection check

```bash
export REFERENCE_BROWSER_ORIGIN="https://your-service.example"
# Set REFERENCE_BROWSER_TOKEN through your secret manager or hidden prompt.
bash examples/codex/check-connection.sh
```

The script avoids redirecting authenticated requests and does not print or save the token. A hosted service waking from idle has a longer health-check timeout; authenticated calls keep their shorter timeout.
