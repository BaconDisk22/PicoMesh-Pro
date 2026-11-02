"""Source-level regression tests for device command response handling."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

def subroutine(name):
    start = SOURCE.index("Sub " + name)
    return SOURCE[start:SOURCE.index("End Sub", start)]

class DeviceResponseTests(unittest.TestCase):
    def test_async_skip_helper_is_bounded(self):
        start = SOURCE.index("Function ReadResponseSkippingAsync$(timeoutMs)")
        end = SOURCE.index("End Function", start)
        self.assertIn("asyncCount >= 20", SOURCE[start:end])

    def test_get_time_checks_response_type_and_length(self):
        body = subroutine("DoGetDeviceTime")
        self.assertIn("If codeVal <> 9 Then", body)
        self.assertIn("If Len(frame$) < 5 Then", body)

    def test_sync_time_checks_acknowledgement(self):
        body = subroutine("DoSyncDeviceTime")
        self.assertIn("If codeVal = 0 Then", body)
        self.assertIn("ElseIf codeVal = 1 Then", body)
