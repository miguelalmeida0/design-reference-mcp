# Research gate handshake

1. `list_reference_sources` displays the saved catalog; **does not** pass any research threshold.
2. `start_reference_research` with `target: 28` returns `job_id` and an actual live research board. The board must visibly populate with captures, not synthetic previews.
3. Poll `get_research_status` until `state: complete`. If fewer than 25 unique captures, report blocked without generating designs.
4. Call `inspect_reference` for EACH screenshot. Review the returned image, then call `record_visual_review` with specific observed layout, why it worked for its original product, and one transferable interaction principle. Do not invent observations.
5. For motion-led work, require verified browser motion measurement and a concrete observed animation. Still screenshots alone do not demonstrate motion quality.
6. `finalize_reference_research(motion_required: true|false)`. The return must include `allow_generation: true` before producing any five-concept design artifacts. If it fails, report the exact missing evidence, not five generic placeholders.
7. Every proposed design must cite at least three distinct **reviewed** screenshot IDs, not mere URLs.

The server implements a stateless JSON-RPC MCP HTTP subset for one trusted operator, with no dynamic OAuth flow. Captures target the public reference catalog. Evidence is durable when PostgreSQL is configured; ephemeral local development loses job metadata on restart. See [architecture](architecture.md) and [limitations](limitations.md).

