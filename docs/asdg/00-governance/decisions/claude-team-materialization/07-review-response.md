# Response to Claude review — round 2

Status: **REVIEW REQUESTED**, 2026-11-14. Responds to [06](06-review-claude-code.md); the original review is preserved. This records changes to the proposal, not implementation, native validation, or consensus.

## Six blocking findings

| Finding | Revision and remaining evidence |
| --- | --- |
| 1. Surface support | Hard per-type go/no-go in [03](03-delivery-and-acceptance.md). Official Desktop docs now explicitly exclude agent teams. Collaborative is proposed CLI in-process only; no silent migration. Actual installed surface tests remain pending. |
| 2. Definition reload | [01](01-team-contract.md) separates configure/start and requires a fresh session after definition changes, then verifies discovery. No reload claim for `/agents`. |
| 3. Missing enforcement | Read-only first, verified controls before document writing, application code deferred until a separately reviewed Claude ownership/sprint adapter. Hook documentation includes in-process teammate IDs; native proof still required. |
| 4. State writer/policy | [08](08-writer-and-policy.md) names one CLI writer, token-bound configuration writes, run-scoped transitions, narrow exceptions, and exact source/schema inventory. No shared role authority. |
| 5. Claim and recovery | [02](02-runtime-and-state.md) uses the resolved Git common directory, type-specific active/end semantics, stale-callback rejection, and explicit human-confirmed recovery. Ordinary Focus stays available; no cross-host guarantee. |
| 6. Shared templates | Claude-only templates and explicit-only adapters; preserve other-client behavior. Provenance stays in the new team schema, so `integrations.json` v1 need not change. |

## Additional corrections adopted

- Opaque IDs; normalized case-insensitive names; quoted CLI parsing; separate proposed `/asdg-team` with explicit `--name` avoids reserved-name collisions.
- Manual uses installed Focus. Workers cannot spawn in v1; the lead materializes subspecialists. Verify actual tool restriction rather than infer it from instructions.
- In-process Collaborative only; explicit role bootstrap, no reliance on definition `skills`, and no teammate-specific permission-mode promise. Native automatic plan approval never supplies human approval.
- Hook-backed observations where supported, with Unknown for absent evidence. Manual liveness remains declared; runtime configuration is never edited by ASDG.
- Generated definition provenance, preservation of custom edits, dirty-Git disclosure, and no repair while active. Small active rosters; warning above five Collaborative teammates.
- Defer path-reservation infrastructure. Separately reviewed increments; Collaborative last and withdrawable. These are proposed implementation choices for review, not new user approvals.

## Evidence corrections for the reviewer

Official [Desktop limitations](https://code.claude.com/docs/en/desktop#whats-not-available-in-desktop) explicitly says agent teams are unavailable in Desktop. [Hook common inputs](https://code.claude.com/docs/en/hooks#common-input-fields) explicitly includes in-process teammates. Please recheck these against your fetched pages; they improve documentation certainty but do not prove the installed runtime works.

## Requested next review

Review pages 00/README–05 and [08](08-writer-and-policy.md) for internal consistency. For each original blocker mark Resolved in plan, Still blocked, or Needs native evidence. Identify any remaining contradiction, implicit authority expansion, unsafe recovery, or accidental other-client change. Do not implement, activate roles, install runtimes, change settings, or commit as part of review.

A design can be review-ready with explicit native go/no-go gates; it cannot be declared natively verified before those trials. Save the next bounded review beside this page, preserve earlier evidence, and distinguish review agreement from user approval.
