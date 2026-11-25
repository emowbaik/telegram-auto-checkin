import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_checkin.config import ConfigError, parse_target, parse_targets, read_dotenv, read_settings, validate_proxy
from auto_checkin.telegram import proxy_options

BASE = {"API_ID": "123", "API_HASH": "hash-only-in-tests", "SESSIONS": "session-one"}


def toml(text: str, directory: Path) -> Path:
    path = directory / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


class TargetParsingTests(unittest.TestCase):
    def test_command_can_contain_colons(self):
        target = parse_target("dump:/check in:v2")
        self.assertEqual(target.username, "dump")
        self.assertEqual(target.command, "/check in:v2")

    def test_all_lines_must_be_valid(self):
        with patch.dict(os.environ, {}), self.assertRaisesRegex(ConfigError, "line 2"):
            parse_targets("dump:/checkin\nmissing-separator", "test")

    def test_usernames_are_not_urls(self):
        with self.assertRaises(ConfigError):
            parse_target("https://example.test/dump:/checkin")

    def test_empty_list_fails_closed(self):
        with self.assertRaises(ConfigError):
            parse_targets("", "test")

    def test_phone_numbers_and_numeric_peers_are_rejected(self):
        for value in ("+628123456789:/checkin", "123456789:/checkin"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                parse_target(value)


class SettingsTests(unittest.TestCase):
    def test_configured_targets_without_real_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = toml("[runtime]\nwait_seconds=9\n\n[[targets]]\nusername='dump'\ncommand='/checkin'\n", root)
            with patch.dict(os.environ, BASE, clear=True):
                creds, targets, runtime = read_settings(path)
            self.assertEqual(targets[0].username, "dump")
            self.assertEqual(runtime.wait_seconds, 9)
            self.assertEqual(len(creds.sessions), 1)

    def test_missing_secret_and_invalid_proxy_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = toml(
                "[[targets]]\nusername='dump'\ncommand='/checkin'\n[network]\nenabled=true\nurl=''\n", Path(directory)
            )
            with patch.dict(os.environ, BASE), self.assertRaises(ConfigError):
                read_settings(path)

    def test_dotenv_is_loaded_without_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "export API_ID=321\nAPI_HASH='value with spaces'\nSESSIONS=\"not-evaluated\"\n", encoding="utf-8"
            )
            env = {}
            read_dotenv(path, env)
            self.assertEqual(env["API_ID"], "321")
            self.assertEqual(env["API_HASH"], "value with spaces")


class ProxyTests(unittest.TestCase):
    def test_remote_dns_alias(self):
        options = proxy_options("socks5h://user:pass@example.test:1080")
        self.assertEqual(options["proxy_type"], "socks5")
        self.assertTrue(options["rdns"])

    def test_http_url(self):
        options = proxy_options("http://example.test:8080")
        self.assertEqual(options["proxy_type"], "http")
        self.assertFalse(options["rdns"])

    def test_direct_when_no_proxy(self):
        self.assertIsNone(proxy_options(""))

    def test_non_string_proxy_is_rejected(self):
        with self.assertRaises(ConfigError):
            validate_proxy(123)

    def test_malformed_toml_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = toml("[runtime\nwait_seconds=oops\n", Path(directory))
            with self.assertRaises(ConfigError):
                read_settings(path)


if __name__ == "__main__":
    unittest.main()
