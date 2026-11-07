"""Channel-operation and UART-interruption regressions (reference models, not hardware)."""
from pathlib import Path
import unittest

import channel_reference as ch
from channel_reference import async_frame, RESP_ERR, RESP_OK, RESP_SENT, ASYNC_STREAK_LIMIT

SOURCE = (Path(__file__).resolve().parents[1] / "meshcore.bas").read_text()


def body(signature, ending):
    start = SOURCE.index(signature)
    return SOURCE[start:SOURCE.index(ending, start)]


class SourceAnchorTests(unittest.TestCase):
    def test_async_skip_limit(self):
        b = body("Function ReadResponseSkippingAsync$", "End Function")
        self.assertIn(f"If codeVal >= {ch.ASYNC_MIN} Then", b)
        self.assertIn(f"If asyncCount >= {ch.ASYNC_STREAK_LIMIT} Then", b)

    def test_read_frame_resyncs_instead_of_flushing(self):
        b = body("Function ReadFrame$(timeoutMs)", "End Function")
        self.assertNotIn("FlushInput", b)
        self.assertIn("FillRxBuf", b)
        self.assertIn('p = InStr(gRxBuf$, ">")', b)
        self.assertIn("payloadLen = Asc(Mid$(gRxBuf$, 2, 1)) + 256 * Asc(Mid$(gRxBuf$, 3, 1))", b)
        invalid = b[b.index("If payloadLen <= 0 Or payloadLen > MAX_FRAME_LEN Then"):b.index("ElseIf Len(gRxBuf$) >= payloadLen + 3 Then")]
        self.assertIn("gRxBuf$ = Mid$(gRxBuf$, 2)", invalid)
        timeout = b[b.index("If Timer - t0 > timeoutMs Then"):]
        self.assertIn('If Left$(gRxBuf$, 1) = ">" Then gRxBuf$ = Mid$(gRxBuf$, 2)', timeout)

    def test_receive_limits_fit_mmbasic_strings(self):
        self.assertIn("Const MAX_FRAME_LEN = MAX_STRING_LEN - 3", SOURCE)
        self.assertEqual(ch.MAX_FRAME_LEN, 252)
        self.assertGreaterEqual(ch.MAX_FRAME_LEN, 176)  # MeshCore MAX_FRAME_SIZE
        fill = body("Sub FillRxBuf", "End Sub")
        self.assertIn("If n > MAX_STRING_LEN - Len(gRxBuf$) Then n = MAX_STRING_LEN - Len(gRxBuf$)", fill)
        self.assertIn('gRxBuf$ = ""', body("Sub FlushInput", "End Sub"))

    def test_uart_opened_with_larger_receive_buffer(self):
        self.assertIn(f'Open "COM2:115200,{ch.UART_RX_BUFFER}" As #1', SOURCE)
        self.assertEqual(SOURCE.count("Open \"COM"), 1)

    def test_only_fill_and_flush_read_the_uart_after_boot(self):
        readers = [m.start() for m in __import__("re").finditer(r"Input\$\([^)]*#1\)", SOURCE)]
        allowed = [body(n, "End Sub") for n in ("Sub FlushInput", "Sub FillRxBuf", "Sub ReadRawBytes")]
        spans = [(SOURCE.index(a), SOURCE.index(a) + len(a)) for a in allowed]
        for pos in readers:
            self.assertTrue(any(lo <= pos < hi for lo, hi in spans), SOURCE[pos - 80:pos + 20])

    def test_channel_send_layout_and_codes(self):
        b = body("Sub DoSendChannelMessage", "End Sub")
        self.assertIn(f"payload$ = payload$ + Chr${'('}{ch.CMD_SEND_CHANNEL_MSG})", b)
        self.assertIn("payload$ = payload$ + Chr$(channelIdx(idxVal))", b)
        self.assertIn(f"If Len(msgText$) > MAX_SEND_PAYLOAD - {ch.CHANNEL_SEND_OVERHEAD} Then", b)
        self.assertIn("ReadResponseSkippingAsync$(FRAME_TIMEOUT)", b)
        for code in (RESP_OK, RESP_ERR, RESP_SENT):
            self.assertIn(f"codeVal = {code} Then", b)

    def test_channel_message_and_info_offsets(self):
        msg = body("Sub ParseChannelMessageFrame", "End Sub")
        self.assertIn(f"If Len(a$) < {ch.CHANNEL_MSG_MIN_LEN} Then", msg)
        self.assertIn("idxVal = Asc(Mid$(a$, 5, 1))", msg)
        self.assertIn("For i = 12 To Len(a$)", msg)
        self.assertIn("idxVal = Asc(Mid$(a$, 2, 1))", msg)
        self.assertIn("For i = 9 To Len(a$)", msg)
        info = body("Sub ReadRadioChannelAt", "End Sub")
        self.assertIn(f"SendFrame Chr$({ch.CMD_GET_CHANNEL}) + Chr$(idxVal)", info)
        self.assertIn(f"If codeVal <> {ch.RESP_CHANNEL_INFO} Then", info)
        self.assertIn(f"If Len(frame$) < {ch.CHANNEL_INFO_MIN_LEN} Then", info)
        self.assertIn("For i = 3 To 34", info)
        self.assertIn('"Channel secret:      [redacted]"', info)


