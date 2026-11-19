# Architecture

## Data flow

```text
config.toml + BOTS + .env/environment
                 │
                 ▼
        cli.py — validation + run mode
                 │
                 ▼
        runner.py — sequential per-account loop
                 │
                 ▼
        telegram.py — Telethon connect / send / read
                 │
                 ▼
        results.py — typed outcomes, HTML-safe summary
                 │
                 ▼
        notifier.py — optional one-shot Bot API report
```

The orchestrator calls accounts **serially**. An invalid session or a network failure is recorded and the next account continues. Target failures (including flood-wait) do not kill the remaining targets. An operator cancellation propagates.

## Configuration boundaries

- **Public defaults** live in `config.toml`; only the neutral placeholder `dump` appears in examples.
- **Private credentials** come from environment variables, in particular `API_ID`, `API_HASH`, `SESSIONS`, and optional notification fields.
- `BOTS`, when non-empty, takes precedence over all configured targets. Every line is validated; no malformed line is silently discarded.
- Proxy use is opt-in. `network.enabled=false` leaves DNS, IP selection and egress entirely to the host. An enabled proxy passes explicitly to Telethon, not globally to unrelated processes.

## Client boundary

`telegram.py` isolates all Telethon imports. Unit tests use an in-memory fake context, so no external calls and no real API credentials are necessary. This also means session-validation behavior is testable without leaking a user's identity.

The adapter handles session backup after a refresh, keeping the rotated session in the user's home data directory. Disconnect or backup failures cannot replace the real per-account error.

## Exit semantics

- `0` for `auto-checkin` means at least one command succeeded.
- `1` means no target succeeded, or (with `--strict`) at least one target failed.
- `2` means a local configuration or required-secret error.
- `130` is a user interrupt.

Report status is deliberately distinct: disabled/unavailable Bot API reporting does not change whether the actual check-in commands succeeded.

## CI separation

`ci.yml` runs only mocked unit tests, syntax/style checks, and package dependency audits. It does not receive user-session secrets. `checkin.yml` contains the scheduled job and its explicit required-secret gate, concurrency, heartbeat and log pruning. Do not add the daily checkout to the test-only jobs to avoid exposing production credentials unnecessarily.
