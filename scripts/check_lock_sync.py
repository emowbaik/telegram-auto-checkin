"""Deterministic CI gate: every locked version must satisfy its declared range.

This does not query PyPI: a new upstream release must not break CI by itself.
Freshness is handled by the weekly lock-refresh workflow.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name
from pip._vendor.packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
LOCK_ENTRY = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", re.MULTILINE)


def declared_requirements(root: Path = ROOT) -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for filename in ("requirements.txt", "requirements-dev.txt"):
        for raw in (root / filename).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "-r", "-e")):
                continue
            requirement = Requirement(line)
            requirements[canonicalize_name(requirement.name)] = requirement
    return requirements


def locked_versions(path: Path) -> dict[str, Version]:
    locked = {}
    for name, version in LOCK_ENTRY.findall(path.read_text(encoding="utf-8")):
        locked[canonicalize_name(name)] = Version(version)
    return locked


def verify(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    requirements = declared_requirements(root)
    locked = locked_versions(root / "requirements.lock")
    for name, requirement in requirements.items():
        if name not in locked:
            errors.append(f"{requirement.name}: missing from requirements.lock")
        elif not requirement.specifier.contains(locked[name], prereleases=True):
            errors.append(
                f"{requirement.name}: locked {locked[name]} violates {requirement.specifier}"
            )
    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("requirements.lock is out of sync:")
        print("\n".join(f"  - {error}" for error in errors))
        return 1
    print(f"lock-sync OK: {len(declared_requirements())} declared constraints satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