class UartInterruptionTests(unittest.TestCase):
    """Audit R10: bad or partial frames no longer discard later good frames."""

    def setUp(self):
        self.uart = ch.UartReadModel()

    def test_back_to_back_frames_read_in_order(self):
        self.uart.arrive(ch.frame(b"\x00") + ch.frame(b"\x06ok"))
        self.assertEqual(self.uart.read_frame(), b"\x00")
        self.assertEqual(self.uart.read_frame(), b"\x06ok")
        self.assertIsNone(self.uart.read_frame())

    def test_garbage_without_start_byte_is_dropped(self):
        self.uart.arrive(b"boot noise\r\n")
        self.assertIsNone(self.uart.read_frame())
        self.assertEqual(self.uart.buffer, b"")

    def test_header_cut_after_start_byte_then_recovery(self):
        self.uart.arrive(b">\x05")
        self.assertIsNone(self.uart.read_frame())
        self.uart.arrive(ch.frame(b"\x00"))
        self.assertEqual(self.uart.read_frame(), b"\x00")

    def test_payload_cut_mid_frame_then_reconnect(self):
        self.uart.arrive(ch.frame(b"\x08" + b"x" * 20)[:10])
        self.assertIsNone(self.uart.read_frame())
        self.uart.arrive(ch.frame(b"\x06"))
        self.assertEqual(self.uart.read_frame(), b"\x06")

    def test_invalid_length_keeps_following_good_frame(self):
        self.uart.arrive(b">\x00\x00" + ch.frame(b"\x00"))
        self.assertEqual(self.uart.read_frame(), b"\x00")

    def test_oversized_length_keeps_following_good_frame(self):
        self.uart.arrive(b">\x01\x04" + b"y" * 50 + ch.frame(b"\x00"))
        self.assertEqual(self.uart.read_frame(), b"\x00")

    def test_stray_start_byte_in_noise_recovers_on_next_read(self):
        # '>' in noise looks like a header for 64 bytes; it times out, its
        # start byte is dropped, and the real frame is read next time.
        self.uart.arrive(b"x>\x40\x00" + ch.frame(b"\x00"))
        self.assertIsNone(self.uart.read_frame())
        self.assertEqual(self.uart.read_frame(), b"\x00")

    def test_repeated_async_frames_then_response(self):
        self.uart.arrive(b"".join(ch.frame(async_frame()) for _ in range(5)) + ch.frame(b"\x06"))
        codes = []
        while (data := self.uart.read_frame()) is not None:
            codes.append(data[0])
        self.assertEqual(codes, [0x88] * 5 + [6])

    def test_max_length_frame_accepted_one_over_rejected(self):
        self.uart.arrive(ch.frame(b"z" * ch.MAX_FRAME_LEN))
        self.assertEqual(len(self.uart.read_frame()), ch.MAX_FRAME_LEN)
        self.uart.arrive(b">" + (ch.MAX_FRAME_LEN + 1).to_bytes(2, "little") + b"z" * 20 + ch.frame(b"\x06"))
        self.assertEqual(self.uart.read_frame(), b"\x06")

    def test_software_buffer_never_exceeds_string_limit(self):
        self.uart.arrive(b"".join(ch.frame(b"\x03" + b"c" * 147) for _ in range(6)))
        frames = []
        while (data := self.uart.read_frame()) is not None:
            self.assertLessEqual(len(self.uart.rx), ch.MAX_STRING_LEN)
            frames.append(data)
        self.assertEqual(len(frames), 6)

    def test_contact_burst_fits_larger_buffer_but_not_default(self):
        burst = b"".join(ch.frame(b"\x03" + b"c" * 147) for _ in range(12))  # ~1.8 KB
        self.assertLessEqual(len(burst), ch.UART_RX_BUFFER)
        self.assertGreater(len(burst), 256)
        self.uart.arrive(burst)
        self.assertEqual(self.uart.overflowed, 0)


