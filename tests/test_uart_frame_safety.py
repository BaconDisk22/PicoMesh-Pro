"""Static UART receive and diagnostic safety checks (not PicoMite execution)."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

def block(signature, ending):
    start = SOURCE.index(signature)
    end = SOURCE.index(ending, start)
    return SOURCE[start:end]

class UartFrameSafetyTests(unittest.TestCase):
    def test_frame_read_rejects_invalid_length(self):
        body = block("Function ReadFrame$(timeoutMs)", "End Function")
        self.assertIn("payloadLen <= 0 Or payloadLen > MAX_FRAME_LEN", body)
        self.assertIn("gRxBuf$ = Mid$(gRxBuf$, 2)", body)

    def test_async_drain_has_bounded_loop(self):
        body = block("Sub DrainAsyncFrames", "End Sub")
        self.assertIn("Do While loops < 10", body)

    def test_message_polling_is_bounded(self):
        for name in ("Sub DoReadNextMessage", "Sub DoReadAllMessages"):
            self.assertIn("Do While quietLoops < 6", block(name, "End Sub"))
