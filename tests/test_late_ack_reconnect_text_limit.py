"""Audit R11 (late confirmations), R12 (reconnect hint) and the radio text limit.

Source anchors plus a small Python model of the pending-ACK flow. Firmware
facts from MeshCore main 81dbae5: MAX_TEXT_LEN is 160; direct text over it is
refused; channel text is sent as "<node name>: <text>" and cut to 160.
Not PicoMite execution.
"""
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()


def block(signature, end):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index(end, start)]


class PendingAckModel:
    """Mirror of gPendingAck$ handling across DoSendMessage, WaitForSendConfirmation,
    HandleAsyncFrame and CheckLateAck."""

    def __init__(self):
        self.pending = b""
        self.log = []

    def check_late_ack(self, frame):
        if len(self.pending) != 4 or len(frame) < 5 or frame[0] != 130 or frame[1:5] != self.pending:
            return False
        self.log.append("late-delivered")
        self.pending = b""
        return True

    def send(self, ack, pushes_during_wait):
        """One DoSendMessage after RESP_CODE_SENT carrying ``ack``."""
        for push in pushes_during_wait:
            if push[0] == 130 and push[1:5] == ack:
                self.log.append("delivered")
                self.pending = b""
                return
            if push[0] == 130 and not self.check_late_ack(push):
                self.log.append("ignored")
        self.log.append("unconfirmed")
        self.pending = ack

    def async_push(self, push):
        if push[0] == 130:
            self.check_late_ack(push)


def confirm(ack):
    return bytes([130]) + ack + b"\x00\x00\x00\x00"


A, B = b"\xaa\x01\x02\x03", b"\xbb\x04\x05\x06"


class LateAckTests(unittest.TestCase):
    def test_late_confirmation_while_idle_is_reported_once(self):
        m = PendingAckModel()
        m.send(A, [])
        m.async_push(confirm(A))
        m.async_push(confirm(A))
        self.assertEqual(m.log, ["unconfirmed", "late-delivered"])

    def test_late_confirmation_during_next_send_credits_previous_message(self):
        m = PendingAckModel()
        m.send(A, [])
        m.send(B, [confirm(A)])
        self.assertEqual(m.log, ["unconfirmed", "late-delivered", "unconfirmed"])
        self.assertEqual(m.pending, B)

    def test_unknown_confirmation_is_ignored(self):
        m = PendingAckModel()
        m.send(A, [confirm(b"\x99\x99\x99\x99")])
        self.assertEqual(m.log, ["ignored", "unconfirmed"])

    def test_delivered_clears_pending(self):
        m = PendingAckModel()
        m.send(A, [confirm(A)])
        self.assertEqual(m.pending, b"")

    def test_source_matches_model(self):
        late = block("Function CheckLateAck(a$)", "End Function")
        self.assertIn("If Len(gPendingAck$) <> 4 Or Len(a$) < 5 Then Exit Function", late)
        self.assertIn("If Mid$(a$, 2, 4) <> gPendingAck$ Then Exit Function", late)
        self.assertIn('gPendingAck$ = ""', late)
        send = block("Sub DoSendMessage", "End Sub")
        miss = send[send.index("If deliveredOk = 0 Then"):]
        self.assertLess(miss.index("gPendingAck$ = ackKey$"), miss.index("Else"))
        self.assertIn('gPendingAck$ = ""', miss[miss.index("Else"):])
        wait = block("Function WaitForSendConfirmation(", "End Function")
        self.assertIn("If CheckLateAck(frame$) = 0 Then", wait)
        handler = block("Sub HandleAsyncFrame(a$)", "End Sub")
        case130 = handler[handler.index("Case 130"):handler.index("Case 131")]
        self.assertIn("CheckLateAck(a$)", case130)


class ReconnectHintTests(unittest.TestCase):
    def test_counts_only_timeouts_and_resets_on_reply(self):
        b = block("Function ReadResponseSkippingAsync$(timeoutMs)", "End Function")
        timeout = b[b.index('If frame$ = "" Then'):b.index("codeVal = Asc")]
        self.assertIn("NoteNoReply", timeout)
        reply = b[b.index("    Else\n      gNoReplyCount = 0"):]
        self.assertIn("ReadResponseSkippingAsync$ = frame$", reply)
        flood = b[b.index("If asyncCount >= 20 Then"):b.index("    Else\n      gNoReplyCount = 0")]
        self.assertNotIn("NoteNoReply", flood)  # async flood is not silence

    def test_hint_after_three_silent_commands_once(self):
        b = block("Sub NoteNoReply", "End Sub")
        self.assertIn("If gNoReplyCount = 3 Then", b)
        self.assertIn("Initialize radio", b)


class RadioTextLimitTests(unittest.TestCase):
    def test_limit_matches_firmware(self):
        self.assertIn("Const MAX_TEXT_LEN = 160", SOURCE)

    def test_direct_limit_checked_before_payload(self):
        b = block("Sub DoSendMessage", "End Sub")
        guard = "If Len(msgText$) > MAX_TEXT_LEN Then"
        self.assertLess(b.index(guard), b.index("payload$ = payload$ + msgText$"))
        self.assertLess(b.index("If Len(msgText$) > MAX_SEND_PAYLOAD - 13 Then"), b.index(guard))

    def test_channel_limit_accounts_for_name_prefix(self):
        b = block("Sub DoSendChannelMessage", "End Sub")
        guard = "If Len(msgText$) > MAX_TEXT_LEN - Len(gNodeName$) - 2 Then"
        self.assertLess(b.index(guard), b.index("payload$ = payload$ + msgText$"))
        # Firmware: "<name>: " + text must fit 160, else it is cut.
        for name in ("", "Base", "n" * 32):
            limit = 160 - len(name) - 2
            self.assertLessEqual(len(f"{name}: ") + limit, 160)
            self.assertGreater(len(f"{name}: ") + limit + 1, 160)


if __name__ == "__main__":
    unittest.main()