class ChannelSendTests(unittest.TestCase):
    def test_payload_layout(self):
        p = ch.channel_send_payload(2, 1_790_000_000, "hello")
        self.assertEqual(p[:3], bytes([3, 0, 2]))
        self.assertEqual(int.from_bytes(p[3:7], "little"), 1_790_000_000)
        self.assertEqual(p[7:], b"hello")

    def test_public_channel_uses_index_zero(self):
        self.assertEqual(ch.channel_send_payload(0, 1, "x")[2], 0)

    def test_frame_bound(self):
        limit = ch.MAX_SEND_PAYLOAD - ch.CHANNEL_SEND_OVERHEAD
        self.assertEqual(limit, 245)
        self.assertEqual(len(ch.channel_send_payload(1, 1, "a" * limit)), ch.MAX_SEND_PAYLOAD)
        self.assertIsNone(ch.channel_send_payload(1, 1, "a" * (limit + 1)))
        self.assertIsNone(ch.channel_send_payload(1, 1, ""))

    def test_outcomes(self):
        self.assertEqual(ch.channel_send_outcome([bytes([RESP_OK])]), "sent")
        self.assertEqual(ch.channel_send_outcome([bytes([RESP_SENT])]), "queued")
        self.assertEqual(ch.channel_send_outcome([bytes([RESP_ERR])]), "failed")
        self.assertEqual(ch.channel_send_outcome([bytes([0x12])]), "unexpected")
        self.assertEqual(ch.channel_send_outcome([None]), "unknown")

    def test_async_before_response_and_async_flood(self):
        self.assertEqual(ch.channel_send_outcome([async_frame()] * 3 + [bytes([RESP_SENT])]), "queued")
        flood = [async_frame()] * ASYNC_STREAK_LIMIT + [bytes([RESP_OK])]
        self.assertEqual(ch.channel_send_outcome(flood), "unknown")


class ChannelMessageTests(unittest.TestCase):
    CHANNELS = [("#public", 0), ("#ops", 3)]

    def test_v1_and_v3_parse_to_same_fields(self):
        v1 = ch.parse_channel_message(ch.channel_message_frame(3, "net check", path_len=2))
        v3 = ch.parse_channel_message(ch.channel_message_frame(3, "net check", v3=True, snr=40, path_len=2))
        for key in ("idx", "path_len", "txt_type", "ts", "text"):
            self.assertEqual(v1[key], v3[key], key)
        self.assertEqual(ch.find_channel_name_by_index(self.CHANNELS, v1["idx"]), "#ops")

    def test_public_and_unknown_channel_names(self):
        self.assertEqual(ch.find_channel_name_by_index(self.CHANNELS, 0), "#public")
        self.assertEqual(ch.find_channel_name_by_index(self.CHANNELS, 7), "(unknown channel)")

    def test_short_frames_rejected(self):
        self.assertIsNone(ch.parse_channel_message(bytes([8]) + b"\x00" * 10))
        self.assertIsNone(ch.parse_channel_message(bytes([17]) + b"\x00" * 10))

    def test_empty_v3_text_is_allowed_at_minimum_length(self):
        msg = ch.parse_channel_message(ch.channel_message_frame(0, "", v3=True) + b"\x00")
        self.assertEqual(msg["text"], "")


class ChannelInfoTests(unittest.TestCase):
    def test_ok_returns_name_never_secret(self):
        status, name = ch.read_channel_info(ch.channel_info_frame(2, "#ops", b"S" * 16), 2)
        self.assertEqual((status, name), ("ok", "#ops"))
        self.assertNotIn("S", name)

    def test_failure_paths(self):
        good = ch.channel_info_frame(2, "#ops")
        self.assertEqual(ch.read_channel_info(None, 2)[0], "no-response")
        self.assertEqual(ch.read_channel_info(bytes([RESP_ERR]), 2)[0], "rejected")
        self.assertEqual(ch.read_channel_info(bytes([RESP_OK]), 2)[0], "unexpected")
        self.assertEqual(ch.read_channel_info(good[:49], 2)[0], "incomplete")
        self.assertEqual(ch.read_channel_info(good, 3)[0], "index-mismatch")

    def test_name_bounded_to_32_bytes(self):
        _, name = ch.read_channel_info(ch.channel_info_frame(1, "n" * 40), 1)
        self.assertEqual(len(name), 32)


if __name__ == "__main__":
    unittest.main()
