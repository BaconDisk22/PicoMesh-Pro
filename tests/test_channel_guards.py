"""Source-level regression checks. Not a PicoMite interpreter or hardware test."""
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()

def sub(name):
    match = re.search(r"(?im)^Sub " + re.escape(name) + r"(?:\([^\n]*\))?\s*$([\s\S]*?)^End Sub\s*$", SOURCE)
    if not match:
        raise AssertionError(f"Missing Sub {name}")
    return match.group(1)

class ChannelGuardTests(unittest.TestCase):
    def test_public_channel_defaults_to_zero(self):
        self.assertIn('channelName$(1) = "#public"', SOURCE)
        self.assertIn("channelIdx(1) = 0", SOURCE)

    def test_duplicate_channel_indexes_rejected(self):
        body = sub("DoAddChannel")
        self.assertIn("channelIdx(i) = idxVal", body)
        self.assertIn("Channel index already exists", body)

    def test_channel_send_selection_validated(self):
        body = sub("DoSendChannelMessage")
        self.assertIn('InStr("0123456789", Mid$(idxStr$, i, 1))', body)
        self.assertIn("idxVal < 1 Or idxVal > channelCount", body)

    def test_channel_send_respects_local_frame_bound(self):
        body = sub("DoSendChannelMessage")
        self.assertIn("Len(msgText$) > MAX_FRAME_LEN - 7", body)
        self.assertIn("Message too long for local frame limit", body)

    def test_channel_send_does_not_dump_raw_response(self):
        body = sub("DoSendChannelMessage")
        self.assertNotIn("DumpHex frame$", body)
        self.assertIn("Response details suppressed", body)

    def test_radio_query_never_dumps_secret(self):
        body = sub("ReadRadioChannelAt")
        self.assertIn("Chr$(31) + Chr$(idxVal)", body)
        self.assertIn("Channel secret:      [redacted]", body)
        self.assertNotIn("DumpHex", body)

    def test_import_does_not_store_secret(self):
        body = sub("DoSyncRadioChannels")
        self.assertIn("channelName$(i) = name$", body)
        self.assertNotIn("channelKey$(", body)
        self.assertNotIn("channelPrefix$(", body)

    def test_channel_import_requires_explicit_confirmation(self):
        body = sub("DoSyncRadioChannels")
        self.assertIn('confirm$ <> "IMPORT"', body)
        self.assertIn("Cancelled; no changes made", body)

    def test_local_removal_requires_confirmation_and_protects_public(self):
        body = sub("DoRemoveLocalChannel")
        self.assertIn("channelIdx(idxVal) = 0", body)
        self.assertIn('confirm$ <> "REMOVE"', body)
        self.assertIn('channelKey$(channelCount) = ""', body)
        self.assertIn('channelPrefix$(channelCount) = ""', body)

if __name__ == "__main__":
    unittest.main()
