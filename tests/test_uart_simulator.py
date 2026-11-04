import unittest

from uart_simulator import StreamDecoder, encode, MAX_FRAME_LEN


class UARTSimulatorTests(unittest.TestCase):
    def test_round_trip_both_directions(self):
        for payload in (b"\x01", b"\x16\x0a", bytes(range(256)), b"x" * MAX_FRAME_LEN):
            for radio_to_host in (True, False):
                decoder = StreamDecoder(radio_to_host=radio_to_host)
                self.assertEqual(decoder.feed(encode(payload, radio_to_host=radio_to_host)), [payload])

    def test_fragmented_header_and_payload(self):
        decoder = StreamDecoder()
        frame = encode(b"\x03contact")
        output = []
        for part in (frame[:1], frame[1:2], frame[2:5], frame[5:]):
            output.extend(decoder.feed(part))
        self.assertEqual(output, [b"\x03contact"])

    def test_async_interleaving_and_multiple_frames(self):
        decoder = StreamDecoder()
        self.assertEqual(decoder.feed(encode(b"\x88event") + encode(b"\x00ok")), [b"\x88event", b"\x00ok"])

    def test_garbage_before_header(self):
        self.assertEqual(StreamDecoder().feed(b"garbage" + encode(b"\x01")), [b"\x01"])

    def test_reject_zero_and_oversized_lengths(self):
        for bad in (b">\x00\x00", b">\x01\x04"):
            decoder = StreamDecoder()
            self.assertEqual(decoder.feed(bad), [])
            self.assertEqual(decoder.feed(encode(b"\x01")), [b"\x01"])

    def test_partial_timeout_then_recovery(self):
        decoder = StreamDecoder()
        self.assertEqual(decoder.feed(b">\x04\x00\x01"), [])
        decoder.timeout_or_disconnect()
        self.assertEqual(decoder.feed(encode(b"\x16\x0a")), [b"\x16\x0a"])

    def test_reject_invalid_outbound_payload(self):
        for payload in (b"", b"x" * (MAX_FRAME_LEN + 1)):
            with self.assertRaises(ValueError):
                encode(payload)


if __name__ == "__main__":
    unittest.main()
