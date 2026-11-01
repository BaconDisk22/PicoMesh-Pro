# PicoMesh Pro — PicoMite channel backup validation

> **Not yet hardware verified.** Do not enable automatic startup restore until these checks pass on the actual PicoMite/PicoCalc firmware.

## Prerequisites
- PicoMite/PicoCalc running the target MMBasic firmware
- A backup of the current `meshcore.bas` and any existing `CHANNELS.TXT`
- A MeshCore companion radio connected over UART for radio read/import checks
- A spare or test channel; never experiment with irreplaceable channel settings

## Compile and file I/O smoke test
1. Load `meshcore.bas` on PicoMite and confirm it parses without syntax errors.
2. Verify `DIR$()`, `EOF(#2)`, `LINE INPUT #2`, `OPEN ... FOR INPUT/OUTPUT`, and local arrays declared as `Local stagedName$(MAX_CHANNELS)` are accepted by your firmware.
3. Check `CHANNELS.TXT` is created on the expected drive, and opening file #2 does not collide with other app file handles.
4. If any syntax or file error occurs, **stop** and record the exact firmware version and error. Do not enable automatic restore.

## Manual backup round trip
1. In Channels, list the starting local mappings.
2. Add a temporary mapping for radio slot 1 (if free), using a short printable name.
3. Choose option 8, type `EXPORT`, and inspect `CHANNELS.TXT`. It must start with `PICOMESH-CHANNELS-V1` and contain lines like `0|#public`. It must contain **no private keys**.
4. Remove the temporary local mapping using option 7 and the `REMOVE` confirmation.
5. Choose option 9 and type `RESTORE`. Confirm the temporary mapping returns and all indexes match.
6. Restart the app and confirm that **automatic** restore does not happen yet.

## Rejection and safety checks
For each test, save a separate backup of the good file, edit `CHANNELS.TXT`, then attempt option 9. The existing local list must remain unchanged when restore rejects the file.

| Test file condition | Expected |
| --- | --- |
| Missing file | Friendly not-found message |
| Wrong or missing version header | Reject |
| Duplicate radio index | Reject |
| Index outside 0–7 | Reject |
| Missing `0|#public` | Reject |
| Index 0 named something other than `#public` | Reject |
| More than 8 mappings | Reject |
| Empty name or name longer than 32 bytes | Reject |
| Name containing a pipe delimiter or control character | Reject |
| Cancel confirmation | No changes |

## Radio and privacy checks
- Export and restore must never issue a radio configuration write.
- Check terminal output and exported file for unintended private channel key disclosure.
- The local list stores names and radio indexes only; a restored mapping is **not** evidence that the radio has the corresponding channel configured.
- Do not rely on GET_CHANNEL response code/offset assumptions until verified against the companion firmware.

## Record results
Document hardware model, MMBasic firmware version, companion firmware version, exact steps, expected vs actual behavior, and any errors. Attach sanitized output only. **Never attach private keys or full unredacted radio responses.**

## Release gate
Automatic startup loading should remain disabled until syntax, file round trip, rejection behavior, and radio safety checks are confirmed on real hardware.
