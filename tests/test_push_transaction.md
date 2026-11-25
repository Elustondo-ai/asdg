# Push-replace transaction acceptance tests

[Source](test_push_transaction.py) tests the [transaction lifecycle and interface](../scripts/lib/cli_push_transaction.md) using temporary directories only. No client repository, native session or host identity is used.

![Fault injection tests each transition between verified inputs, deterministic plans, writes and execution evidence.](../docs/images/push-replace-flow.svg)

| Scenario | Evidence |
| --- | --- |
| No-op | No lock, backup, ownership receipt or event is created. |
| Publication order | Payload exists before verification; receipts remain old until it returns. Final journal includes actual hashes, modes, verification and elapsed time. |
| Fresh preflight | Byte and permission changes invalidate preimages; changes made inside the caller’s locked preflight are rechecked. |
| Verification failure | Modified and deleted files are restored, new files removed, and original permissions retained. |
| Interruption | Injected interruption during payload writing leaves a journal that can resume without source files or restore before-images. |
| Publication interruption | A crash after receipt publication but before COMMITTED can resume verification and finish. |
| Later user edit | Recovery blocks all restoration when any file matches neither recorded state. |
| Backup damage | Modified manifest checksums or blobs block recovery. Incomplete preparation can be abandoned only against exact unchanged preimages; partial backups remain. |
| Recovery idempotence | Repeating COMMITTED resume or ROLLED_BACK rollback preserves journal bytes and modification time; committed resume refuses later edits. |
| Preparation interruption | Valid manifest without its first journal can be abandoned; a changed target blocks abandonment. |
| Resource/error failure | Capacity and permission checks fail before mutation; failure to persist an error journal still reports recovery identity and durable state. |
| Unsafe paths | Traversal, symlinks, hardlinks, Git metadata, nested repositories and transaction-control targets are refused. |
| Lock and pending operation | A competing lock or unfinished prior transaction blocks a new apply, including a nominal no-op; read-only idle checks detect it. |

`PushTransactionTests` builds fixture files and exact plans. Fault injection patches internal writes/journal transitions; no hidden CLI flags weaken production behavior. Tests use the same `execute`, `inspect` and `recover` entry points as the caller.

Run `python3 -B -m unittest discover -s tests -p test_push_transaction.py -v` from the canonical root. These tests establish file behavior under injected failures; they do not simulate physical disk failure or prove native Claude Code/Codex behavior.
