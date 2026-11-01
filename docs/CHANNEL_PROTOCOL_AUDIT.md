# Channel protocol audit — PicoMesh Pro

## Confirmed from `meshcore.bas`
- `MAX_CHANNELS = 8` is a **local list capacity**, not proof of radio channel capacity.
- The local list initially maps `#public` to radio channel index 0.
- The channel send routine constructs a payload starting with command byte 3, then byte 0, then the chosen channel index, followed by a four-byte little-endian Unix timestamp and message text.
- The response handling recognizes codes 0, 1 and 6.
- Incoming channel messages are decoded with index-based name lookup, including a distinct code-17 layout.
- `DoAddChannel` only changes in-memory name/index arrays. It does **not** send a channel-configuration command to the radio.
- `channelKey$` and `channelPrefix$` arrays are declared, but the add-channel routine does not populate them.

## Important gaps
1. Establish the supported MeshCore companion firmware version and its authoritative UART protocol definitions.
2. Verify channel query and set commands, their exact wire layouts, acknowledgements and error handling.
3. Determine whether keys are stored/configured on the radio or the host, and how to avoid logging secrets.
4. Establish channel capacity, index constraints and channel names from the radio rather than assuming the local list is authoritative.
5. Confirm whether path hash size is configurable through companion commands and which firmware versions support it.
6. Check byte-length limits, timestamp handling and response framing before adding transmissions.

## Implementation sequence
- **A. Read-only discovery:** query radio capabilities and channel metadata, if documented and supported; handle timeouts and unsupported firmware.
- **B. Synchronization:** map radio-provided channels into local state, preserving a fallback to `#public`.
- **C. Configuration:** guarded channel provisioning with explicit confirmation; never print private keys.
- **D. Routing:** implement path hash size only with documented command and compatibility checks.
- **E. Verification:** parser fixtures, controlled UART captures, PicoMite syntax checks, and hardware regression tests.

## Test status
This document is a static source audit. No hardware tests or new radio commands have been executed.
