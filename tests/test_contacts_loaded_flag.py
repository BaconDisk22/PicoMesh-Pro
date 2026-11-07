"""Audit R3: contacts are synced once, and only a completed sync counts.

Source-level checks plus the session reference model; not PicoMite execution.
"""
from pathlib import Path
import re
import unittest

import session_reference as ref

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()


def body(signature):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("End Sub", start)]


class ContactsLoadedFlagTests(unittest.TestCase):
    def test_flag_is_only_written_inside_contact_sync(self):
        sync = body("Sub DoGetContacts")
        self.assertEqual(SOURCE.count("contactsLoaded = 1"), 1)
        self.assertEqual(sync.count("contactsLoaded = 1"), 1)
        clear = re.compile(r"^\s*contactsLoaded = 0$", re.M)
        self.assertEqual(len(clear.findall(SOURCE)), 1)
        self.assertEqual(len(clear.findall(sync)), 1)

    def test_flag_cleared_before_request_and_set_only_on_end_of_contacts(self):
        sync = body("Sub DoGetContacts")
        self.assertLess(sync.index("contactsLoaded = 0"), sync.index("SendFrame payload$"))
        end_case = sync[sync.index(f"Case {ref.RESP_END_OF_CONTACTS}\n"):sync.index("Case Else")]
        self.assertIn("contactsLoaded = 1", end_case)
        for failure in ("Timeout waiting for contacts frame", "Contact sync stopped after continuous async traffic"):
            branch_start = sync.index(failure)
            branch = sync[branch_start:sync.index("Exit Do", branch_start)]
            self.assertNotIn("contactsLoaded = 1", branch)

    def test_ensure_contacts_loaded_only_syncs_when_unloaded(self):
        ensure = body("Sub EnsureContactsLoaded")
        self.assertIn("If contactsLoaded = 0 Then\n    DoGetContacts", ensure)

    def test_model_only_completed_sync_counts_as_loaded(self):
        start = bytes([ref.RESP_CONTACTS_START]) + ref.u32le(1)
        end = bytes([ref.RESP_END_OF_CONTACTS]) + ref.u32le(0)
        alice = ref.contact_frame(b"\xa1" * 32, "Alice")
        self.assertTrue(ref.sync_contacts([start, alice, end]).completed)
        self.assertFalse(ref.sync_contacts([start, alice]).completed)
        flood = [ref.async_frame()] * ref.ASYNC_STREAK_LIMIT
        self.assertFalse(ref.sync_contacts([start, *flood, end]).completed)


if __name__ == "__main__":
    unittest.main()
