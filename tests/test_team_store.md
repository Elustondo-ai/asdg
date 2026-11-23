# Team specification store tests

[Source](test_team_store.py). Focused tests for listing, preview and token-checked apply in [`cli_team_store`](../scripts/lib/cli_team_store.md). Each test builds a disposable Git project in the system temporary folder and reuses the fixture from [the model tests](test_team_model.md).

Every listing and preview, including those before an apply, runs inside a check that snapshots the whole disposable area, Git internals included, and requires identical paths, bytes, link targets and modification times afterwards.

| Evidence | Coverage |
| --- | --- |
| Empty store and listing | No store folder lists as empty and creates nothing; sessions, subagents and teammates files list in order with unverified provenance; a fresh ID avoids stored ones |
| Exact, deterministic preview | Twelve type and name combinations, including `start`, a path-like name and shell text: equal results twice, the opaque path, the exact bytes, token form, resolved common directory; no store, claim folder or side effect appears |
| Bound inputs | Purpose, type, supplied context, role list, another saved team, a stray file, a claim file and the project binding each change the token; non-text context and a changed project ID are refused |
| Duplicate names | A case variant is `NAME_IN_USE`; a different name is ready; a stored full-width duplicate makes the listing unclean and blocks saving |
| Unreadable stored files | Malformed, non-object, foreign, version 2, mismatched ID, invalid lead, reformatted bytes, a sync conflict copy, an unknown `.json` and a folder are each classified, block saving and keep their bytes; a reformatted file still holds its name |
| Unsafe paths | A symlinked specification, a symlinked store folder, path-like and uppercase IDs, a non-Git folder, a subfolder, a relative root, a symlinked claim and a missing binding are refused; the outside target is untouched |
| Replacement | Identical bytes are `UNCHANGED`; every replacement is `PROVENANCE_UNVERIFIED`, also with a supplied baseline hash; a stale or wrong revision and any present claim add their own conflicts |
| Local agreement | A file with a changed handoff rule, saved in the exact serialization, is not replaced by revision 2 and keeps its bytes; an unchanged read and an unrelated create still work |
| Size limit | A candidate of exactly 262144 saved bytes is ready and lists after saving; one byte more is refused read-only with the caller's object unchanged |
| Linked worktree | The worktree resolves the main repository's common directory and gets a different token |
| Create and read back | For all three types, apply writes exactly the previewed specification and receipt, lists them, then previews as `UNCHANGED`; a used token is refused; unrelated content is intact |
| Revision and receipts | Revision 2 and 3 apply with a matching receipt; a local edit, a missing, malformed, other-root or stale receipt each block; a receipt without its file blocks a create |
| Rejected tokens | Malformed tokens are refused before any lock exists; a stale token, a swapped candidate, changed context and a changed role list are refused, leaving only the empty lock file and its two folders |
| Concurrency | Six threads with normalized-equal names and valid tokens save exactly one team and one receipt; a held lock makes a writer refuse after waiting |
| Symlinked helpers | A symlinked lock folder, lock file, cache folder and receipt file are refused by preview and apply; nothing appears outside |
| Injected failures | A read-back failure on create removes both new files and the created cache folders; a receipt failure on replace restores the prior specification; an unrelated file is untouched, no temporary file remains, and the same token then applies |

All mutation happens in the disposable area. The concurrency evidence is threads in one process on a local filesystem; it shows nothing about crashes, other programs or synced folders. No claim schema, host identity, command, skill or native session is exercised.
