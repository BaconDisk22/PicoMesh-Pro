from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class InitializationStatusTests(unittest.TestCase):
    def test_does_not_claim_unverified_success(self):
        start = SOURCE.index("Sub DoInitialize")
        body = SOURCE[start:SOURCE.index("End Sub", start)]
        self.assertIn('Print "Initialization commands finished"', body)
        self.assertIn('Check the responses above to confirm radio readiness', body)
        self.assertNotIn('Print "Initialization complete"', body)

if __name__ == "__main__":
    unittest.main()
