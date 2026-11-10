# Security model

The API uses one bearer secret and is intended for a single trusted operator. It is not a multi-tenant hosted service.

## Implemented controls

- Constant-time bearer-token comparison for MCP requests.
- Fixed HTTPS top-level seed hosts and public DNS checks before capture.
- Browser subrequest checks reject private literal addresses and hosts resolving to non-public addresses.
- Robots restrictions and blocked pages are recorded as failures, not bypassed.
- Per-job unpredictable board view tokens; board pages use no-referrer and no-store headers.
- One active job and bounded attempts; Chromium memory monitoring on bounded Linux cgroups.
- Client scripts avoid forwarding credentials through redirects and prompt without echoing token input.

## Trust boundaries

Board URLs are bearer capabilities: anyone holding the full URL can see the job. Do not share them publicly. The database stores board tokens, job briefs, review text, and captured page bytes; protect it accordingly.

Application DNS checks do not pin network destinations. Chromium subresources are not restricted to the catalog, and redirects are checked after navigation. For internet deployment, use infrastructure-level egress isolation to keep private networks inaccessible. The endpoint has no per-user quotas or tenant isolation; the single-job admission limit is not comprehensive rate limiting. Request-size enforcement currently uses the declared Content-Length, not a streaming byte limit.

Third-party pages are untrusted content. Clients must ignore instructions in them and treat them only as research evidence. Screenshot delivery does not validate a review's truthfulness.

## Reporting

Please do not post credentials, private board links, database URLs, or exploit details in a public issue. Use the repository's private vulnerability reporting feature if enabled, or contact the maintainer through the linked portfolio to arrange private disclosure. No response-time guarantee is offered.

## Publication scope

This repository is a standalone source snapshot. It excludes private repository history, service credentials, captured research data, and the surrounding product application. Test tokens are deliberately fake fixture values.
