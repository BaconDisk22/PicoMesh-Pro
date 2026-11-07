"""Audit R1: no outgoing string may exceed MMBasic's 255-character limit.

Models the string lengths DoSendMessage, DoSendChannelMessage and SendFrame
build for every text length Line Input can return (0-255), using the caps
read from meshcore.bas. Source-level check only, not PicoMite execution.
"""
from pathlib import Path
import re
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()
MMBASIC_STRING_LIMIT = 255
HEADER_LEN = 3  # "<" + uint16 length


def const(name):
    m = re.search(rf"^Const {name} = (.+)$", SOURCE, re.M)
    expr = m.group(1).strip()
    for other in re.findall(r"[A-Z_]{3,}", expr):
        expr = expr.replace(other, str(const(other)))
    return eval(expr, {"__builtins__": {}})


def body(signature):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index("End Sub", start)]


def text_cap(sub_name, overhead):
    b = body(f"Sub {sub_name}")
    m = re.search(rf"If Len\(msgText\$\) > ([A-Z_]+) - {overhead} Then", b)
    return const(m.group(1)) - overhead


class StringLengthSafetyTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(const("MAX_STRING_LEN"), MMBASIC_STRING_LIMIT)
        self.assertEqual(const("MAX_SEND_PAYLOAD"), MMBASIC_STRING_LIMIT - HEADER_LEN)

    def test_send_frame_rejects_payloads_that_would_overflow_header_join(self):
        self.assertIn("Len(payload$) > MAX_SEND_PAYLOAD Then", body("Sub SendFrame("))

    def check_sub(self, sub_name, overhead, expected_cap):
        cap = text_cap(sub_name, overhead)
        self.assertEqual(cap, expected_cap)
        for n in range(0, MMBASIC_STRING_LIMIT + 1):  # every Line Input length
            if n > cap:
                continue  # rejected before payload$ is built
            payload = overhead + n
            self.assertLessEqual(payload, MMBASIC_STRING_LIMIT, (sub_name, n))
            self.assertLessEqual(payload + HEADER_LEN, MMBASIC_STRING_LIMIT, (sub_name, n))

    def test_direct_message_never_builds_oversized_string(self):
        self.check_sub("DoSendMessage", 13, 239)

    def test_channel_message_never_builds_oversized_string(self):
        self.check_sub("DoSendChannelMessage", 7, 245)

    def test_cap_check_precedes_payload_construction(self):
        for sub_name, overhead in (("DoSendMessage", 13), ("DoSendChannelMessage", 7)):
            b = body(f"Sub {sub_name}")
            guard = f"If Len(msgText$) > MAX_SEND_PAYLOAD - {overhead} Then"
            self.assertLess(b.index(guard), b.index("payload$ = payload$ + msgText$"))

    def test_node_name_payload_is_small(self):
        b = body("Sub DoSetNodeName")
        self.assertIn("If Len(name$) > 32 Then", b)
        self.assertLess(b.index("If Len(name$) > 32 Then"), b.index("payload$ = Chr$(8) + name$"))


if __name__ == "__main__":
    unittest.main()
