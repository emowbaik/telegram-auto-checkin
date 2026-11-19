import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_checkin.config import Credentials, Runtime, Target
from auto_checkin.runner import CheckinRunner
from auto_checkin.telegram import TelegramConnection


class FloodWaitError(Exception):
    seconds = 3


class Connection:
    def __init__(self, session, api_id, api_hash, proxy=None, session_directory=None):
        self.session = session
        self.proxy = proxy

    async def __aenter__(self):
        if self.session == "connection-fails":
            raise ConnectionError("offline (synthetic test)")
        return self

    async def __aexit__(self, *args):
        return None

    async def is_user_authorized(self):
        return self.session != "expired"

    async def get_identity(self):
        return "user"

    async def send_and_read(self, username, command):
        return None

    async def latest_message(self, username):
        if username == "FloodWaitError":
            raise FloodWaitError()
        return "done"


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dead_account_does_not_stop_the_next(self):
        credentials = Credentials(123, "hash", ("expired", "good"))
        result = await CheckinRunner(
            credentials,
            [Target("dump", "/checkin")],
            Runtime(wait_seconds=0, account_delay_seconds=0, notify_timeout_seconds=0),
            connection_factory=Connection,
            log=lambda _: None,
        ).run()
        self.assertEqual(result[0].status, "session_invalid")
        self.assertEqual(result[1].status, "success")

    async def test_failed_connection_is_isolated(self):
        credentials = Credentials(123, "hash", ("connection-fails", "good"))
        result = await CheckinRunner(
            credentials,
            [Target("dump", "/checkin")],
            Runtime(wait_seconds=0, account_delay_seconds=0, notify_timeout_seconds=0),
            connection_factory=Connection,
            log=lambda _: None,
        ).run()
        self.assertEqual(result[0].status, "connection_error")
        self.assertEqual(result[1].status, "success")

    async def test_flood_wait_records_the_wait(self):
        credentials = Credentials(123, "hash", ("good",))
        result = await CheckinRunner(
            credentials,
            [Target("FloodWaitError", "/checkin")],
            Runtime(wait_seconds=0, account_delay_seconds=0, notify_timeout_seconds=0),
            connection_factory=Connection,
            log=lambda _: None,
        ).run()
        self.assertEqual(result[0].status, "flood_wait_3s")

    async def test_two_sends_are_not_collapsed(self):
        credentials = Credentials(123, "hash", ("one", "two"))
        result = await CheckinRunner(
            credentials,
            [Target("dump", "/checkin")],
            Runtime(wait_seconds=0, account_delay_seconds=0, notify_timeout_seconds=0),
            connection_factory=Connection,
            log=lambda _: None,
        ).run()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item.ok for item in result))


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_cleanup_and_session_persistence(self):
        telethon = types.ModuleType("telethon")
        sessions = types.ModuleType("telethon.sessions")

        class StringSession:
            def __init__(self, text):
                self.text = text

        class Save:
            def save(self):
                return "rotated-session"

        class Message:
            text = "reply"

        class User:
            username = "unit_test"
            id = 1
            first_name = "test"

        class Client:
            def __init__(self, *args, **kwargs):
                self.session = Save()

            async def connect(self):
                return True

            async def disconnect(self):
                return True

            async def is_user_authorized(self):
                return True

            async def get_me(self):
                return User()

            async def send_message(self, username, command):
                return Message()

            async def get_messages(self, username, limit=1):
                return [Message()]

        setattr(telethon, "TelegramClient", Client)  # noqa: B010
        setattr(sessions, "StringSession", StringSession)  # noqa: B010
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"telethon": telethon, "telethon.sessions": sessions}):
                async with TelegramConnection(
                    "initial-session", 123, "hash", session_directory=Path(directory)
                ) as client:
                    self.assertEqual(await client.get_identity(), "@unit_test")
            saved = Path(directory) / "telegram-session.txt"
            self.assertEqual(saved.read_text(encoding="utf-8").strip(), "rotated-session")


if __name__ == "__main__":
    unittest.main()
