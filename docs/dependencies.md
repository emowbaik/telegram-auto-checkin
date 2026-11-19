# Dependency management

There are three intentionally small requirement layers:

- `requirements.txt`: direct runtime requirements.
- `requirements-dev.txt`: runtime plus local/CI style checks.
- `requirements.lock`: the exact resolved set, with per-artefact SHA-256 hashes, for the CI runner (Linux x86_64 / CPython 3.11).

The lock prevents a newly published transitive package from changing a production install unexpectedly; it does not prevent a vulnerability from being found later, so the dependency-audit job remains a separate check.

## Update

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/lock_dependencies.py
pip install --require-hashes -r requirements.lock
python -m unittest discover -s tests -v
python -m ruff check auto_checkin tests main.py checkin.py
```

`scripts/lock_dependencies.py` performs one platform-neutral resolution first (including source-only packages), then resolves a matching x86_64/CPython 3.11 artefact per exact package version. Never generate lock hashes with a local interpreter's preferred architecture. A bad hash must be treated as an update defect, not something to bypass.

Run a real GitHub check-in after significant dependency bumps (`Telethon`, `python-socks`, or job startup changes); mocked tests cannot prove account authorization or bot replies.
