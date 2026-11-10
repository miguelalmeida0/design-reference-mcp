# Architecture

## Responsibilities

| Module | Owns |
| --- | --- |
| `main.py` | FastAPI routes, bearer authentication, tool dispatch, job orchestration |
| `browsing.py` | Capture queue, robots checks, public-host checks, image capture, discovery |
| `catalog.py` | Curated seeds and fixed HTTPS host allowlist |
| `memory_budget.py` | Container memory monitoring and Chromium-child termination |
| `models.py` | Job and capture records |
| `validation.py` | Structural review gate |
| `storage.py` | PostgreSQL snapshots, image bytes, retention, and recovery |
| `board.py` | Read-only HTML research board |
| `report.py` | Structured evidence report |
| `security.py` | URL and public DNS checks |

## Capture and recovery

One research job runs at a time. The queue begins with project/specific sources, then galleries and archives. Gallery discovery stays on the same allowed host, uses URL heuristics, and adds at most 20 candidates per visited source. The run stops at its capture target, an empty queue, or 95 attempted pages.

Each page uses a fresh Chromium process. Before capture, the URL is marked as seen and checkpointed. With PostgreSQL enabled, a restarted job skips an interrupted in-flight URL and records it as blocked instead of repeatedly loading a page that may have crashed Chromium. Image bytes and job metadata are separate writes; this is checkpoint recovery, not an exactly-once transaction across the whole browser operation.

The memory guard polls bounded Linux cgroup usage. At the lower of 75% of the container limit or the limit minus 128 MiB, it terminates Chromium descendants. It does not provide a hard memory guarantee: spikes between polls and unbounded environments remain possible. The capture records a failure and the queue can continue.

## Evidence and trust

`inspect_reference` marks an image as served. `record_visual_review` requires that mark, three fields of 45–1,800 characters, and a supported motion flag. Finalization validates records, uniqueness, counts, completion, and freshness. It cannot determine whether the client truly looked at the image or whether the prose is accurate.

Boards use independent unpredictable view tokens in the URL. Anyone with a complete board URL can read that job. Keep those URLs out of public issues and CVs.

## Persistence

Production uses PostgreSQL with TLS required. `reference_jobs` stores snapshots; `reference_images` stores image bytes with cascade deletion. The service retains up to two job snapshots under its single-process usage model. Ephemeral local mode keeps jobs in memory and screenshots on disk; it is not durable and does not provide a disk-retention guarantee.

Use one Uvicorn worker. Locks, admission control, and the job cache are process-local. Multi-worker and multi-replica operation need a shared queue and distributed coordination before they are supported.

## Protocol

The service implements a small stateless JSON-RPC MCP HTTP subset, advertising protocol version `2025-06-18`. There is no SSE stream, OAuth flow, multi-user tenancy, session negotiation, or general-purpose browser control. See [protocol details](protocol.md).
