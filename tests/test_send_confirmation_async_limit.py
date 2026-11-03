from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class SendConfirmationGuardTests(unittest.TestCase):
    def test_async_limit_during_confirmation(self):
        start = SOURCE.index("Function WaitForSendConfirmation(")
        body = SOURCE[start:SOURCE.index("End Function", start)]
        self.assertIn("Local asyncCount", body)
        self.assertIn("asyncCount = asyncCount + 1", body)
        self.assertIn("If asyncCount >= 20 Then", body)
        self.assertIn("WaitForSendConfirmation = 0", body)

if __name__ == "__main__":
    unittest.main()
