"""Source-level guard for direct-message frame sizing."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class DirectMessageFrameTests(unittest.TestCase):
    def test_message_length_checked_before_payload_construction(self):
        start = SOURCE.index("Sub DoSendMessage")
        end = SOURCE.index("End Sub", start)
        body = SOURCE[start:end]
        guard = "If Len(msgText$) > MAX_SEND_PAYLOAD - 13 Then"
        self.assertIn(guard, body)
        self.assertLess(body.index(guard), body.index("payload$ = payload$ + msgText$"))
        self.assertIn('Print "Maximum text bytes: "; MAX_SEND_PAYLOAD - 13', body)
        self.assertIn("Exit Sub", body[body.index(guard):body.index("prefix$ = PubKeyPrefix6$")])

if __name__ == "__main__":
    unittest.main()
