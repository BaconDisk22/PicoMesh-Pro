# PicoMesh Pro — v0.1.0-rc.1 readiness checklist

This checklist records release gates, not claims of completed hardware testing.

## Source and documentation
- [ ] All intended PRs merged and `main` reviewed for accidental regressions
- [ ] GitHub Actions static checks green on the exact candidate commit
- [ ] README accurately reflects implemented features and known limitations
- [ ] GPL-3.0 attribution and upstream source retained
- [ ] No private channel keys, credentials, or personal radio data included
- [ ] Installation and UART wiring instructions reviewed for the target PicoMite firmware

## Hardware acceptance (must be observed on real devices)
- [ ] PicoMite/PicoCalc starts the program and connects to a MeshCore companion over UART
- [ ] Device query and clock synchronization work with normal and asynchronous responses
- [ ] Contact and channel message reading works without hangs
- [ ] Channel sending works, with acknowledgement/queued/unknown outcomes distinguished
- [ ] Reserved #public mapping cannot be accidentally overwritten
- [ ] Local channel export and restore work; malformed backups leave mappings unchanged
- [ ] Disconnect, partial frame, timeout and reconnect scenarios documented and tested
- [ ] No crashes or data loss during a practical smoke-test session

## Upstream contribution (independent of release)
- [ ] Confirm current Vigoleis912/PicoMeshCore source and contribution guidance
- [ ] Identify one narrow, compatible improvement
- [ ] Compare patch against current upstream code and verify licensing
- [ ] Obtain owner approval before submitting an upstream PR

## Candidate publication
- [ ] Record hardware and static-test results against a specific commit SHA
- [ ] Write release notes, known limitations and installation steps
- [ ] Publish `v0.1.0-rc.1` only after the release gates are reviewed

See `docs/UART_COMMAND_RESPONSE_HARDWARE_TEST_PLAN.md` and `docs/CHANNEL_RESTORE_HARDWARE_TEST_PLAN.md` for scenario details.
