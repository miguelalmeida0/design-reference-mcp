# MCP tool reference

Send JSON-RPC requests to `POST /mcp` with `Authorization: Bearer <token>`, `Content-Type: application/json`, and an MCP-capable client that can display image content. The server advertises eight tools.

## Start research

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "start_reference_research",
    "arguments": {
      "brief": "Research calm mobile reading interfaces with clear hierarchy and compact controls.",
      "target": 28
    }
  }
}
```

The result contains `job_id`, `state`, and `board_url`. The brief must have 10–1,000 characters. The target must be an integer from 25 to 30; default 28. A second active job is refused.

## Arguments

| Tool | Arguments | Result |
| --- | --- | --- |
| `list_reference_sources` | None | Seed count and source records |
| `start_reference_research` | `brief`; optional `target` | Job ID, state, board URL |
| `get_research_status` | `job_id` | Capture/review counts, captures, recent attempts |
| `inspect_reference` | `job_id`, `reference_id` | Metadata text and actual base64 image content |
| `record_visual_review` | `job_id`, `reference_id`, `visual_observation`, `product_reason`, `transferable_mechanism`; optional `motion_observed` | Saved-review acknowledgment |
| `finalize_reference_research` | `job_id`; optional `motion_required` | Allow/deny decision and reasons |
| `get_research_board` | `job_id` | Read-only board URL |
| `get_research_report` | `job_id`; optional `motion_required` | Evidence manifest and gate results |

`motion_required` defaults to `true`; explicitly set it to `false` for static-layout research. `motion_observed` defaults to `false`. Each review text field must contain 45–1,800 characters, and the image must have been served first. A finalized report rejects further reviews.

## Client sequence

1. Discover sources and start one job.
2. Poll status and retain blocked-attempt reasons.
3. Retrieve each eligible screenshot with `inspect_reference`.
4. Inspect the returned image before writing the review. Reject login walls, placeholders, and irrelevant captures.
5. Finalize with an explicit motion requirement.
6. Report either the evidence or the exact blocking reasons. Never fabricate observations to meet counts.

Tool failures generally use a successful JSON-RPC envelope with `isError: true` in its result. Unknown methods/tools use JSON-RPC error objects. Clients must inspect both levels; HTTP 200 alone is not tool success.
