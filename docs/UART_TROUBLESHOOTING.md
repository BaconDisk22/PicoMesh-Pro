# UART troubleshooting for PicoMesh Pro testers

**Safety:** Verify pinout, logic voltage, common ground and power requirements for your exact PicoMite/PicoCalc and MeshCore companion radio. Do not assume one board's wiring applies to another. Never connect incompatible voltage levels.

## Startup reports commands finished but no radio responses

- This message means startup commands were attempted, **not** that radio initialization succeeded.
- Check the radio is powered and running a compatible UART companion firmware.
- Compare the program's `COM2:115200` setting with your board pin mapping and the companion's UART baud rate.
- Check TX/RX crossover and common ground using the actual board documentation.
- Run a read-only device query and record the exact response or timeout.

## Contacts stop loading

- The contact synchronization routine can stop after repeated quiet timeouts or sustained asynchronous traffic.
- Treat a partial contact list as incomplete; retry when traffic subsides.
- Do not interpret the number of stored contacts as proof that the full list synchronized.

## Direct messages show unknown or unconfirmed status

- **Unknown** means no definitive send response was observed. Do not retry blindly: the radio may have accepted the message.
- **Queued** means the request was accepted for sending, not necessarily delivered.
- A missing delivery confirmation does not prove failure. Verify through the recipient or other independent evidence before retrying.

## Malformed frames or disconnects

- Record the command, frame symptoms, firmware versions and whether the issue is reproducible.
- Test recovery with read-only queries first. Avoid repeated sends while the outcome is unknown.
- For a repeatable failure, include a redacted log and exact source commit SHA in an issue.

## What to include in a bug report

- Exact PicoMesh Pro commit SHA and firmware versions
- Board and radio model, UART port and baud rate
- Expected vs observed behavior and reproduction steps
- Whether a power cycle or reconnect changes the result
- Redacted serial output (remove private keys, contact IDs, message text and precise location)

See [UART hardware test plan](UART_COMMAND_RESPONSE_HARDWARE_TEST_PLAN.md) and [RC evidence log](RC_EVIDENCE_LOG.md). Hardware behavior is not yet certified.
