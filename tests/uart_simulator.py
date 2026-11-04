"""Deterministic protocol framing simulator, NOT an MMBasic runtime or real radio.

PicoMesh Pro transmits '<' and receives '>' followed by uint16 LE length
and payload. This model exercises wire-format invariants independently of hardware.
"""
from dataclasses import dataclass

MAX_FRAME_LEN = 1024
HOST_START = b"<"
RADIO_START = b">"


def encode(payload: bytes, *, radio_to_host: bool = True) -> bytes:
    if not 1 <= len(payload) <= MAX_FRAME_LEN:
        raise ValueError("invalid frame length")
    start = RADIO_START if radio_to_host else HOST_START
    return start + len(payload).to_bytes(2, "little") + payload


@dataclass
class StreamDecoder:
    """Incremental reference decoder. Invalid/partial frames can be reset.

    This is an idealized parser, not a claim that the MMBasic implementation
    behaves identically under timing, UART buffering or Timer rollover.
    """
    radio_to_host: bool = True

    def __post_init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        marker = RADIO_START if self.radio_to_host else HOST_START
        frames = []
        while self.buffer:
            pos = self.buffer.find(marker)
            if pos < 0:
                self.buffer.clear()
                break
            if pos:
                del self.buffer[:pos]
            if len(self.buffer) < 3:
                break
            size = int.from_bytes(self.buffer[1:3], "little")
            if size == 0 or size > MAX_FRAME_LEN:
                # Model the source's invalid-length recovery by discarding
                # the currently buffered bytes.
                self.buffer.clear()
                break
            if len(self.buffer) < size + 3:
                break
            frames.append(bytes(self.buffer[3:3 + size]))
            del self.buffer[:3 + size]
        return frames

    def timeout_or_disconnect(self):
        """Model source FlushInput on a partial frame timeout."""
        self.buffer.clear()
