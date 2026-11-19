import unittest

from auto_checkin.results import Result, build_report, compact_reply
from auto_checkin.runner import totals


class ResultTests(unittest.TestCase):
    def test_html_never_injects_tags(self):
        report = build_report(
            [
                Result("<account>", "<bot>", "error", "<detail>"),
            ],
            "2026-01-01 <bang>",
        )
        self.assertIn("&lt;account&gt;", report)
        self.assertIn("&lt;bot&gt;", report)
        self.assertNotIn("<account>", report)
        self.assertNotIn("<detail>", report)

    def test_success_marker_and_long_reply(self):
        reply = compact_reply("ok " * 900, 700)
        self.assertEqual(len(reply), 700)
        self.assertTrue(reply.endswith("…"))
        totals_ = totals([Result("acc", "dump", "success")], 3)
        self.assertEqual(totals_.sent, 1)
        self.assertEqual(totals_.accounts, 3)


if __name__ == "__main__":
    unittest.main()
