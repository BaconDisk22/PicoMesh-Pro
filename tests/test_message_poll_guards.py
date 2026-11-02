"""Source-level message polling regression tests; no PicoMite hardware execution."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

def routine(name):
    start = SOURCE.index(name)
    return SOURCE[start:SOURCE.index("End Sub" if name.startswith("Sub ") else "End Function", start)]

class MessagePollingTests(unittest.TestCase):
    def test_read_next_has_bounded_polling(self):
        self.assertIn("Do While quietLoops < 6", routine("Sub DoReadNextMessage"))

    def test_read_all_has_bounded_polling(self):
        self.assertIn("Do While quietLoops < 6", routine("Sub DoReadAllMessages"))

    def test_async_response_skip_is_bounded(self):
        self.assertIn("asyncCount >= 20", routine("Function ReadResponseSkippingAsync$("))

    def test_read_all_reports_count(self):
        self.assertIn('Print "Messages read: "; count', routine("Sub DoReadAllMessages"))
