from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class ConfirmationTimeoutTests(unittest.TestCase):
    def test_nonpositive_timeout_returns_unconfirmed(self):
        start = SOURCE.index("Function WaitForSendConfirmation(")
        body = SOURCE[start:SOURCE.index("End Function", start)]
        self.assertIn("If timeoutMs <= 0 Or Len(ackKey$) <> 4 Then", body)
        self.assertIn("WaitForSendConfirmation = 0\n    Exit Function", body)
        self.assertLess(body.index("If timeoutMs <= 0 Or Len(ackKey$) <> 4 Then"), body.index("t0 = Timer"))

if __name__ == "__main__":
    unittest.main()
