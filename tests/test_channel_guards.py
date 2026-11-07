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

    def test_local_channel_name_is_bounded_and_printable(self):
        body = sub("DoAddChannel")
        self.assertIn("Len(name$) > 32", body)
        self.assertIn("Asc(Mid$(name$, i, 1)) < 32", body)

    def test_local_index_matches_supported_radio_slots(self):
        body = sub("DoAddChannel")
        self.assertIn("idxVal < 0 Or idxVal >= MAX_CHANNELS", body)

    def test_manual_channel_cannot_reuse_public_name(self):
        body = sub("DoAddChannel")
        self.assertIn('If name$ = "#public" Then', body)
        self.assertIn('Print "#public is reserved for radio channel 0"', body)

    def test_channel_name_validation_locations_exist(self):
        manual = sub("DoAddChannel")
        imported = sub("DoSyncRadioChannels")
        restored = sub("DoRestoreLocalChannels")
        exported = sub("DoExportLocalChannels")
        self.assertIn('name$ = "#public"', manual)
        self.assertIn("validName = 0", imported)
        self.assertIn("validFile = 0", restored)
        self.assertIn('nameChar$ = "_"', exported)

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
        self.assertIn("Len(msgText$) > MAX_SEND_PAYLOAD - 7", body)
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

    def test_imported_names_reject_controls_and_empty_values(self):
        body = sub("DoSyncRadioChannels")
        self.assertIn('If name$ = "" Then validName = 0', body)
        self.assertIn("Asc(Mid$(name$, j, 1)) < 32", body)
        self.assertIn("Skipped invalid/empty name", body)

    def test_channel_import_requires_explicit_confirmation(self):
        body = sub("DoSyncRadioChannels")
        self.assertIn('confirm$ <> "IMPORT"', body)
        self.assertIn("Cancelled; no changes made", body)

    def test_channel_export_uses_sanitized_copy_and_no_keys(self):
        body = sub("DoExportLocalChannels")
        self.assertIn('If nameChar$ = "|" Then nameChar$ = "_"', body)
        self.assertIn('Trim$(Str$(channelIdx(i)))', body)
        self.assertNotIn('Mid$(safeName$, j, 1) = "_"', body)
        self.assertNotIn('channelKey$(', body)
        self.assertIn('confirm$ <> "EXPORT"', body)

    def test_restore_is_confirmation_gated(self):
        body = sub("DoRestoreLocalChannels")
        self.assertIn('confirm$ <> "RESTORE"', body)
        self.assertIn('line$ <> "PICOMESH-CHANNELS-V1"', body)

    def test_restore_stages_before_mutating_live_channels(self):
        body = sub("DoRestoreLocalChannels")
        self.assertIn("stagedName$(countVal) = name$", body)
        self.assertIn("stagedIdx(countVal) = idxVal", body)
        self.assertLess(body.index("Close #2"), body.index("channelCount = countVal"))
        self.assertIn("validFile = 0 Or seenPublic = 0", body)

    def test_restore_rejects_duplicates_and_out_of_range_indexes(self):
        body = sub("DoRestoreLocalChannels")
        self.assertIn('InStr("01234567", number$) = 0', body)
        self.assertIn("stagedIdx(i) = idxVal", body)
        self.assertIn('name$ <> "#public"', body)
        self.assertIn("countVal >= MAX_CHANNELS", body)

    def test_restore_requires_public_channel_first(self):
        body = sub("DoRestoreLocalChannels")
        self.assertIn("If countVal = 0 And idxVal <> 0 Then validFile = 0", body)
        self.assertIn('If name$ <> "#public" Then validFile = 0', body)

    def test_restore_reserves_public_name_for_index_zero(self):
        body = sub("DoRestoreLocalChannels")
        self.assertIn('If idxVal <> 0 And name$ = "#public" Then validFile = 0', body)
        self.assertIn('If name$ <> "#public" Then validFile = 0', body)

    def test_restore_does_not_write_radio_or_load_keys(self):
        body = sub("DoRestoreLocalChannels")
        self.assertNotIn("SendFrame", body)
        self.assertIn('channelKey$(i) = ""', body)
        self.assertIn('channelPrefix$(i) = ""', body)

    def test_channel_backup_export_restore_format_agrees(self):
        exporter = sub("DoExportLocalChannels")
        restorer = sub("DoRestoreLocalChannels")
        self.assertIn('Print #2, "PICOMESH-CHANNELS-V1"', exporter)
        self.assertIn('line$ <> "PICOMESH-CHANNELS-V1"', restorer)
        self.assertIn('Trim$(Str$(channelIdx(i))); "|"; safeName$', exporter)
        self.assertIn('separator = InStr(line$, "|")', restorer)
        self.assertIn('number$ = Left$(line$, separator - 1)', restorer)
        self.assertIn('name$ = Mid$(line$, separator + 1)', restorer)

    def test_backup_menu_actions_are_wired(self):
        menu = sub("ChannelsMenu")
        self.assertIn('Case "8"', menu)
        self.assertIn("DoExportLocalChannels", menu)
        self.assertIn('Case "9"', menu)
        self.assertIn("DoRestoreLocalChannels", menu)

    def test_local_removal_requires_confirmation_and_protects_public(self):
        body = sub("DoRemoveLocalChannel")
        self.assertIn("channelIdx(idxVal) = 0", body)
        self.assertIn('confirm$ <> "REMOVE"', body)
        self.assertIn('channelKey$(channelCount) = ""', body)
        self.assertIn('channelPrefix$(channelCount) = ""', body)

if __name__ == "__main__":
    unittest.main()
