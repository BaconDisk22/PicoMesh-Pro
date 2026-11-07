"""Reference models of PicoMesh Pro session logic, NOT an MMBasic runtime.

Each model mirrors the control flow of one MMBasic routine in meshcore.bas so
that scenario tests can exercise contact sync, direct-send responses and
message polling against scripted radio replies. A scripted reply of ``None``
represents a ReadFrame$ timeout (empty string in MMBasic).

These models are deliberately small and are kept honest by source-anchor tests
(test_session_scenarios.SourceAnchorTests) that fail if the MMBasic thresholds
or response codes they copy change. Passing tests here do not show that the
MMBasic program behaves the same on a PicoMite with a real companion radio.
"""
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

# Response / push codes as used by meshcore.bas.
RESP_OK = 0
RESP_ERR = 1
RESP_CONTACTS_START = 2
RESP_CONTACT = 3
RESP_END_OF_CONTACTS = 4
RESP_SENT = 6
RESP_CONTACT_MSG = 7
RESP_CHANNEL_MSG = 8
RESP_NO_MORE_MESSAGES = 10
RESP_CONTACT_MSG_V3 = 16
RESP_CHANNEL_MSG_V3 = 17
PUSH_SEND_CONFIRMED = 130
ASYNC_MIN = 128

CONTACT_FRAME_MIN_LEN = 148
CONTACT_TYPE_REPEATER = 2  # MeshCore ADV_TYPE_REPEATER; excluded from the sendable map
MAX_CONTACTS = 320

CONTACT_SYNC_QUIET_LIMIT = 3
ASYNC_STREAK_LIMIT = 20
POLL_QUIET_LIMIT = 6
CONTACT_MSG_MIN_LEN = 17


def u32le(value: int) -> bytes:
    return int(value).to_bytes(4, "little")


def contact_frame(pubkey: bytes, name: str, contact_type: int = 1) -> bytes:
    """Build a RESP_CONTACT frame with the offsets ParseContactSilent reads."""
    if len(pubkey) != 32:
        raise ValueError("pubkey must be 32 bytes")
    frame = bytearray(CONTACT_FRAME_MIN_LEN)
    frame[0] = RESP_CONTACT
    frame[1:33] = pubkey
    frame[33] = contact_type
    encoded = name.encode("ascii")[:32]
    frame[100:100 + len(encoded)] = encoded  # MMBasic index 101 (1-based)
    return bytes(frame)


def contact_message_frame(sender_prefix: bytes, text: str, ts: int = 1_790_000_000,
                          v3: bool = False) -> bytes:
    """Contact message frame: sender prefix at bytes 5-10, ts at 13-16, text at 17."""
    frame = bytearray(16)
    frame[0] = RESP_CONTACT_MSG_V3 if v3 else RESP_CONTACT_MSG
    frame[4:10] = sender_prefix[:6]
    frame[12:16] = u32le(ts)
    return bytes(frame) + text.encode("ascii")


def async_frame(code: int = 0x88) -> bytes:
    if code < ASYNC_MIN:
        raise ValueError("async codes are >= 128")
    return bytes([code, 0])


def _script(replies: Iterable[Optional[bytes]]) -> Iterator[Optional[bytes]]:
    for reply in replies:
        yield reply
    while True:  # once the script is exhausted the radio is silent
        yield None


@dataclass
class Contact:
    pubkey_hex: str
    name: str
    contact_type: int


@dataclass
class ContactSyncResult:
    contacts: list = field(default_factory=list)
    expected: int = 0
    received: int = 0
    completed: bool = False
    stopped_by_async: bool = False
    timed_out: bool = False
    since: int = 0

    @property
    def sendable(self) -> list:
        return [c for c in self.contacts if c.contact_type != CONTACT_TYPE_REPEATER]


def parse_contact_silent(frame: bytes) -> Optional[Contact]:
    if len(frame) < CONTACT_FRAME_MIN_LEN or frame[0] != RESP_CONTACT:
        return None
    name = frame[100:].split(b"\x00", 1)[0].decode("ascii", "replace")
    return Contact(frame[1:33].hex().upper(), name, frame[33])


def sync_contacts(replies: Iterable[Optional[bytes]]) -> ContactSyncResult:
    """Mirror of Sub DoGetContacts."""
    result = ContactSyncResult()
    quiet = 0
    async_streak = 0
    for frame in _script(replies):
        if not frame:
            quiet += 1
            if quiet >= CONTACT_SYNC_QUIET_LIMIT:
                result.timed_out = True
                break
            continue
        quiet = 0
        code = frame[0]
        if code >= ASYNC_MIN:
            async_streak += 1
            if async_streak >= ASYNC_STREAK_LIMIT:
                result.stopped_by_async = True
                break
            continue
        async_streak = 0
        if code == RESP_CONTACTS_START:
            if len(frame) >= 5:
                result.expected = int.from_bytes(frame[1:5], "little")
        elif code == RESP_CONTACT:
            contact = parse_contact_silent(frame)
            if contact and len(result.contacts) < MAX_CONTACTS:
                result.contacts.append(contact)
            result.received += 1
        elif code == RESP_END_OF_CONTACTS:
            if len(frame) >= 5:
                result.since = int.from_bytes(frame[1:5], "little")
            result.completed = True
            break
        # any other non-async code is ignored during sync
    return result


