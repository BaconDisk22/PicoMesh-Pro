# PicoMesh Pro — release evidence log

Use this form for the exact commit proposed for `v0.1.0-rc.1`. A green source-level test workflow is **not** evidence that the MMBasic program runs on hardware. Leave fields **NOT TESTED** until actual evidence is available.

## Candidate identity

- Candidate commit SHA (CI-verified baseline): `eccf8d517b6d6470a1d98faa8c2896ee550499e4` (reverify if candidate changes)
- Date / tester: **NOT RECORDED**
- PicoMite/PicoCalc model and firmware: **NOT RECORDED**
- MeshCore companion model and firmware: **NOT RECORDED**
- UART port, baud rate and wiring: **NOT RECORDED**

## Automated checks

- GitHub Actions run URL: https://github.com/TheLogsAreScreaming/PicoMesh-Pro/actions/runs/42320456867 (`push` on `main`)
- Commit SHA shown in run metadata: `eccf8d517b6d6470a1d98faa8c2896ee550499e4` (`main`, merge of #81)
- Job conclusion: **SUCCESS** (`source-regressions`; all reported steps succeeded)
- Test suite: `python -m unittest discover -s tests -v` (source-level checks only)
- Test log artifact: `source-test-results` (artifact ID `13552214062`, downloaded and reviewed 2026-11-06: 114 tests, 0 failures, 0 errors, `OK`; 56 prior + 28 session scenarios #78 + 25 channel/UART interruption #79 + 5 issue-form checks #81)
- Superseded baselines: run 41754015177 at `2065f65c1d3c3aaa02f584f46efc0401e6f4fc2d` (56 tests, `OK`); run 41743741668 at `13dc8221ce0edc47622d0777fb5d51896d69ad86` (49 tests, `OK`)
- Failures and follow-up issues: **NONE REPORTED BY JOB** (hardware issues not assessed)

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
