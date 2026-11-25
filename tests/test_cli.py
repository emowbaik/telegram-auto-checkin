import types
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_checkin.config import Credentials, Runtime, Target
from auto_checkin.results import Result
from auto_checkin.runner import totals


def args(strict=False):
    return types.SimpleNamespace(strict=strict, config=Path("config.toml"))


class ExitPolicyTests(unittest.TestCase):
    def setUp(self):
        self.credentials = Credentials(123, "hash", ("account-1", "account-2"))
        self.targets = [Target("dump", "/checkin"), Target("checker", "/start")]
        self.runtime = Runtime(wait_seconds=0, account_delay_seconds=0)

    def evaluate(self, results, strict=False):
        with (
            patch("auto_checkin.cli.read_settings", return_value=(self.credentials, self.targets, self.runtime)),
            patch("auto_checkin.cli.asyncio.run", return_value=results),
            patch("auto_checkin.cli.Notifier"),
        ):
            from auto_checkin.cli import run_once

            return run_once(args(strict=strict))

    def test_full_coverage_returns_zero(self):
        results = [Result("@a", "dump", "success"), Result("@a", "checker", "success")]
        results += [Result("@b", "dump", "success"), Result("@b", "checker", "success")]
        self.assertEqual(self.evaluate(results), 0)

    def test_one_failed_target_fails_the_run(self):
        results = [Result("@a", "dump", "success"), Result("@a", "checker", "success")]
        results += [Result("@b", "dump", "success"), Result("@b", "checker", "no_reply")]
        self.assertEqual(totals(results, 2).sent, 3)
        self.assertEqual(self.evaluate(results), 1)

    def test_strict_mode_also_fails_on_any_error(self):
        results = [Result("@a", "dump", "success"), Result("@a", "checker", "success")]
        results += [Result("@b", "dump", "success"), Result("@b", "checker", "no_reply")]
        self.assertEqual(self.evaluate(results, strict=True), 1)


if __name__ == "__main__":
    unittest.main()
