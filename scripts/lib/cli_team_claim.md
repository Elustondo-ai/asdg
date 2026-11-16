# Host identity and the active-run claim

[Source](cli_team_claim.py). The local host identity and the one claim per project under [team workflows](../../00-governance/docs/team-workflows.md). It reuses [`cli_team_store`](cli_team_store.md) for the project, the saved team and the one write lock. No command calls it yet. It launches, stops and observes nothing; release and recovery only rewrite the claim file.

| Interface | Responsibility |
| --- | --- |
| `default_host_path()` | The proposed `~/.local/state/asdg/host-id.json`. Returned only; nothing here creates it without a preview and token. |
| `read_host(host_path, *, root)` | `NONE`, `VALID`, `INVALID` or `UNSAFE`. Read-only. |
| `host_preview(host_path, *, root, host_id, created_at)` | Exact bytes and token for creating the identity, or `UNCHANGED` with the existing one, or `CONFLICT`. |
| `host_setup(host_path, token, *, root, host_id, created_at)` | Creates the previewed file once, mode `0600`. Never replaces, repairs or regenerates. |
| `read_claim(common)` | `NONE`, `CLAIMED`, `RELEASED` (a tombstone), `UNREADABLE` or `UNSAFE`, plus `suspects`: any unregistered file beside the claim. |
| `start_preview(root, team_id, *, goal, owner_session, run_id, started_at, host_path, role_ids, coordinator)` | Exact claim bytes and token for one run, or the conflicts. |
| `acquire(root, team_id, token, *, wait=10.0, **start)` | Writes the claim only when a fresh preview under the write lock gives the same token. |
| `release_preview(root, *, run_id, generation, session, ended_at, host_path)`, `release(root, token, *, wait, **end)` | The owner ends its run: the claim becomes a tombstone in the same file. |
| `recover_preview(root, *, ..., confirmation=None)`, `recover(root, token, *, wait, **end)` | Ends a run the caller's fields do not own, only with the exact phrase the preview states. |
| `check_run(root, run_id, generation)` | `CURRENT` for the exact active run, else `STALE`, or `UNPROVEN` when the claim folder is unclear. Read-only. |
| `describe_suspects(common)` | Each unregistered file beside the claim: kind, hash and, when it parses, the claim it holds. |
| `validate_claim`, `new_host_id`, `new_run_id` | Strict version 1 claim and tombstone shape; random opaque IDs. |

The caller generates `host_id`, `run_id` and the time once and passes the same values to preview and apply, so previews are deterministic.

## Claim, version 1

`<git-common-dir>/asdg/teams/active-run.json`, exact fields in the saved serialization: `schema_version`, `kind`, `run_id`, `generation` (1 when no claim exists, otherwise the tombstone's plus one), `team_id`, `spec_revision`, `spec_sha256`, `project_id`, `git_common_dir`, `worktree`, `host_id`, `owner_session`, `owner_evidence`, `goal`, `state` (`ACTIVE` or `RELEASED`) and `started_at`.
A `RELEASED` tombstone keeps every claim field and adds `ended_at`, `end_kind` (`RELEASE` or `RECOVERY`), `ended_by_host`, `ended_by_session`, `ended_by_worktree` and `end_evidence`. It stays in the claim file as the durable epoch; nothing here deletes it.
Every start, release and recovery token binds the prior claim state, hash and generation, so a token approved before a run started or ended never applies afterwards. A start cannot reuse the tombstone's run ID.
`owner_evidence` is always `UNCORRELATED`: the session ID is a supplied string, checked only for being present and not a placeholder or unexpanded variable. Nothing here verifies a role, a session or a runtime.

## Start conflicts

| Code | Meaning |
| --- | --- |
| `CLAIM_EXISTS` | A valid claim is present. The conflict names its run, team, host, session, worktree and time. |
| `CLAIM_UNREADABLE`, `CLAIM_UNSAFE` | The claim file is malformed, reformatted, of another shape, or behind a symlink. |
| `CLAIM_FOLDER_SUSPECT` | Another file sits beside the claim, such as a sync conflict copy or a leftover. It may be another run's claim. |
| `RUN_ID_REUSED` | The run ID equals the tombstone's. |
| `HOST_IDENTITY_NONE`, `_INVALID`, `_UNSAFE` | No valid host identity at the given path. |

An unknown or invalid team, a bad session, goal, run ID or time, and an unsafe lock or host path raise `Conflict`.

## Ending a run

| Standing | Supplied fields compared with the claim | Path |
| --- | --- | --- |
| `OWNER_FIELDS_MATCH` | Host, project, session and worktree all equal | `release` |
| `OTHER_SESSION`, `OTHER_WORKTREE`, `FOREIGN_PROJECT`, `FOREIGN_HOST` | The first field that differs | `recover`, with `RECOVER <standing> RUN <run> GENERATION <n> HOST <claim host>` |
| `HOST_UNKNOWN` | No valid local identity to compare | Neither |

Conflict codes: `STALE_RUN` (another run or generation is active), `NOT_ACTIVE`, `NO_CLAIM`, `NOT_OWNER`, `OWNER_USES_RELEASE`, `CONFIRMATION_REQUIRED`, `ENDS_BEFORE_START`, and the claim, folder and host codes above.

## Limits

- A claim records an agreement to run. It never shows that a worker is running, and every result says `runtime: NOT_OBSERVED`.
- Sync detection is a name check for a few known folder names plus a ban on paths inside the project. It cannot prove a folder is local.
- The token binds the project, the team file hash and revision, the host identity, the claim folder state, the claim bytes and the lock path. The session and role list are bound as supplied, unverified values.
- The lock is advisory and unproven on synced filesystems. A first claim is created exclusively and later writes replace the file through one temporary file; an ordinary failure restores what was there. A refused start can leave the reusable lock file.
- Standing is equality of supplied fields. Recovery records `HUMAN_DECLARED_UNVERIFIED`: nothing shows who gave the phrase, and no worker is checked or stopped (`liveness: NOT_ENFORCED`).
- Conflict copies, leftovers and unknown files block start, release and recovery. They are never chosen between, adopted or removed here, and an unreadable claim has no recovery path; a human resolves both.
- Deleting the tombstone by hand resets the epoch: tokens approved while no claim existed could apply again.
- Not exercised: the real host location, native protected-path prompts when a client writes these paths, and any synced filesystem.
