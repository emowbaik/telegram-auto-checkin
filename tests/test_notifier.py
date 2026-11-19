import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from auto_checkin.notifier import Notifier


class NotifierTests(unittest.TestCase):
    def test_disabled_without_credentials(self):
        with patch("urllib.request.urlopen") as request:
            self.assertFalse(Notifier().send("report"))
        request.assert_not_called()

    def test_success_payload(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response) as request:
            self.assertTrue(Notifier("fake-token-for-unit-test", "12345").send("report"))
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body["chat_id"], "12345")
        self.assertEqual(body["parse_mode"], "HTML")

    def test_network_exception_is_not_fatal(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            self.assertFalse(Notifier("fake-token-for-unit-test", "12345").send("report"))


if __name__ == "__main__":
    unittest.main()
