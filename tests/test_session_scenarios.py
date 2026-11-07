"""Simulated contact, direct-message and polling scenarios (not hardware tests)."""
from pathlib import Path
import re
import unittest

import session_reference as ref

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()


def body(signature, ending):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index(ending, start)]


def key(n: int) -> bytes:
    return bytes([n]) * 32


START = bytes([ref.RESP_CONTACTS_START]) + ref.u32le(3)
END = bytes([ref.RESP_END_OF_CONTACTS]) + ref.u32le(1_790_000_123)
ALICE = ref.contact_frame(key(0xA1), "Alice", 1)
BOB = ref.contact_frame(key(0xB2), "Bob", 1)
REPEATER = ref.contact_frame(key(0xC3), "Repeater", ref.CONTACT_TYPE_REPEATER)


class SourceAnchorTests(unittest.TestCase):
    """Fail loudly if meshcore.bas drifts from what the reference models copy."""

    def test_contact_sync_thresholds_and_codes(self):
        b = body("Sub DoGetContacts", "End Sub")
        self.assertIn(f"If quietVal >= {ref.CONTACT_SYNC_QUIET_LIMIT} Then", b)
        self.assertIn(f"If asyncStreak >= {ref.ASYNC_STREAK_LIMIT} Then", b)
        for code in (ref.RESP_CONTACTS_START, ref.RESP_CONTACT, ref.RESP_END_OF_CONTACTS):
            self.assertRegex(b, rf"\n\s+Case {code}\n")
        silent = body("Sub ParseContactSilent", "End Sub")
        self.assertIn(f"If Len(a$) < {ref.CONTACT_FRAME_MIN_LEN} Then Exit Sub", silent)
        self.assertIn("ReadCString$(a$, 101)", silent)
        self.assertIn("If contactCount < MAX_CONTACTS Then", silent)
        self.assertIn(f"Const MAX_CONTACTS = {ref.MAX_CONTACTS}", SOURCE)

    def test_send_response_codes(self):
        b = body("Sub DoSendMessage", "End Sub")
        self.assertIn(f"If codeVal = {ref.RESP_OK} Then", b)
        self.assertIn(f"ElseIf codeVal = {ref.RESP_ERR} Then", b)
        self.assertIn(f"ElseIf codeVal = {ref.RESP_SENT} Then", b)
        self.assertIn("delivery status unknown (do not retry blindly)", b)
        confirm = body("Function WaitForSendConfirmation", "End Function")
        self.assertIn(f"If codeVal = {ref.PUSH_SEND_CONFIRMED} And Len(frame$) >= 5 And Mid$(frame$, 2, 4) = ackKey$ Then", confirm)
        self.assertIn("ackKey$ = Mid$(frame$, 3, 4)", b)
        self.assertIn("waitMs = U32LEVal(frame$, 7)", b)
        self.assertIn(f"Const SEND_CONFIRM_MIN_MS = {ref.SEND_CONFIRM_MIN_MS}", SOURCE)
        self.assertIn(f"Const SEND_CONFIRM_MAX_MS = {ref.SEND_CONFIRM_MAX_MS}", SOURCE)
        self.assertIn("frame$ = ReadFrame$(300)", confirm)
        self.assertIn(f"If asyncCount >= {ref.ASYNC_STREAK_LIMIT} Then", confirm)
        skip = body("Function ReadResponseSkippingAsync$", "End Function")
        self.assertIn(f"If asyncCount >= {ref.ASYNC_STREAK_LIMIT} Then", skip)

    def test_poll_and_message_codes(self):
        b = body("Sub DoReadNextMessage", "End Sub")
        self.assertIn(f"Do While quietLoops < {ref.POLL_QUIET_LIMIT}", b)
        self.assertIn(f"ElseIf codeVal = {ref.RESP_NO_MORE_MESSAGES} Then", b)
        real = body("Function IsRealMessage", "End Function")
        codes = sorted(int(c) for c in re.findall(r"codeVal = (\d+)", real))
        self.assertEqual(codes, sorted([ref.RESP_CONTACT_MSG, ref.RESP_CHANNEL_MSG,
                                        ref.RESP_CONTACT_MSG_V3, ref.RESP_CHANNEL_MSG_V3]))
        msg = body("Sub ParseContactMessageFrame", "End Sub")
        self.assertIn(f"If Len(a$) < {ref.CONTACT_MSG_MIN_LEN} Then", msg)
        self.assertIn("For i = 5 To 10", msg)
        self.assertIn("For i = 17 To Len(a$)", msg)


