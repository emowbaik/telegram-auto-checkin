import stat
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_checkin.config import Credentials, Runtime, Target
from auto_checkin.runner import CheckinRunner, totals
from auto_checkin.telegram import TelegramConnection, make_session_storage


class FloodWaitError(Exception):
    seconds = 3


class Connection:
    def __init__(self, session, api_id, api_hash, proxy=None, session_directory=None):
        self.session = session

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

    async def send_and_wait_reply(self, username, command, delay=0):
        if username == "FloodWaitError":
            raise FloodWaitError()
        if username == "no_reply":
            return 7, None
        return 7, "done"


def run(credentials, targets, connection=Connection):
    return CheckinRunner(
        credentials,
        targets,
        Runtime(wait_seconds=0, account_delay_seconds=0, notify_timeout_seconds=0),
        connection_factory=connection,
        log=lambda _: None,
    ).run()


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dead_account_does_not_stop_the_next(self):
        result = await run(Credentials(123, "hash", ("expired", "good")), [Target("dump", "/checkin")])
        self.assertEqual(result[0].status, "session_invalid")
        self.assertEqual(result[1].status, "success")

    async def test_failed_connection_is_isolated(self):
        result = await run(Credentials(123, "hash", ("connection-fails", "good")), [Target("dump", "/checkin")])
        self.assertEqual(result[0].status, "connection_error")
        self.assertEqual(result[1].status, "success")

    async def test_flood_wait_records_the_wait(self):
        result = await run(Credentials(123, "hash", ("good",)), [Target("FloodWaitError", "/checkin")])
        self.assertEqual(result[0].status, "flood_wait_3s")

    async def test_two_sends_are_not_collapsed(self):
        result = await run(Credentials(123, "hash", ("one", "two")), [Target("dump", "/checkin")])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item.ok for item in result))

    async def test_missing_reply_is_not_counted_as_success(self):
        result = await run(Credentials(123, "hash", ("good",)), [Target("no_reply", "/checkin")])
        self.assertEqual(result[0].status, "no_reply")
        self.assertFalse(result[0].ok)
        self.assertEqual(totals(result, 1).failed, 1)


class SessionStorageTests(unittest.TestCase):
    def test_sessions_are_owner_only_and_backup_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = make_session_storage("dummy-one", root)
            self.assertEqual(stat.S_IMODE(current.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            previous = root / "telegram-session.previous.txt"
            make_session_storage("dummy-two", root)
            self.assertEqual(previous.read_text(encoding="utf-8").strip(), "dummy-one")
            make_session_storage("dummy-two", root)
            self.assertEqual(previous.read_text(encoding="utf-8").strip(), "dummy-one")


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_a_new_incoming_reply_from_the_bot_is_accepted(self):
        telethon = types.ModuleType("telethon")
        sessions = types.ModuleType("telethon.sessions")
        api = types.SimpleNamespace(id=101)

        class StringSession:
            def __init__(self, text):
                self.text = text

        class Save:
            def save(self):
                return "rotated-session"

        class Message:
            def __init__(self, id, out, sender_id, text):
                self.id = id
                self.out = out
                self.sender_id = sender_id
                self.text = text

        class User:
            username = "unit_test"
            id = 101
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

            async def get_entity(self, username):
                return api

            async def send_message(self, username, command):
                return Message(100, True, 101, command)

            async def iter_messages(self, entity, min_id=0, limit=10):
                yield Message(100, True, 101, "own command")
                yield Message(99, False, 101, "stale reply")
                yield Message(101, False, 999, "someone else")
                yield Message(102, False, 101, "verified reply")

        setattr(telethon, "TelegramClient", Client)  # noqa: B010
        setattr(sessions, "StringSession", StringSession)  # noqa: B010
        with patch.dict("sys.modules", {"telethon": telethon, "telethon.sessions": sessions}):
            async with TelegramConnection("initial-session", 123, "hash") as client:
                self.assertEqual(await client.get_identity(), "@unit_test")
                sent_id, reply = await client.send_and_wait_reply("dump", "/checkin")
                self.assertEqual(sent_id, 100)
                self.assertEqual(reply, "verified reply")


if __name__ == "__main__":
    unittest.main()
