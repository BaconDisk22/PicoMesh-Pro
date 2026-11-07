# PicoMesh Pro — release verification procedure

This procedure applies to a **specific commit** proposed for `v0.1.0-rc.1`. Do not treat source-level tests as PicoMite hardware validation.

## 1. Confirm the candidate

1. Open the [repository commits](https://github.com/TheLogsAreScreaming/PicoMesh-Pro/commits/main) and copy the full SHA for the intended candidate.
2. Confirm the expected pull requests are merged and no unreviewed changes landed afterward.
3. Record the SHA in [RC_EVIDENCE_LOG.md](RC_EVIDENCE_LOG.md). If `main` changes, repeat the CI verification against the new SHA.

## 2. Verify GitHub Actions

1. Open [GitHub Actions](https://github.com/TheLogsAreScreaming/PicoMesh-Pro/actions) and select **Source-level regression checks**.
2. Find the run whose commit SHA exactly matches the candidate. If none exists, use **Run workflow** on the appropriate branch, or investigate why Actions are not running. Do not mark CI green without a completed matching run.
3. Check that the **source-regressions** job has a **success** conclusion. Inspect failed or cancelled steps rather than assuming they passed.
4. Download the **source-test-results** artifact and review the unittest output for failures/errors. Record the run URL, SHA and conclusion in the evidence log.
5. Remember that these tests inspect source text; they do not compile or execute MMBasic on PicoMite hardware.

## 3. Run hardware acceptance

Follow [UART command/response test plan](UART_COMMAND_RESPONSE_HARDWARE_TEST_PLAN.md) and [channel restore test plan](CHANNEL_RESTORE_HARDWARE_TEST_PLAN.md). Record the PicoMite/PicoCalc firmware, companion firmware, wiring, UART baud rate, observed results and any redacted logs. Confirm at minimum startup, contacts, direct/channel messages, partial frames, disconnect/reconnect and backup/restore.

Do not include private channel keys, personal contact data, or identifying radio traffic in uploaded evidence.

## 4. Release decision

Review [RC readiness checklist](RC_READINESS_CHECKLIST.md) and [RC evidence log](RC_EVIDENCE_LOG.md). If any required gate remains unverified, retain **HOLD**. Draft release notes only after evidence is collected, and publish `v0.1.0-rc.1` only with explicit owner approval.
