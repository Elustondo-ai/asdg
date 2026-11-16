# ASDG roles, agents, and teams in Claude

A saved team is a reusable working agreement: purpose, members, responsibilities, communication, outputs, and completion rules. Assigning a goal turns that agreement into bounded tasks. Multiple definitions can be saved, but **only one ASDG team works in a project at a time**. Teams of teams are deferred until individual teams have been built, tested, and used.

Status: **IMPLEMENTATION UNDER WAY; naming amendment accepted by Pablo.** The current materializations are Sessions, Subagents, and Teammates; all collaborate. [Naming decision and implementation handoff](17-team-materialization-names.md) records the scope. The [earlier implementer sign-off](14-implementer-signoff-final.md) binds the pre-amendment hashes; Claude's [narrow acknowledgment](18-naming-amendment-acknowledgment.md) records the renamed bytes by exact hash; it is not a new technical sign-off. [Gate 1 evidence](16-gate1-native-report.md) remains preserved under its original labels.

![Shared specialist roles feed saved teams of three types, with only one active team per project.](images/team-types.svg)

| Type | Working agreement | First-version target |
| --- | --- | --- |
| Sessions | Persistent specialist chats, with human coordination or authorized assisted handoffs. | Desktop using existing Focus; activity is human-declared. |
| Subagents | A lead dispatches bounded specialist tasks and integrates returned findings. | Desktop first, subject to actual native capability tests. |
| Teammates | A lead and peers discuss and coordinate a shared goal. | Experimental CLI, in-process only, subject to a separate native trial. |

Current official Desktop documentation explicitly excludes native agent teams. A Teammates request there retains its type and definition and explains the CLI requirement; it never silently becomes Subagents or a Desktop dynamic workflow. Using a different surface requires the user's choice, not an automatic migration.

## Agreed direction and proposed delivery

1. Keep `/asdg-create-team-sessions`, `/asdg-create-team-subagents`, and `/asdg-create-team-teammates`. Missing name is the first question; then ask only material unresolved questions with useful defaults.
2. Save teams under `.asdg/teams/specs/`. Configure once, reuse across goals, and create concrete task scopes per run.
3. Creation skills invoke one controlled writer for needed adapters and specifications. Sessions reuses Focus; native types generate or repair owned agent definitions without overwriting custom edits.
4. Separate configuration from launch. First creation or changed definitions require a fresh session and verified loading before start in v1.
5. Begin with a small read-only native trial. Document writing follows demonstrated controls; application coding is outside v1 until a separately reviewed Claude sprint/ownership hook adapter is validated.
6. Preserve specialist authority and single-writer ownership of shared files. Subspecialists remain members of one team; only its lead launches workers.
7. Save many teams, run one. Finish or pause with a handoff before switching; uncertain activity needs reconciliation or an explicit human recovery release.
8. Deliver separately reviewed increments, Teammates last and independently withdrawable. Passing tests does not constitute user acceptance or deployment permission.

## Plan and review navigation

Start with the [step-by-step implementation roadmap](12-implementation-roadmap.md): Sessions → Subagents → Teammates, with a real user exercise after each milestone.

- [Team contract](01-team-contract.md): naming, setup questions, goals, communication, lifecycle.
- [Runtime and state](02-runtime-and-state.md): generation, loading, claims, recovery, and observations.
- [Delivery and acceptance](03-delivery-and-acceptance.md): go/no-go gates and bounded native trials.
- [Evidence and limitations](04-evidence.md): official sources and inspected ASDG code.
- [Concurrency and ownership](05-concurrency-and-ownership.md): independence within one team.
- [Claude's original review](06-review-claude-code.md): preserved unchanged.
- [Response and review queue](07-review-response.md): historical disposition of the first review findings.
- [Claude round 2](09-review-claude-round2.md) and [correction response](10-round2-corrections.md): original blockers addressed; see [final verdict](11-review-claude-round3.md).
- [Writer and policy change inventory](08-writer-and-policy.md): exact implementation boundaries.

Canonical ASDG owns implementation; Alice is a later consumer test. This naming amendment changes plan documents and diagrams only; the F1/F2 implementation rename is applied, uncommitted, and awaits supervisor review.
