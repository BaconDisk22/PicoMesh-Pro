"""Static regression checks for UART timeout and message polling paths."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class TimeoutSafetyTests(unittest.TestCase):
    def test_frame_read_has_timeout_checks(self):
        start = SOURCE.index("Function ReadFrame$(timeoutMs)")
        end = SOURCE.index("End Function", start)
        body = SOURCE[start:end]
        self.assertIn("If Timer - t0 > timeoutMs Then", body)
        self.assertIn("payloadLen <= 0 Or payloadLen > MAX_FRAME_LEN", body)

    def test_message_polling_is_bounded(self):
        start = SOURCE.index("Sub DoReadNextMessage")
        end = SOURCE.index("End Sub", start)
        self.assertIn("Do While quietLoops < 6", SOURCE[start:end])

    def test_channel_send_has_no_automatic_retry(self):
        start = SOURCE.index("Sub DoSendChannelMessage")
        end = SOURCE.index("End Sub", start)
        self.assertEqual(SOURCE[start:end].count("SendFrame payload$"), 1)
