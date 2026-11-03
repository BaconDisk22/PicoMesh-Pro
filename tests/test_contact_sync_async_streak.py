"""Source-level guard for continuous asynchronous traffic during contact sync."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class ContactSyncAsyncTests(unittest.TestCase):
    def test_async_streak_bounded_and_reset_on_sync_response(self):
        start = SOURCE.index("Sub DoGetContacts")
        body = SOURCE[start:SOURCE.index("End Sub", start)]
        self.assertIn("Local asyncStreak", body)
        self.assertIn("asyncStreak = asyncStreak + 1", body)
        self.assertIn("If asyncStreak >= 20 Then", body)
        self.assertIn("Contacts may be incomplete", body)
        self.assertIn("Else\n        asyncStreak = 0\n        Select Case codeVal", body)
        self.assertIn("BuildSendableMap", body)

if __name__ == "__main__":
    unittest.main()
