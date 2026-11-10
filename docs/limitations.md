# Known limits

This is an early-stage, single-operator research tool. These are properties of the current code, not promises of future behavior.

| Area | Current boundary |
| --- | --- |
| Visual understanding | The server knows that it served an image, not that a model understood it. Review text is length-validated, not semantically graded. |
| Research diversity | The gate counts distinct source IDs. Related seeds from the same publisher can count separately. |
| Individual works | Project categories include manually classified seeds and URL-based discovery heuristics. They are not independently verified works. |
| Motion | A hover probe counts running animations. The saved artifact is a static screenshot with animations disabled; there is no video or full interaction trace. |
| Completion | A capture job may finish with fewer than 25 usable references. Completed capture does not imply a passing gate. |
| Live sites | Robots restrictions, timeouts, authentication walls, scripts, and page memory can reduce coverage. |
| Memory | Per-page browser processes and cgroup monitoring reduce exposure but do not guarantee freedom from OOM termination. |
| Recovery | A checkpointed in-flight URL is skipped after restart. Image persistence and snapshot updates are not one atomic operation. |
| Retention | Database history is bounded to two jobs. Ephemeral development files are not a durable archive and may accumulate. |
| Network isolation | Public DNS checks are application-level defenses, not DNS pinning or a network sandbox. Browser subresources can use public hosts outside the seed catalog. |
| Input robustness | The MCP subset is deliberately small. Some malformed JSON-RPC shapes may cause server errors; not every schema constraint is centrally enforced. |
| Scaling | One process and one active job. No tenant isolation, distributed locks, or durable worker queue. |
| Testing | Contract/recovery fixtures do not prove real database behavior or a successful live research run. |

## Next engineering work

- Capture a reproducible live-run receipt with actual screenshot review and blocked-source reporting.
- Exercise real PostgreSQL persistence, pruning, and restart recovery in integration tests.
- Normalize source families and verify project eligibility more reliably.
- Add inspectable motion sequences and stronger review-quality checks.
- Harden malformed-request handling, enforce streamed body limits, and test network-boundary edge cases.
