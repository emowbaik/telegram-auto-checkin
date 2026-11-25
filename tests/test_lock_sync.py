import tempfile
import unittest
from pathlib import Path

from scripts.check_lock_sync import verify


class LockSyncTests(unittest.TestCase):
    def build(self, root: Path, runtime: str, dev: str, lock: str) -> None:
        (root / "requirements.txt").write_text(runtime, encoding="utf-8")
        (root / "requirements-dev.txt").write_text("-r requirements.txt\n" + dev, encoding="utf-8")
        (root / "requirements.lock").write_text(lock, encoding="utf-8")

    def test_satisfied_constraints_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build(
                root,
                "demo>=1,<3\n",
                "lint>=2,<4\n",
                "demo==2.1 \\\n    --hash=sha256:abc\nlint==3.0 \\\n    --hash=sha256:def\n",
            )
            self.assertEqual(verify(root), [])

    def test_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build(root, "demo>=3,<4\n", "", "demo==2.1 \\\n    --hash=sha256:abc\n")
            self.assertTrue(any("violates" in error for error in verify(root)))

    def test_missing_pin_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build(root, "demo>=1,<3\n", "", "# empty\n")
            self.assertTrue(any("missing" in error for error in verify(root)))


if __name__ == "__main__":
    unittest.main()
