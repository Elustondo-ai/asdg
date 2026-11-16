# Runtime, durable state, and recovery

Sessions, Subagents, and Teammates all collaborate; their materialization and lifecycle differ. Keep reusable agreements, native definitions, and observations separate. Existing role/session receipts retain authority; a shared run claim never selects anyone's role.

![The same catalogue supports different runtime forms, with one active team per project.](images/team-types.svg)

## Definitions and launch

Creation owns generation/repair through `cli.py team …`; installation supplies templates and skills. Sessions validates existing Focus; adapter repair remains with the existing refresh workflow, extended with verified baseline comparison in roadmap step 2. Native definitions have unique names, short descriptions, explicit tools, a role bootstrap body, and build/template/content fingerprints. Preserve unknown or locally changed files through reconciliation; never overwrite them automatically.

V1 treats definition creation or change as requiring a fresh session before native launch. Probe discovery against expected fingerprints/role content in the actual surface. Report unavailable CLI or native tools as a capability gap. Do not install a runtime, change security settings, or substitute a team type as part of discovery.

The lead supplies project root, ASDG build, role sources, team/run/member IDs, goal, bounded task, inputs, outputs, and completion rules. The role-loading receipt combines the lead's native invocation record with a role/build/template fingerprint embedded in the definition body and returned by the worker. Once the recorder is available, correlate `SubagentStart` identity/type. Before then label evidence as invocation plus self-reported fingerprint, not independently proven loading; read-only workers need no shell or CLI access. Teammates need explicit bootstrap instructions rather than dependence on definition `skills`.

Only the lead launches members in v1. A subspecialist is a narrower member assignment, not another team. Native tool restrictions must prevent specialist spawning and be tested; instructions alone do not establish that restriction. Teammates is CLI in-process only in this version; split panes and recursive delegation are deferred.

## One writer, separate stores

| Store | Purpose and owner |
| --- | --- |
| `.asdg/teams/specs/<opaque-id>.json` | Versioned agreement and adapter provenance, written through the team CLI. |
| `.claude/agents/asdg-*.md` | Versioned generated native definitions, written through the same CLI. |
| `.asdg/cache/teams/` | Per-checkout observations and the writer's local write receipts (`spec-writes/<opaque-id>.json`); never the shared claim, approval or role authority. |
| `<git-common-dir>/asdg/teams/active-run.json` | Local project-wide claim shared by linked worktrees, written only by the team CLI. One dedicated `write.lock` beside it serializes configuration and claim transitions. |
| `~/.local/state/asdg/host-id.json` | Proposed v1 host identity outside the synced project, created by reviewed CLI setup. If this location is itself synced, require a previewed non-synced equivalent. |
| `.claude/settings.json` owned hook entries | Reviewed setup-observer command; preserve unrelated settings. |
| Native team/task storage | Claude-owned; observe through supported interfaces, never pre-author or edit it. |

Only the team writer may use bounded temporary transaction files next to its exact registered outputs, removed on ordinary failure. Resolve the canonical absolute Git common directory through Git, not by assuming `.git` is a directory. Write only the ASDG-owned subdirectory there, never refs, index, config, or other Git internals. Non-Git projects and cross-host coordination are unsupported in v1; separate clones are not one shared claim domain. The current repositories are Drive-synced, so that directory may in fact synchronize. A foreign-host claim blocks start and requires human-confirmed recovery; conflict copies or divergent claims produce Interrupted. This is not a distributed lock: v1 requires single-host operation and offers no protection against simultaneous starts from unsynchronized hosts.

## Claim transitions

The CLI atomically acquires the claim before any managed dispatch. Record schema, run/team IDs, host, owner session, worktree, state, generation, and start time. Obtain owner identity from a verified `${CLAUDE_SESSION_ID}` skill expansion and correlate with hook `session_id` once increment 3 supplies the recorder. Before then accept a present, nonliteral value as Uncorrelated; reject absent/literal values and later mismatches. A host-local identity outside the synced repository distinguishes hosts; its bounded creation belongs to the reviewed setup command. Concurrent attempts fail with the active run's identity. Setup may save inactive definitions but cannot repair definitions used by a running team.

For live updates, require the exact run ID and generation; stale callbacks cannot mutate a replacement run. User-approved start authorizes only that run's bounded claim transitions, not arbitrary future starts. Use atomic writes and compare-and-swap semantics, with a lock shared through the Git common directory.

Normal completion releases only after the type-specific conditions in [the contract](01-team-contract.md) hold. Idle notifications, elapsed time, and a missing cache record never prove shutdown. On a crash or missing callbacks, retain Interrupted/Unknown until reconciliation.

Recovery release shows the claim, last evidence, affected members, and warning that release does not stop processes. Require explicit human confirmation that work has stopped, append a recovery observation, then release that exact generation. Sessions stop/pause likewise relies on a human declaration and reports that evidence level honestly.

## Observation and authority

Use supported runtime events such as `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, and `TeammateIdle` where available, plus session/run evidence. Check event coverage on the installed surface; an idle or stop event alone may not mean all descendants ended. Collect minimal public metadata, not full transcripts, secrets, or private reasoning.

A reviewed hook recorder calls the same narrow CLI observation writer. Drop events whose `session_id` differs from the claim owner, or whose host/run generation does not match. Verify these IDs for each supported native mode; no inferred enrollment of other sessions. Ordinary Focus and internal agents are not recorded as team members. Map native `agent_id` or verified `teammate_name` to registered members; never assume teammate `agent_type` exists. Missing events produce Unknown rather than inferred activity. Native configuration can disappear at session end; saved ASDG specifications do not. Sessions Focus observations remain human-declared when no native lifecycle is observable.

V1 begins read-only. Document-write trials require demonstrated path/tool controls; application edits wait for a separately reviewed and tested Claude ownership/sprint hook adapter. Worker tool/path restrictions are the bounded enforcement claim; the v1 lead remains instruction-bound and uses the team CLI through its ordinary authorized tools. Do not claim end-to-end sandbox enforcement for the team. A team is never a new source of approval or specialist authority. [Required policy changes](08-writer-and-policy.md)
