# PicoMesh Pro — release evidence log

Use this form for the exact commit proposed for `v0.1.0-rc.1`. A green source-level test workflow is **not** evidence that the MMBasic program runs on hardware. Leave fields **NOT TESTED** until actual evidence is available.

## Candidate identity

- Candidate commit SHA: **NOT SELECTED**
- Date / tester: **NOT RECORDED**
- PicoMite/PicoCalc model and firmware: **NOT RECORDED**
- MeshCore companion model and firmware: **NOT RECORDED**
- UART port, baud rate and wiring: **NOT RECORDED**

## Automated checks

- GitHub Actions run URL: **NOT VERIFIED**
- Commit SHA shown in run: **NOT VERIFIED**
- Job conclusion: **NOT VERIFIED**
- Test suite: `python -m unittest discover -s tests -v` (source-level checks only)
- Failures and follow-up issues: **NOT RECORDED**

## Hardware checks

| Scenario | Result | Evidence / notes |
| --- | --- | --- |
| Program loads on PicoMite/PicoCalc | NOT TESTED | |
| UART connection and device query | NOT TESTED | |
| Clock sync and APP_START | NOT TESTED | |
| Contact synchronization with async frames | NOT TESTED | |
| Direct send, accepted/unknown/delivery feedback | NOT TESTED | |
| Channel list, #public mapping and channel send | NOT TESTED | |
| Channel export/restore and malformed backup | NOT TESTED | |
| Partial UART frames, timeout and recovery | NOT TESTED | |
| Disconnect/reconnect and extended smoke test | NOT TESTED | |

## Release decision

- Release gate owner: **NOT RECORDED**
- Blocking issues: **NOT ASSESSED**
- Decision: **HOLD — pending evidence and approval**

Do not publish an RC or represent the hardware as validated until these fields have been completed with real results. Follow `docs/RC_READINESS_CHECKLIST.md` for the release gates.
