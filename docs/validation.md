# Validation

## Standalone publication check — 2026-11-10

| Check | Outcome |
| --- | --- |
| Server and Codex client tests | 26 passed on Python 3.12 |
| Shell syntax | Passed for all four launch/helper scripts |
| Public-source review | No production credentials found in the selected text files; fake test tokens are retained as fixtures |
| Private deployment references | Removed from the public copy; localhost is the default |
| Chromium rendering smoke test | Not completed locally: browser download returned a truncated archive. The GitHub Actions workflow runs this check independently. |
| Live 28-reference research | Not run during this publication pass |
| Real PostgreSQL restart test | Not run; existing restart coverage uses a fake store |

The workflow badge in the README reflects the current GitHub Actions result. It is separate from this dated local check.

## What the tests establish

The server suite covers authentication, selected origin/domain restrictions, initialization, the eight-tool catalog, review gating, image-before-review ordering, board-token access, invalid targets, unknown methods, serialized recovery, and the durable-storage configuration requirement.

The client suite covers a mock MCP handshake, token normalization, rejected credentials, timeouts, sandbox/configuration flags, explicit tool scope, CLI argument order, and research prompt expectations.

Fixtures are synthetic. Passing them does not certify the safety of arbitrary browser content, prove visual understanding, or guarantee a live run can reach its evidence threshold.
