# Code-review record

Review: one read-only fresh-context code reviewer, base 319d4ca, reviewed implementation through c2c114a. Requirements: docs/requirements.txt, architecture.md and the implementation plan. This file summarizes the review; it is not presented as a native dialogue export.

No Critical findings. Two Important findings were reproduced and fixed:

1. An expired upload could write the shared source key and reset a newer upload's state. Fix: unique source key per attempt, lease-conditional completion/cleanup and receiving heartbeat.
2. A stale worker could overwrite the shared published MP4/thumbnail even though its metadata update lost the lease. Fix: immutable output keys per attempt, publish only by compare-and-set on the current lease, discard unpublished output when ownership is lost.

Regression evidence: tests/test_recovery_races.py first produced 3 failures, then passed with the complete 37-test PostgreSQL suite. These tests deliberately schedule a newer attempt between actual S3 I/O and old attempt completion, checking authoritative metadata and media bytes.

Reviewer found no straightforward privacy/CSRF/role-injection defect. This is a review observation, not a security certification. No Minor findings were deferred.

Final reconciliation with the literal employer specification removed the earlier documented staff exception for private playback. Moderator/admin now need an owner grant, and moderation reports redact private metadata without that grant. Three additional regressions first failed and then passed; the complete native PostgreSQL suite now has 40 passing tests. The earlier reviewer treated the exception as intentional, so this policy correction was made by the parent against the binding original specification.

Behaviors the reviewer did not independently judge: actual clean Ubuntu execution, production TLS/backups/high availability/adaptive streaming, deliberately documented moderator access to private content, final documentation/provenance packaging, and rerunning the parent's shared-database tests. The parent owns their validation and records the actual outcome in docs/verification.md.

## Follow-up: PostgreSQL container lifecycle

After the user requested continued work, a second read-only reviewer inspected the focused change against base 8bfaba4: PostgreSQL init in both Compose files, the real-container continuity regression, CI and its supporting documentation. The actual invocation is captured in db-lifecycle-review-invocation.json; the complete native reviewer session is kept in the separate user-review archive.

The reviewer accepted the reproduced mechanism: the exact orphaned probe PID appears in the RED PostgreSQL crash log, and a persistent SQL witness connection is lost. With docker-init as PID 1 the same connection survives the probe's exit2. The historical first-run PID was not captured, so its identity remains an inference in the documentation.

One Important finding: witness teardown failure could skip Compose cleanup and mask the original error. Fixed with independent project teardown and preservation of the primary failure; three fault-injection cases observed RED then GREEN. One Minor finding: simultaneous invocations could share a fixed diagnostic project. Fixed with a random project suffix. The reviewer rechecked both fixes and reported no remaining Critical/Important/Minor findings.

The reviewer did not run shared Docker tests or judge the complete assignment audit. Final native/Linux suites, actual app/DB restart and archive verification remain the parent's work, with observed results in docs/verification.md.
