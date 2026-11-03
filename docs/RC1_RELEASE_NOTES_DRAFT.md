# PicoMesh Pro v0.1.0-rc.1 — DRAFT release notes

**NOT PUBLISHED — release on hold pending CI and physical hardware validation.**

PicoMesh Pro is an MMBasic terminal client for a PicoMite/PicoCalc connected over UART to a compatible MeshCore companion radio. It builds on Vigoleis912/PicoMeshCore.

## Proposed highlights

- Channel listing and selection, with reserved `#public` mapping protection.
- Channel send workflows and explicit distinction between accepted, queued, delivered and unknown send outcomes.
- Local channel name/index mapping export and staged restore, with malformed-file rejection. Backups do **not** contain private channel keys.
- UART framing length checks, partial-frame timeout handling and bounded asynchronous traffic during selected command-response flows.
- Source-level Python regression tests and GitHub Actions workflow.

## Known limitations

- Physical PicoMite/PicoCalc and companion radio compatibility is **not yet verified**.
- Python tests inspect source-level invariants; they do not execute MMBasic or validate radio interoperability.
- Private channel key management and path hash size controls are not confirmed features.
- No verified device screenshots are available yet.

## Before publication

- [ ] Choose and record exact candidate commit SHA.
- [ ] Confirm matching GitHub Actions run succeeded; save test artifact URL.
- [ ] Complete and document real hardware smoke tests.
- [ ] Confirm firmware, wiring and installation instructions.
- [ ] Review GPL-3.0 attribution, README, and privacy of included materials.
- [ ] Obtain explicit owner approval to publish.

See [readiness checklist](RC_READINESS_CHECKLIST.md), [evidence log](RC_EVIDENCE_LOG.md) and [hardware test plan](UART_COMMAND_RESPONSE_HARDWARE_TEST_PLAN.md).

**Do not present this draft as a published or hardware-validated release.**
