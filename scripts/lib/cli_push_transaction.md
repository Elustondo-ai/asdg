# Recoverable push-replace file changes

[Source](cli_push_transaction.py) applies a previously validated replacement plan without deciding file ownership or granting authorization. The caller supplies exact preimages and verifies the payload before ownership/audit records are published.

![A fixed plan is rechecked under the lock, backed up, applied, verified and recorded with recovery evidence.](../../docs/images/push-replace-flow.svg)

## Responsibilities and collaborators

The transaction owns the cooperative lock at `.asdg/cache/push-replace.lock` and backups under `.asdg/backups/push-replace/<transaction-id>/`. It uses standard-library file operations, `flock`, SHA-256 and [Conflict](cli_files.md); the push-replace planner owns path/category authorization, source integrity and target compatibility.

| Interface | Contract |
| --- | --- |
| `execute(root, plan, verify_callback, preflight_callback=None, wait=10.0)` | Validate preimages/resources, lock, recheck via the caller, save backups, apply payload, call the mandatory verifier, publish designated paths, and verify all realized bytes/modes. Returns identity, state, backup, elapsed wall time, changed paths, verification result and realized hashes. |
| `recover(root, transaction_id, mode='rollback', verify_callback=None, wait=10.0)` | Validate immutable backup content and resume or restore exact recorded states. Resume requires a verifier and is refused after rollback. Repeating a terminal operation preserves the journal; committed resume checks current outputs. |
| `inspect(root, transaction_id)` | Read and checksum-validate manifest, journal and blobs; return desired/before hashes, modes, publication flags and caller verification metadata. No writes. |
| `assert_idle(root)` | Read-only guard refusing unfinished or unverifiable prior transactions, including when a new plan has no changed files. |
| `TransactionFailure` | A Conflict carrying `transaction_id` and `state`; failure may leave a recoverable partial result. |

The plan contains `plan_id`, `changes`, optional `publish_paths` and JSON `verification` metadata. Each change has `path`, `before_sha256`, `before_mode`, `after` bytes or None, and `after_mode`. Absent files have null hashes/modes. Shared-file merge decisions must already be reflected in exact after-bytes.

## Persistence and recovery

Backups contain a checksummed immutable manifest, before/after blobs and an atomically updated journal. Writes fsync file and directory state. Publication paths are deferred until the payload verifier succeeds; all outputs are checked again before COMMITTED, whose journal records actual hashes, modes and verification. Callers retain source-independent verification metadata for recovery.

Ordinary apply failures attempt rollback. Interruption leaves the journal for explicit recovery. Recovery refuses symlinks, hardlinks, traversal, Git metadata, nested repositories and later edits. Existing unfinished or corrupted transactions block new writes. No-op plans create no lock, backup, receipt or event.

A failed backup preparation leaves payload unchanged and reports PREPARATION_INCOMPLETE. With an intact manifest/checksum, rollback can abandon PREPARING or PREPARATION_INCOMPLETE only when every target still matches its exact before-state; partial backups remain retained. A crash before the manifest/checksum is durable or a corrupted backup requires explicit reconciliation. Backup hashes detect corruption, not an attacker who rewrites content and checksums.

The lock protects cooperating processes only. Resource checks estimate available capacity and writable parents; they reserve neither. Arbitrary external writers, operating-system/storage failure beyond fsync guarantees and active native sessions are outside the transaction guarantee. A failed error-journal write reports the last readable durable state and transaction ID. Empty created directories are retained. No hook trust, native runtime verification or Git operation follows from this module.

[Disposable tests](../../tests/test_push_transaction.md) exercise interruption, publication ordering, restoration, stale inputs, unsafe paths and preservation of later edits.
