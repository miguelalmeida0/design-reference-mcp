# Contributing

Start with a focused issue describing the user problem and a reproducible example. Keep captured third-party pages, private board links, secrets, and model transcripts out of issues and commits.

## Local checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m playwright install chromium
PYTHONPATH=server python server/tests/chromium-smoke-test.py
```

Keep changes in the module that owns the behavior. Add regression coverage when fixing a behavioral bug; avoid tests that merely repeat implementation details. Document changed tool contracts and failure modes. Never weaken a research gate just to make a live run pass.

The source is public for inspection but does not currently carry an open-source license. Discuss reuse or contributions with the maintainer before relying on broader permissions.
