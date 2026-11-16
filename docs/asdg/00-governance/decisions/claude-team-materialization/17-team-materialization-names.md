# Sessions, Subagents, and Teammates

**Decision accepted by Pablo on 2026-11-14:** use the three commands below, and recognize that **all three team materializations collaborate**. This replaces the earlier type labels; it does not introduce another team type.

![All three materializations use ASDG specialist roles, reusable agreements, and one active team per project.](images/team-types.svg)

| Materialization | Command | Members and coordination | Earlier label |
| --- | --- | --- | --- |
| Sessions | `/asdg-create-team-sessions` | Persistent specialist chats the user can open and address directly; human coordination or authorized assisted handoffs where supported. | Manual |
| Subagents | `/asdg-create-team-subagents` | A lead gives bounded assignments to native subagents and integrates their returns. | Delegated |
| Teammates | `/asdg-create-team-teammates` | Native teammates coordinate through the supported experimental team runtime. | Collaborative |

## Shared collaboration, different materialization

Every type uses the same specialist roles, saved working agreement, goals, ownership limits, output rules and integration responsibility. Coordination may use messages or durable files as appropriate. A type describes how members exist and operate, not whether they collaborate or how much the user must type.

Sessions can use an authorized coordinator to relay messages while retaining direct access to each chat. Availability must be checked on the actual surface. UI relaying is not proof of a native messaging API, automated chat creation, or reliable session-liveness control. Sessions activity and pause/stop remain human-declared in v1.

Subagents and Teammates retain their existing native dispatch and shutdown requirements. Teammates remains the experimental native-team materialization; passing messages between ordinary sessions does not silently change their type. All existing authority, runtime, one-active-team, setup, approval and writing boundaries remain in force.

## Implementation handoff before F3

Update F1/F2 and future typed skills to use `sessions`, `subagents`, and `teammates` as the stored type values and exact command suffixes. Preserve all unrelated validation and client behavior. F2 is uncommitted and has no installed team-store format, so no released-data migration or legacy aliases are needed for this amendment.

In `cli_team_model`, `lead: null` for Sessions means no native subagent/team dispatch lead. It must not be described as forbidding a coordination or integration owner; the saved agreement still records that responsibility. Do not add automatic cross-session messaging as part of this naming change.

Claude should make one bounded naming chunk: update `team-workflows.md`, the model and both companions/tests, check for old type literals in active implementation, run the focused team-model tests, and acknowledge the renamed plan with current hashes. A full suite or repeated native feasibility trial is unnecessary for labels alone. Stop for supervisor review before F3.

## Review and history

The current design, roadmap, scheduling text and diagrams now use the accepted names. Existing file names and chunk IDs remain stable so links and earlier receipts remain usable. Original review pages, exact-hash sign-off, Gate 1 evidence and prior ledger entries remain unchanged; their old labels map through the table above.

The [earlier implementer sign-off](14-implementer-signoff-final.md) does not transfer to changed bytes. The handoff was sent, and Claude's [narrow acknowledgment](18-naming-amendment-acknowledgment.md) records the renamed bytes by exact hash; it is not a new technical sign-off. This records the user's naming decision, not a claim of implemented commands, publication, deployment or new runtime verification.