class ContactSyncScenarioTests(unittest.TestCase):
    def test_clean_sync_excludes_repeaters_from_sendable(self):
        r = ref.sync_contacts([START, ALICE, BOB, REPEATER, END])
        self.assertTrue(r.completed)
        self.assertEqual((r.expected, r.received), (3, 3))
        self.assertEqual([c.name for c in r.sendable], ["Alice", "Bob"])
        self.assertEqual(r.since, 1_790_000_123)

    def test_async_frames_interleaved_do_not_lose_contacts(self):
        noise = ref.async_frame(0x83)
        r = ref.sync_contacts([START, noise, ALICE, noise, noise, BOB, noise, REPEATER, END])
        self.assertTrue(r.completed)
        self.assertEqual(len(r.contacts), 3)

    def test_async_streak_resets_on_each_sync_frame(self):
        burst = [ref.async_frame()] * (ref.ASYNC_STREAK_LIMIT - 1)
        r = ref.sync_contacts([START, *burst, ALICE, *burst, BOB, END])
        self.assertTrue(r.completed)
        self.assertFalse(r.stopped_by_async)

    def test_continuous_async_stops_sync_as_incomplete(self):
        r = ref.sync_contacts([START, ALICE] + [ref.async_frame()] * ref.ASYNC_STREAK_LIMIT + [BOB, END])
        self.assertTrue(r.stopped_by_async)
        self.assertFalse(r.completed)
        self.assertEqual([c.name for c in r.contacts], ["Alice"])

    def test_delayed_responses_within_quiet_limit_complete(self):
        gap = [None] * (ref.CONTACT_SYNC_QUIET_LIMIT - 1)
        r = ref.sync_contacts([*gap, START, *gap, ALICE, *gap, END])
        self.assertTrue(r.completed)

    def test_interrupted_stream_times_out_with_partial_contacts(self):
        r = ref.sync_contacts([START, ALICE])  # radio goes silent
        self.assertTrue(r.timed_out)
        self.assertFalse(r.completed)
        self.assertEqual((r.expected, r.received), (3, 1))

    def test_truncated_and_unexpected_frames_are_counted_not_stored(self):
        r = ref.sync_contacts([START, ALICE[:100], bytes([ref.RESP_OK]), BOB, END])
        self.assertTrue(r.completed)
        self.assertEqual(r.received, 2)  # truncated frame counted, not stored
        self.assertEqual([c.name for c in r.contacts], ["Bob"])

    def test_short_start_and_end_frames_are_tolerated(self):
        r = ref.sync_contacts([bytes([ref.RESP_CONTACTS_START]), ALICE, bytes([ref.RESP_END_OF_CONTACTS])])
        self.assertTrue(r.completed)
        self.assertEqual((r.expected, r.since), (0, 0))

    def test_contact_storage_is_capped(self):
        frames = [ref.contact_frame(key(i % 256), f"N{i}") for i in range(ref.MAX_CONTACTS + 5)]
        r = ref.sync_contacts([START, *frames, END])
        self.assertEqual(len(r.contacts), ref.MAX_CONTACTS)
        self.assertEqual(r.received, ref.MAX_CONTACTS + 5)


