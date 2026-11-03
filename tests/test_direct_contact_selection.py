"""Guard against Val() silently accepting malformed contact selections."""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

class ContactSelectionTests(unittest.TestCase):
    def test_direct_send_requires_digits_before_val(self):
        start = SOURCE.index("Sub DoSendMessage")
        body = SOURCE[start:SOURCE.index("End Sub", start)]
        self.assertIn('If idxStr$ = "" Then', body)
        self.assertIn('InStr("0123456789", Mid$(idxStr$, idxVal, 1)) = 0', body)
        self.assertIn('Print "Contact selection must be a whole number"', body)
        self.assertLess(body.index('InStr("0123456789"'), body.index('GetSendableContactIndex(Val(idxStr$))'))

if __name__ == "__main__":
    unittest.main()
