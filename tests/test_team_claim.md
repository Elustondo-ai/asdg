# Host identity and run-claim tests

[Source](test_team_claim.py). Focused tests for [`cli_team_claim`](../scripts/lib/cli_team_claim.md). Each test builds a disposable Git project with two saved teams and uses a fixture host path inside the same temporary area. Helpers come from [the store tests](test_team_store.md).

| Evidence | Coverage |
| --- | --- |
| Host preview and setup | Preview is read-only and deterministic; ID, time and path each change the token; stale tokens are refused; setup writes the previewed bytes with mode `0600`; a later proposal reports the existing ID and nothing is replaced |
| Refused identities | Malformed, unknown version, unknown field, reformatted and bad-ID files are `INVALID`, block a start and keep their bytes; a symlinked file is `UNSAFE`; relative, in-project, in-Git, misnamed, symlinked-folder, `..` and known synced-folder paths are refused |
| First and second claim | The claim equals the previewed bytes and binds the team hash and revision, host, session, worktree and common directory; the same team or another team is then `CLAIM_EXISTS` with the active run named; the claim is unchanged |
| Linked worktrees | Two real worktrees resolve one common directory; four separate processes, two per worktree, each hold a valid token and exactly one acquires |
| Bad inputs | Twelve missing, literal or placeholder session values; bad run IDs, times and goals; unknown, path-like and malformed teams; seven invalid claim shapes |
| Stale tokens and blockers | Malformed tokens are refused before any lock exists; a changed goal, run ID, session, role list or edited team file is refused, leaving only the lock; a conflict copy, a leftover, and malformed, reformatted or foreign claims block and keep their bytes; a symlinked claim or folder is refused and nothing appears outside |
| Ordinary failure | A read-back failure removes the new claim, leaves the host identity and lock, and the same token then acquires |
| Release and replay | Wrong run, generation or time is refused; release leaves the previewed tombstone; start tokens approved before the run, or against an earlier tombstone, never apply; a reused run ID is refused; generations go 1, 2, 3 |
| Owner fields and recovery | Another session or linked worktree cannot release; recovery states its phrase, refuses any other text, a missing phrase or a release token, records the declaring session as unverified, and the recovered owner's late release is refused |
| Foreign host and copies | A second fixture identity is `FOREIGN_HOST` and needs its own phrase; a missing identity ends nothing; a conflict copy, a leftover and an unknown file each block start, release and recovery and keep their bytes; unreadable and absent claims are reported |
| Store coordination | A saved team's revision is blocked while a run is active, ready over a clean tombstone with a new token, and blocked again when a copy sits beside it |

Previews run inside a snapshot check of the whole disposable area. These tests never touch the real host location, a real project store or a synced folder, and they show nothing about native prompts for protected paths, crashes or running workers.
