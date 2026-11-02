# UART command-response hardware test plan

These checks require a PicoCalc/PicoMite running `meshcore.bas` and a MeshCore companion radio connected over UART. Python static checks alone cannot verify UART behavior.

## Before testing
- Back up existing local channel mappings and record the firmware versions and wiring.
- Use a test radio and avoid sending repeated messages during uncertain delivery states.
- Record the command, expected result, actual output, and any observed radio disconnect.

## Scenarios
1. **SET_DEVICE_TIME:** Trigger time sync while unsolicited async frames arrive. Confirm an async event is handled and the time-sync acknowledgement is still interpreted correctly.
2. **GET_DEVICE_TIME:** Query device time with an async event arriving first. Confirm the response type is validated and the timestamp displayed is plausible.
3. **DEVICE_QUERY:** Query device info during async activity. Confirm the expected device-info response is parsed rather than the async event.
4. **No radio response:** Disconnect the radio and issue each command. Confirm it exits without hanging and reports a missing response.
5. **Continuous async traffic:** Generate many unsolicited frames during a response wait. Confirm the existing 20-frame cap stops the wait and that the UI remains responsive.
6. **Partial frame:** Interrupt the UART stream mid-header and mid-payload. Confirm the reader eventually returns; note any buffered data loss.
7. **Recovery:** Reconnect the radio and repeat the commands; confirm no stale bytes are interpreted as successful responses.

## Release gate
Do not mark these scenarios passed until observed on physical hardware. Record results and investigate failures before a release candidate.