class DirectSendScenarioTests(unittest.TestCase):
    ACK = b"\x11\x22\x33\x44"
    OTHER_ACK = b"\x99\x88\x77\x66"
    OK = bytes([ref.RESP_OK])
    SENT = ref.sent_frame(ACK, est_timeout_ms=3000)
    CONFIRM = ref.confirm_frame(ACK)

    def test_queued_then_delivered(self):
        self.assertEqual(ref.direct_send_outcome([self.SENT, None, self.CONFIRM]), "delivered")

    def test_plain_ok_is_untracked(self):
        self.assertEqual(ref.direct_send_outcome([self.OK, self.CONFIRM]), "untracked")

    def test_short_sent_frame_is_untracked(self):
        self.assertEqual(ref.direct_send_outcome([self.SENT[:5], self.CONFIRM]), "untracked")

    def test_async_before_response_is_skipped(self):
        replies = [ref.async_frame(0x88)] * 5 + [self.SENT, self.CONFIRM]
        self.assertEqual(ref.direct_send_outcome(replies), "delivered")

    def test_async_flood_before_response_is_unknown(self):
        replies = [ref.async_frame()] * ref.ASYNC_STREAK_LIMIT + [self.SENT]
        self.assertEqual(ref.direct_send_outcome(replies), "unknown")

    def test_no_response_is_unknown_not_failed(self):
        self.assertEqual(ref.direct_send_outcome([]), "unknown")

    def test_error_and_unexpected_responses(self):
        self.assertEqual(ref.direct_send_outcome([bytes([ref.RESP_ERR])]), "failed")
        self.assertEqual(ref.direct_send_outcome([bytes([ref.RESP_CONTACT])]), "unexpected")

    def test_confirmation_flood_is_interrupted(self):
        replies = [self.SENT] + [ref.async_frame()] * ref.ASYNC_STREAK_LIMIT
        self.assertEqual(ref.direct_send_outcome(replies, confirm_polls=40), "interrupted")

    def test_extra_non_async_frame_during_confirm_is_ignored(self):
        replies = [self.SENT, bytes([ref.RESP_CONTACT_MSG]), self.CONFIRM]
        self.assertEqual(ref.direct_send_outcome(replies), "delivered")

    def test_late_confirmation_after_window_is_unconfirmed(self):
        replies = [self.SENT] + [None] * 7 + [self.CONFIRM]
        self.assertEqual(ref.direct_send_outcome(replies, confirm_polls=7), "queued-unconfirmed")

    # Audit R2: a confirmation for an earlier message must not count.
    def test_confirmation_for_other_message_is_not_delivery(self):
        replies = [self.SENT, ref.confirm_frame(self.OTHER_ACK)]
        self.assertEqual(ref.direct_send_outcome(replies), "queued-unconfirmed")

    def test_matching_confirmation_after_stale_one_is_delivery(self):
        replies = [self.SENT, ref.confirm_frame(self.OTHER_ACK), None, self.CONFIRM]
        self.assertEqual(ref.direct_send_outcome(replies), "delivered")

    def test_truncated_confirmation_is_not_delivery(self):
        replies = [self.SENT, self.CONFIRM[:4]]
        self.assertEqual(ref.direct_send_outcome(replies), "queued-unconfirmed")

    def test_ack_bytes_containing_nul_still_match(self):
        ack = b"\x00\x01\x00\x02"
        self.assertEqual(ref.direct_send_outcome([ref.sent_frame(ack), ref.confirm_frame(ack)]), "delivered")

    # Audit R11: wait window follows the radio's estimate, clamped.
    def test_wait_window_uses_radio_estimate_with_clamp(self):
        self.assertEqual(ref.confirm_wait_ms(ref.sent_frame(self.ACK, 500)), ref.SEND_CONFIRM_MIN_MS)
        self.assertEqual(ref.confirm_wait_ms(ref.sent_frame(self.ACK, 9000)), 9000)
        self.assertEqual(ref.confirm_wait_ms(ref.sent_frame(self.ACK, 120000)), ref.SEND_CONFIRM_MAX_MS)

    def test_flood_confirmation_inside_longer_window_is_delivered(self):
        sent = ref.sent_frame(self.ACK, est_timeout_ms=9000, flood=True)
        replies = [sent] + [None] * 20 + [self.CONFIRM]  # ~6 s of silence
        self.assertEqual(ref.direct_send_outcome(replies), "delivered")


class MessagePollScenarioTests(unittest.TestCase):
    def setUp(self):
        self.contacts = ref.sync_contacts([START, ALICE, BOB, END]).contacts

    def test_message_after_no_more_and_async(self):
        msg = ref.contact_message_frame(key(0xB2)[:6], "hi there")
        r = ref.poll_next_message([bytes([ref.RESP_NO_MORE_MESSAGES]), ref.async_frame(), msg])
        self.assertEqual(r.message, msg)
        self.assertEqual(r.requests_sent, 3)
        self.assertEqual(ref.contact_message_sender(r.message, self.contacts), "Bob")
        self.assertEqual(ref.contact_message_text(r.message), "hi there")

    def test_polling_gives_up_after_quiet_limit(self):
        r = ref.poll_next_message([bytes([ref.RESP_NO_MORE_MESSAGES])] * 10)
        self.assertIsNone(r.message)
        self.assertEqual(r.requests_sent, ref.POLL_QUIET_LIMIT)

    def test_unexpected_frames_count_toward_quiet_limit(self):
        r = ref.poll_next_message([bytes([ref.RESP_CONTACT])] * ref.POLL_QUIET_LIMIT)
        self.assertIsNone(r.message)
        self.assertEqual(r.skipped_non_message, ref.POLL_QUIET_LIMIT)

    def test_message_just_inside_quiet_limit_is_read(self):
        msg = ref.contact_message_frame(key(0xA1)[:6], "late", v3=True)
        r = ref.poll_next_message([None] * (ref.POLL_QUIET_LIMIT - 1) + [msg])
        self.assertEqual(r.message, msg)

    def test_message_after_quiet_limit_is_missed(self):
        msg = ref.contact_message_frame(key(0xA1)[:6], "too late")
        r = ref.poll_next_message([None] * ref.POLL_QUIET_LIMIT + [msg])
        self.assertIsNone(r.message)

    def test_unknown_sender_and_short_frame(self):
        msg = ref.contact_message_frame(b"\x99" * 6, "who")
        self.assertEqual(ref.contact_message_sender(msg, self.contacts), "(unknown)")
        self.assertIsNone(ref.contact_message_sender(msg[:16], self.contacts))

    def test_text_stops_at_nul(self):
        msg = ref.contact_message_frame(key(0xA1)[:6], "visible") + b"\x00hidden"
        self.assertEqual(ref.contact_message_text(msg), "visible")


if __name__ == "__main__":
    unittest.main()
