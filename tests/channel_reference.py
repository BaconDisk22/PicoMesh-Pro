"""Reference models for channel traffic and MMBasic-style UART reads.

NOT an MMBasic runtime. ``UartReadModel`` mirrors Function ReadFrame$ in
meshcore.bas more literally than uart_simulator.StreamDecoder: bytes that have
not arrived when ReadFrame$ needs them are treated as a timeout, and every
timeout or invalid length after a start byte calls FlushInput, which discards
*everything* buffered, including later frames. Channel helpers mirror
DoSendChannelMessage, ParseChannelMessageFrame, FindChannelNameByIndex$ and
ReadRadioChannelAt. Source-anchor tests keep these in step with meshcore.bas.
"""
from typing import Optional

RESP_OK = 0
RESP_ERR = 1
RESP_SENT = 6
ASYNC_MIN = 128
ASYNC_STREAK_LIMIT = 20


def u32le(value: int) -> bytes:
    return int(value).to_bytes(4, "little")


def async_frame(code: int = 0x88) -> bytes:
    return bytes([code, 0])

MAX_FRAME_LEN = 1024
RADIO_START = 0x3E  # '>'
CMD_SEND_CHANNEL_MSG = 3
CMD_GET_CHANNEL = 31
RESP_CHANNEL_INFO = 18
CHANNEL_INFO_MIN_LEN = 50
CHANNEL_MSG_MIN_LEN = 12
CHANNEL_SEND_OVERHEAD = 7
MAX_CHANNELS = 8


class UartReadModel:
    def __init__(self):
        self.buffer = bytearray()
        self.flushes = 0

    def arrive(self, data: bytes):
        self.buffer.extend(data)

    def _flush(self):
        self.buffer.clear()
        self.flushes += 1

    def read_frame(self) -> Optional[bytes]:
        # Hunt for the start byte; bytes before it are consumed and dropped.
        while self.buffer:
            b = self.buffer.pop(0)
            if b == RADIO_START:
                break
        else:
            return None  # timeout while hunting: no flush in MMBasic
        if len(self.buffer) < 2:
            self._flush()  # timeout waiting for a length byte
            return None
        size = self.buffer[0] | (self.buffer[1] << 8)
        del self.buffer[:2]
        if size <= 0 or size > MAX_FRAME_LEN:
            self._flush()
            return None
        if len(self.buffer) < size:
            self._flush()  # payload did not complete within the timeout
            return None
        payload = bytes(self.buffer[:size])
        del self.buffer[:size]
        return payload


def frame(payload: bytes) -> bytes:
    return bytes([RADIO_START]) + len(payload).to_bytes(2, "little") + payload


def channel_send_payload(channel_idx: int, epoch: int, text: str) -> Optional[bytes]:
    """Mirror of the payload DoSendChannelMessage builds; None if rejected locally."""
    data = text.encode("ascii")
    if not data or len(data) > MAX_FRAME_LEN - CHANNEL_SEND_OVERHEAD:
        return None
    return bytes([CMD_SEND_CHANNEL_MSG, 0, channel_idx]) + u32le(epoch) + data


def channel_send_outcome(replies) -> str:
    """Mirror of the response handling after SendFrame in DoSendChannelMessage."""
    async_count = 0
    for reply in replies:
        if not reply:
            return "unknown"
        if reply[0] >= ASYNC_MIN:
            async_count += 1
            if async_count >= ASYNC_STREAK_LIMIT:
                return "unknown"
            continue
        return {RESP_OK: "sent", RESP_ERR: "failed", RESP_SENT: "queued"}.get(reply[0], "unexpected")
    return "unknown"


def find_channel_name_by_index(channels, idx: int) -> str:
    for name, channel_idx in channels:
        if channel_idx == idx:
            return name
    return "(unknown channel)"


def channel_message_frame(idx: int, text: str, ts: int = 1_790_000_000, *, v3: bool = False,
                          snr: int = 0, path_len: int = 0, txt_type: int = 0) -> bytes:
    if v3:
        head = bytes([17, snr & 0xFF, 0, 0, idx, path_len, txt_type]) + u32le(ts)
    else:
        head = bytes([8, idx, path_len, txt_type]) + u32le(ts)
    return head + text.encode("ascii")


def parse_channel_message(data: bytes) -> Optional[dict]:
    """Mirror of ParseChannelMessageFrame; None for frames it rejects as too short."""
    if len(data) < CHANNEL_MSG_MIN_LEN:
        return None
    if data[0] == 17:
        idx, path_len, txt_type = data[4], data[5], data[6]
        ts = int.from_bytes(data[7:11], "little")
        text = data[11:]
    else:
        idx, path_len, txt_type = data[1], data[2], data[3]
        ts = int.from_bytes(data[4:8], "little")
        text = data[8:]
    return {"idx": idx, "path_len": path_len, "txt_type": txt_type, "ts": ts,
            "text": text.split(b"\x00", 1)[0].decode("ascii", "replace")}


def channel_info_frame(idx: int, name: str, secret: bytes = b"\x5a" * 16) -> bytes:
    body = bytearray(CHANNEL_INFO_MIN_LEN)
    body[0] = RESP_CHANNEL_INFO
    body[1] = idx
    encoded = name.encode("ascii")[:32]
    body[2:2 + len(encoded)] = encoded
    body[34:34 + len(secret)] = secret[:16]
    return bytes(body)


def read_channel_info(reply: Optional[bytes], requested_idx: int):
    """Mirror of ReadRadioChannelAt: returns (status, name). Never returns the secret."""
    if not reply:
        return "no-response", None
    if reply[0] == RESP_ERR:
        return "rejected", None
    if reply[0] != RESP_CHANNEL_INFO:
        return "unexpected", None
    if len(reply) < CHANNEL_INFO_MIN_LEN:
        return "incomplete", None
    if reply[1] != requested_idx:
        return "index-mismatch", None
    name = reply[2:34].split(b"\x00", 1)[0].decode("ascii", "replace")
    return "ok", name
