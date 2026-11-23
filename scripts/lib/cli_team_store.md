# Team specification store: listing, preview and apply

[Source](cli_team_store.py). The saved-team store under [team workflows](../../00-governance/docs/team-workflows.md): `.asdg/teams/specs/<opaque-id>.json`. Listing and preview write nothing. Apply writes one specification and its receipt under one lock. No command calls this module yet.
Shape rules come from [`cli_team_model`](cli_team_model.md); file writes reuse [`cli_files`](cli_files.md).

| Interface | Responsibility |
| --- | --- |
| `project(root)` | Evidence for where the store lives: resolved root, Git common directory as Git reports it, project ID and binding hash. |
| `scan(root, *, role_ids, coordinator)` | Every stored file, classified. `teams` holds files valid in shape and saved serialization, each marked `provenance: UNVERIFIED`. |
| `preview(root, candidate, *, role_ids, coordinator, context=None)` | Outcome, token, the exact specification and receipt bytes, both `effects` and the `helpers` apply would use. |
| `apply(root, candidate, token, *, role_ids, coordinator, context=None, wait=10.0)` | Saves only what an identical fresh preview shows. |
| `write_lock(common, wait=10.0)` | The one cooperative lock, `<git-common-dir>/asdg/teams/write.lock`. Claim transitions must use it too. |
| `receipt_bytes`, `receipt_state` | The receipt this writer records, and whether the one on disk is exactly that. |
| `run_state(common)`, `unused_team_id(root)`, `spec_bytes(spec)` | Uninterpreted claim state; a fresh opaque ID; the saved serialization, which shows format and never origin. |

## Outcomes

`preview` returns `READY` with a token, `UNCHANGED` with none, or `CONFLICT` with none and a list of codes. An invalid candidate, one over 262144 saved bytes, an unsafe or symlinked specification, receipt or lock path, and an unusable project raise `Conflict`.

| Code | Meaning |
| --- | --- |
| `STORE_NEEDS_RECONCILIATION` | A stored file is malformed, foreign, of another version, invalid, not in the saved serialization, a symlink, not a file, too large or an unknown `.json`. Every save waits. |
| `DUPLICATE_NAMES`, `NAME_IN_USE` | Two stored teams, or the candidate and another team, share a normalized name. |
| `PROVENANCE_UNVERIFIED` | A replacement whose receipt is missing, unreadable or not exactly the record for the stored revision and bytes. A supplied hash does not lift this. |
| `RECEIPT_PRESENT` | A new team whose ID already has a receipt. |
| `REVISION`, `STALE_REVISION` | A new team must be revision 1; a replacement must be the stored revision plus one. |
| `RUN_STATE_UNPROVEN`, `RUN_STATE_UNREADABLE` | A replacement while the claim is active, not a valid claim, or has another file beside it; a clean `RELEASED` tombstone reads as `INACTIVE` and does not block. A claim path that is a symlink or not a regular file. |

## Receipt

`.asdg/cache/teams/spec-writes/<opaque-id>.json` records schema, project ID, root, Git common directory, team ID, revision and the hash of the bytes this writer saved. It is local write evidence. It is not approval, role authority or protection against someone who edits both files. A fresh clone or cleared cache has none, so replacements there stay blocked; adoption is a later, separately reviewed step.

## What the token binds

A hash with no clock or random input over: filesystem evidence (root, common directory, binding, every store entry, target and receipt hashes, claim state), the candidate, both effects, the helper locations, and `supplied_unverified` (role list, coordinator, optional context labels, which prove nothing about a source or runtime).

## Apply, and its limits

Apply takes the lock, recomputes the preview from disk and the caller's current inputs, requires the identical token, checks that the bytes about to be replaced are the previewed ones, writes the specification then the receipt, and reads both back. A waiting writer therefore sees the earlier save and is refused.

- A refused apply can leave the lock file and its two folders. The lock is empty and reused; nothing else is left.
- The lock is advisory `flock`. It does not stop an editor, a sync client or any program that ignores it, and it is unproven on network or synced filesystems. Without `fcntl`, apply refuses.
- The two files are not one atomic transaction. An ordinary failure rolls back this writer's own changes and created folders. A crash between the writes leaves a specification without its matching receipt, which reads as `PROVENANCE_UNVERIFIED`, and may leave a `.asdg-tmp-*` file.
- Claim content is still uninterpreted, and provenance fields are checked for shape only.
