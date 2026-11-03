"""Source-level checks for bounded direct-message send response handling."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class DirectSendResponseTests(unittest.TestCase):
    def test_direct_send_uses_bounded_async_response_helper(self):
        start = SOURCE.index("Sub DoSendMessage")
        body = SOURCE[start:SOURCE.index("End Sub", start)]
        self.assertIn("frame$ = ReadResponseSkippingAsync$(FRAME_TIMEOUT)", body)
        self.assertNotIn("frame$ = ReadFrame$(FRAME_TIMEOUT)", body)
        self.assertIn("delivery status unknown (do not retry blindly)", body)

    def test_helper_has_async_limit(self):
        start = SOURCE.index("Function ReadResponseSkippingAsync$(timeoutMs)")
        body = SOURCE[start:SOURCE.index("End Function", start)]
        self.assertIn("asyncCount >= 20", body)

if __name__ == "__main__":
    unittest.main()