def read_response_skipping_async(script: Iterator[Optional[bytes]]) -> Optional[bytes]:
    """Mirror of Function ReadResponseSkippingAsync$."""
    async_count = 0
    while True:
        frame = next(script)
        if not frame:
            return None
        if frame[0] >= ASYNC_MIN:
            async_count += 1
            if async_count >= ASYNC_STREAK_LIMIT:
                return None
            continue
        return frame


SEND_CONFIRM_MIN_MS = 2000
SEND_CONFIRM_MAX_MS = 15000
CONFIRM_POLL_MS = 300  # ReadFrame$(300) inside WaitForSendConfirmation


def sent_frame(ack: bytes, est_timeout_ms: int = 3000, flood: bool = False) -> bytes:
    """RESP_CODE_SENT as MeshCore companion firmware writes it (10 bytes)."""
    return bytes([RESP_SENT, 1 if flood else 0]) + ack[:4] + u32le(est_timeout_ms)


def confirm_frame(ack: bytes, trip_ms: int = 850) -> bytes:
    """PUSH_CODE_SEND_CONFIRMED as the firmware writes it (9 bytes)."""
    return bytes([PUSH_SEND_CONFIRMED]) + ack[:4] + u32le(trip_ms)


def confirm_wait_ms(sent: bytes) -> int:
    """Wait window DoSendMessage derives from the radio's estimated timeout."""
    wait = int.from_bytes(sent[6:10], "little")
    return max(SEND_CONFIRM_MIN_MS, min(SEND_CONFIRM_MAX_MS, wait))


def wait_for_send_confirmation(script: Iterator[Optional[bytes]], polls: int, ack: bytes) -> str:
    """Mirror of WaitForSendConfirmation(timeoutMs, ackKey$); ``polls`` approximates
    the wait window divided into 300 ms ReadFrame$ attempts."""
    if len(ack) != 4:
        return "no-confirmation"
    async_count = 0
    for _ in range(polls):
        frame = next(script)
        if not frame:
            continue
        if frame[0] == PUSH_SEND_CONFIRMED and len(frame) >= 5 and frame[1:5] == ack:
            return "delivered"
        if frame[0] >= ASYNC_MIN:  # includes confirmations for other messages
            async_count += 1
            if async_count >= ASYNC_STREAK_LIMIT:
                return "interrupted"
        # extra non-async frames are printed and ignored
    return "no-confirmation"


def direct_send_outcome(replies: Iterable[Optional[bytes]], confirm_polls: Optional[int] = None) -> str:
    """Mirror of the response handling in Sub DoSendMessage.

    Returns one of: ``unknown`` (no response; do not retry blindly), ``failed``,
    ``unexpected``, ``untracked`` (accepted but no ACK code to match),
    ``delivered``, ``queued-unconfirmed``, ``interrupted``.
    """
    script = _script(replies)
    frame = read_response_skipping_async(script)
    if frame is None:
        return "unknown"
    code = frame[0]
    if code == RESP_ERR:
        return "failed"
    if code == RESP_OK:
        return "untracked"
    if code != RESP_SENT:
        return "unexpected"
    if len(frame) < 10:
        return "untracked"
    polls = confirm_polls if confirm_polls is not None else -(-confirm_wait_ms(frame) // CONFIRM_POLL_MS)
    outcome = wait_for_send_confirmation(script, polls, frame[2:6])
    return "queued-unconfirmed" if outcome == "no-confirmation" else outcome


def is_real_message(code: int) -> bool:
    return code in (RESP_CONTACT_MSG, RESP_CHANNEL_MSG, RESP_CONTACT_MSG_V3, RESP_CHANNEL_MSG_V3)


@dataclass
class PollResult:
    message: Optional[bytes]
    requests_sent: int
    skipped_non_message: int = 0


def poll_next_message(replies: Iterable[Optional[bytes]]) -> PollResult:
    """Mirror of the polling loop in Sub DoReadNextMessage (after DrainAsyncFrames)."""
    script = _script(replies)
    quiet = 0
    sent = 0
    skipped = 0
    while quiet < POLL_QUIET_LIMIT:
        sent += 1  # SendFrame Chr$(10) each iteration
        frame = next(script)
        if not frame:
            quiet += 1
            continue
        code = frame[0]
        if code >= ASYNC_MIN:
            quiet += 1
        elif is_real_message(code):
            return PollResult(frame, sent, skipped)
        elif code == RESP_NO_MORE_MESSAGES:
            quiet += 1
        else:
            skipped += 1
            quiet += 1
    return PollResult(None, sent, skipped)


def find_contact_name(contacts: list, prefix_hex: str) -> str:
    """Mirror of FindContactName$ (prefix match, first wins)."""
    for contact in contacts:
        if contact.pubkey_hex.startswith(prefix_hex):
            return contact.name
    return "(unknown)"


def contact_message_sender(frame: bytes, contacts: list) -> Optional[str]:
    """Sender name as ParseContactMessageFrame resolves it, or None if too short."""
    if len(frame) < CONTACT_MSG_MIN_LEN:
        return None
    return find_contact_name(contacts, frame[4:10].hex().upper())


def contact_message_text(frame: bytes) -> str:
    return frame[16:].split(b"\x00", 1)[0].decode("ascii", "replace")
