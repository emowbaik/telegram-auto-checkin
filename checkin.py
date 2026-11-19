"""Backward-compatible script name; use `main.py --non-interactive` for new jobs."""

from auto_checkin.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--non-interactive"]))
