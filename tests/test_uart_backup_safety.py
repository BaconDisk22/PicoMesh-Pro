"""Static safety checks for UART and backup code; not hardware tests."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

def routine(name):
    start = SOURCE.index(name)
    end = SOURCE.index("End Sub" if name.startswith("Sub ") else "End Function", start)
    return SOURCE[start:end]

class UartAndBackupSafetyTests(unittest.TestCase):
    def test_uart_frame_length_limit(self):
        body = routine("Sub SendFrame(")
        self.assertIn("Len(payload$) > MAX_SEND_PAYLOAD", body)
        self.assertIn("Print #1", body)

    def test_uart_read_length_limit(self):
        body = routine("Function ReadFrame$(")
        self.assertIn("payloadLen <= 0 Or payloadLen > MAX_FRAME_LEN", body)

    def test_restore_stages_before_live_mutation(self):
        body = routine("Sub DoRestoreLocalChannels")
        self.assertLess(body.index("If validFile = 0 Or seenPublic = 0 Then"), body.index("channelCount = countVal"))

    def test_channel_send_does_not_auto_retry(self):
        body = routine("Sub DoSendChannelMessage")
        self.assertEqual(body.count("SendFrame payload$"), 1)
