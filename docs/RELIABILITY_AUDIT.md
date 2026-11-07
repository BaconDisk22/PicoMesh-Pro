# PicoMesh Pro — source reliability audit

**Audited:** `meshcore.bas` at `4c3c191` (2026-11-07). **Method:** manual read of all 2,735 lines covering timeouts, buffer handling, reconnection behavior and error paths. **Not done:** nothing here was run on a PicoMite or a MeshCore companion. Every finding is a source-reading result and still needs hardware confirmation.

Each finding says how sure we are:
- **Code fact:** visible directly in `meshcore.bas`.
- **MMBasic:** depends on documented PicoMite MMBasic behavior. Check it against the target firmware's manual.
- **Protocol:** depends on the MeshCore companion protocol layout as understood here. Check it against the companion firmware source before fixing.

No code is changed by this audit. Fixes are proposed as separate, small PRs (see the end of this file), and each one should be hardware-tested before any RC.

## Summary

| ID | Severity | Area | Finding | Basis |
| --- | --- | --- | --- | --- |
| R1 | High | Send | Long messages crash the program (string over 255 chars) | MMBasic |
| R2 | High | Send | "Delivered" can be shown for a different message | Protocol |
| R3 | Medium | Contacts | Contacts re-sync before every read and send | Code fact |
| R4 | Medium | UART | 256-byte receive buffer can overflow during contact sync | MMBasic |
| R5 | Medium | Startup | Unset Pico clock is pushed to the radio on every start | Code fact |
| R6 | Medium | Radio config | Radio params and TX power are sent with no range check or confirmation | Code fact |
| R7 | Medium | Channels | Channel scan/import: late replies cascade, and failures are silent | Code fact |
| R8 | Low | Messages | Legacy contact messages (code 7) are parsed with v3 offsets | Protocol |
| R9 | Low | UART | `MAX_FRAME_LEN = 1024` is above what an MMBasic string can hold | MMBasic |
| R10 | Low | UART | One bad frame flushes good frames already buffered (pinned by #79) | Code fact |
| R11 | Low | Send | Fixed 2 s confirmation window; late confirmations are discarded | Code fact / Protocol |
| R12 | Low | Reconnect | No disconnect detection or reconnect guidance | Code fact |
| R13 | Low | Robustness | Smaller hazards: boot read loop, worst-case blocking, by-reference argument, file I/O errors | Code fact / MMBasic |

## Findings

### R1 — Long messages crash the program (High, MMBasic)

MMBasic strings hold at most 255 characters, and building a longer one stops the program with an error. `DoSendMessage` puts 13 bytes in front of the text, and `SendFrame` adds 3 more for the header when it builds `hdr$ + payload$`. The only text limit checked is `MAX_FRAME_LEN - 13` (1011), while `Line Input` accepts up to 255 characters.

- **Direct message:** text of 240–242 chars fails in `SendFrame`. Text of 243 or more fails while `payload$` is being built. The largest text that is safe today is **239** chars.
- **Channel message:** 7-byte prefix, so 246–248 chars fail in `SendFrame` and 249 or more fail while building. The largest safe text is **245** chars.

When it fails, the program stops at the MMBasic prompt with the UART still open, and the menu is gone.

**Proposed fix:** cap direct text at 239 and channel text at 245, or lower if the companion firmware has a smaller text limit (check `MAX_TEXT_LEN` in the firmware). Base the check on the 255-char string limit, not `MAX_FRAME_LEN`. Add source-anchor tests for both caps.

### R2 — "Delivered" can belong to a different message (High, Protocol)

`WaitForSendConfirmation` treats any `PUSH_CODE_SEND_CONFIRMED` (130) as delivery of the message just sent. In the companion protocol, `RESP_CODE_SENT` (6) carries an expected ACK code, and the confirmation push carries the ACK code it is confirming. The source never compares the two. If message A's confirmation arrives late, during message B's wait, the app prints **Delivered** for B even when B was never delivered.

**Proposed fix:** keep the 4-byte expected ACK from the `RESP_CODE_SENT` frame. Report "Delivered" only when the push's ACK matches, and ignore or log other confirmations. Confirm the byte offsets against the firmware first.

### R3 — Contacts re-sync before every read and send (Medium, Code fact)

`EnsureContactsLoaded` syncs only when `contactsLoaded = 0`, but nothing in the file ever sets `contactsLoaded` to 1. So every **Read next message** and every **Send message** runs a full `DoGetContacts` first. That costs seconds with many contacts, and each run starts with `FlushInput`, which throws away any frames already waiting, such as message-waiting pushes or late confirmations.

**Proposed fix:** set `contactsLoaded = 1` only when a sync completes (`RESP_END_OF_CONTACTS` received). Leave it at 0 after a timeout or an async-flood stop, so the next operation retries.

### R4 — Receive buffer can overflow during contact sync (Medium, MMBasic, needs hardware)

`Open "COM2:115200" As #1` uses the default serial receive buffer, which the PicoMite manual gives as 256 bytes. At 115200 baud that fills in about 22 ms. Contact sync streams 148-byte frames back to back, and the interpreted `ReadFrame$` loop has to keep up, so a few frames arriving together are enough to overflow it. Lost bytes break framing, and then the R10 flush behavior discards more.

**Proposed fix:** open the port with a larger buffer, for example `Open "COM2:115200,4096" As #1`. Check the exact syntax and the maximum size for the target firmware. During the hardware test, compare received and expected contact counts with 50+ contacts.

### R5 — Unset Pico clock is pushed to the radio (Medium, Code fact)

`DoInitialize` runs at every start and calls `DoSyncDeviceTime`, which sends `Date$`/`Time$` to the radio with no sanity check. A PicoMite whose clock hasn't been set reports 2000-01-01. Depending on the firmware, the radio either rejects that (the user sees "Time sync ERROR" every start) or accepts it, which puts radio timestamps back to 2000. Outgoing direct and channel messages also use the Pico clock for their timestamps, so they can carry 2000-era dates either way.

**Proposed fix:** skip the time sync, with a clear message, when the Pico year is before 2024. Ask before pushing a time that is earlier than the radio's current time (`DoGetDeviceTime` already reads it).

### R6 — Radio params and TX power: no range check or confirmation (Medium, Code fact)

`DoSetRadioParams` accepts any frequency and bandwidth above 0, and sends the change right away with no confirmation. A typo such as `9150` or `91.5` reconfigures the radio, and the radio saves the setting. SF, CR and TX power are not required to be whole numbers. TX power is checked against 0–30, not against the `gMaxTxPowerVal` the radio reported. A wrong frequency can take the node off the mesh, and can mean transmitting outside the permitted band.

**Proposed fix:** check frequency against the radio's band (and optionally the region), and bandwidth against the LoRa set (7.8–500 kHz). Require whole numbers for SF, CR and power, and cap power at `gMaxTxPowerVal` when it is known. Show a summary and require typing `APPLY` before sending.

### R7 — Channel scan/import: cascading mismatches, silent failures (Medium, Code fact)

`DoScanRadioChannels` and `DoSyncRadioChannels` query slots 0–7 back to back without flushing between queries. If one reply arrives after its timeout, it gets read as the reply to the next query. The index check correctly rejects it, but the next slot's reply then lags in turn, and later slots can all mismatch. Import counts only invalid names. No response, rejection, index mismatch, a short frame and "list full" are all skipped silently, so the summary can say "Added 0" with no reason.

**Proposed fix:** call `FlushInput` (or drain) before each slot query. Count and report each skip reason in the import summary.

### R8 — Legacy contact messages parsed with v3 offsets (Low, Protocol)

`ParseContactMessageFrame` uses the v3 layout (sender prefix in bytes 5–10, text from byte 17) for both code 16 and code 7. In the legacy code-7 layout the prefix starts at byte 2 and the text at byte 14, so a code-7 frame would show the wrong sender and lose the first 3 characters of the text. The app asks for protocol v3 in `DEVICE_QUERY`, so current firmware should send code 16 and this path is rarely used. Channel messages already handle both layouts correctly. The #78 test helper copies the v3 layout for code 7 as well, matching the source as written.

**Proposed fix:** branch on the code the same way `ParseChannelMessageFrame` does, after confirming the code-7 layout.

### R9 — `MAX_FRAME_LEN` is larger than an MMBasic string (Low, MMBasic)

`ReadFrame$` accepts lengths up to 1024, but `Input$(n)` and string variables are limited to 255. With a 256-byte receive buffer, a corrupt length of 256 can pass the wait loop, and the `Input$` call then stops the program. Larger lengths time out and flush, which is safe. Companion frames are much shorter in practice (172 bytes or less).

**Proposed fix:** set the receive limit to 255, or to the companion's maximum frame size, and update the Python models and anchors to match.

### R10 — One bad frame flushes good buffered frames (Low, Code fact)

`ReadFrame$` calls `FlushInput` on every failure after a start byte. An invalid length, or a stray `>` in noise, therefore also drops valid frames already in the buffer. #79 pins this behavior in `test_channel_uart_interruption.py`.

**Proposed fix:** on failure, drop only the bad start byte and search for the next `>`, instead of clearing the whole buffer. Update the #79 tests to assert recovery.

### R11 — Fixed confirmation window (Low)

`DoSendMessage` waits a fixed 2,000 ms for delivery. `RESP_CODE_SENT` also carries an estimated timeout (Protocol), and flood-routed messages often take longer than 2 s, so "Queued, no delivery confirmation yet" will be common. Confirmations that arrive later are dropped by `HandleAsyncFrame`, or wiped by R3's flush, so the user never learns the message did arrive.

**Proposed fix:** use the radio's estimated timeout, with a sensible cap. After R2 is fixed, report late matching confirmations when they are seen.

### R12 — No disconnect detection or reconnect guidance (Low, Code fact)

The port is opened once at start. If the radio resets or loses power, every command just times out with its own message, and nothing suggests **Device → Initialize radio**.

**Proposed fix:** count consecutive no-response results. After about 3, print a hint to check wiring and power and run Initialize radio.

### R13 — Smaller robustness notes

- **Boot read loop (Code fact):** `ReadRawBytes 1000` at startup reads until 1 s of silence. A radio that keeps sending (debug logging, a stuck port) keeps the program there forever. Add an overall deadline.
- **Worst-case blocking (Code fact):** `ReadResponseSkippingAsync$` gives each read the full 3 s timeout and allows 20 async frames, so it can block for about 63 s before giving up. Use one overall deadline.
- **By-reference argument (MMBasic):** `UnixToDate$` changes its parameter `t`, and MMBasic passes plain variables by reference. Today's callers pass `Int(...)` or call it after the payload is built, so nothing breaks yet. Copy `t` to a local before changing it.
- **File I/O errors (MMBasic):** export and restore have no `On Error` handling. A write-protected or missing drive stops the program. Export also overwrites the only `CHANNELS.TXT` in place, so a power cut mid-write loses the previous backup. Restore's validation rejects a corrupt file, so live channels stay safe.
- **Test helper wording (fixed here):** the #78 helper named contact type 2 "room". In MeshCore, type 2 is a repeater (rooms are type 3), and the source correctly leaves repeaters out of the sendable list. This PR renames it in the tests. `ShowContactsList` marks type 2 as `R`, which fits "repeater".

## What already holds up

- Every UART wait has a timeout, and every polling loop is bounded (quiet-loop limits, async-streak limits, drain loop limit).
- Unknown and failed send outcomes are reported honestly, including "status unknown, do not retry blindly".
- Channel secrets are never printed, stored or exported. Restore stages and validates the whole file before changing live channels.
- Input checks cover menu selections, channel names and indexes, and the reserved `#public` name.

## Suggested follow-up PRs (each small, each hardware-tested before RC)

1. R1 + R9: string-safe text caps and receive limit. Small, and removes a crash.
2. R3: set `contactsLoaded` on a completed sync. One line plus a test.
3. R2 + R11: match confirmations to ACK codes and use the radio's timeout. Check the protocol offsets first.
4. R5 + R6: clock sanity check, and radio-parameter validation with confirmation.
5. R4 + R10: larger receive buffer and resync on the next `>`. Needs the most hardware validation.
6. R7, R8, R12, R13: channel query hygiene, legacy message offsets, reconnect hint, smaller cleanups.

Hardware testers should watch for R1, R2, R3, R4 and R5 in particular. They can be reported with the hardware test issue form.
