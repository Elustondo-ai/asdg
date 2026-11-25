# Project Plan Sync coordinator

[Source](cli_plan_sync.py) implements the explicit [planning sync workflow](../../docs/project-plan-sync.md).

| Responsibility | Collaborator |
| --- | --- |
| Verify Git origin, branch and local cache bytes; pin a preview digest | Git and fixed worktree-local paths |
| Compare last synchronized fields with local and remote edits | [Three-way merge](cli_plan_merge.md) |
| Read, create and update shared planning records | [GitHub adapter](cli_plan_github.md) |
| Journal one remote mutation at a time and verify readback | Atomic JSON writes and POSIX worktree lock |

`synchronize(root, repository=None, project_number=None, bootstrap_ref=None, apply=False, expected_plan=None, resume=False, abandon=False, acknowledge_uncertain=False, api=None)` returns a preview, conflicts, verified completion, unchanged or abandoned result. `render` produces plain terminal output. API injection supports isolated tests.
Preview reads only; exact-plan apply rechecks Git binding, cache bytes and the complete remote snapshot. The worktree lock serializes local writers; it is not a cross-machine lock. GitHub field updates have no atomic compare-and-swap, so concurrent writes between read and update remain a documented limitation.
The structured cache is `docs/asdg/07-planning/project-plan-cache.json`; prose notes and all unrelated files stay untouched. Optional bootstrap reads that exact file from a pinned local commit without switching or updating branches. Origin must match the selected github.com repository.
The ignored `.asdg/cache/project-plan-sync/journal.json` retains original cache bytes, scope, snapshots, pending operations and completion evidence. A known completed creation establishes a provisional baseline in the journal; the visible cache advances only after all remote changes verify. Nothing deletes issues or rolls back remote work.
Resume checks the original worktree/revision and cache, then observes any uncertain mutation before proceeding within recorded operation targets and values. Confirmed request rejection permits retry; an unobserved create is never repeated automatically. Exact-plan abandonment archives evidence and preserves local/remote changes for a fresh plan; abandoning an unknown outcome requires separate explicit human acknowledgement. Local edits are never overwritten for recovery.
Stores reject symlinks and hard links, use atomic replacement and fsync; locking currently requires macOS/Linux. `Conflict` and standard I/O errors propagate to the CLI's JSON/plain error handler. Tokens never enter the journal.
CLI invocation and native skill discovery are separate from tests. See [transaction tests](../../tests/test_plan_sync.md) for simulated coverage; no live GitHub acceptance is implied.
