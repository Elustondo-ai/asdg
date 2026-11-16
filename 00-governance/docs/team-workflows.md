# Managed team workflows

Status: policy for a capability under construction. The team command named here is planned. Until a client's installed package provides it and its checks pass, managed teams are unavailable in that client, and nothing on this page may be reported as working or enforced.

These allowances supplement [role ownership](documentation-authority.md) and the [write exceptions](write-exceptions.md). They select no role and authorize no project work.

## Configuring and starting are separate

| Explicit human request | Permits | Never permits |
| --- | --- | --- |
| Create Team, for one named team | Saving that team's specification and the client definitions it needs, through the controlled writer. | Launching members, assigning work or starting a run. |
| Start, for one named team and goal | One managed run: its claim transitions, bounded member assignments inside the saved agreement, and dispatch of that team's registered members by its lead. | A second run, members of another team, or any later start. |
| Recovery release | Releasing one exact abandoned claim after the human confirms that work has stopped. | Stopping processes or releasing a newer run. |

## One controlled writer

Only the team command of the installed CLI writes the registered team stores. Skills gather intent and call it; they never write those stores themselves.
Configuration follows preview, exact token, then apply. Apply rechecks every input bound by the token and fails on any difference.
The registered stores are exactly these:

| Store | Limit |
| --- | --- |
| `.asdg/teams/specs/<opaque-id>.json` | One file per saved team. No other lasting file under `.asdg/teams/`. |
| `.claude/agents/asdg-*.md` | Only definitions ASDG generated. Other client definitions are never written. |
| `.asdg/cache/teams/` | Per-checkout observations, and the writer's local write receipts in `spec-writes/<opaque-id>.json`. A receipt is local write evidence, never approval or authority. |
| `<resolved-git-common-dir>/asdg/teams/active-run.json` and one dedicated `write.lock` beside it | The lock serializes configuration and claim transitions. Nothing else in the Git common directory. Refs, index, config and all other Git internals are preserved. |
| `~/.local/state/asdg/host-id.json`, or an explicitly previewed non-synced equivalent | One host identity file. |
| ASDG's own entries in `.claude/settings.json` | Only through observer setup, below. Unrelated settings are preserved. |

Only the team writer may use bounded temporary transaction files next to its exact registered outputs; they are removed on ordinary failure.
Native runtime stores for teams and tasks remain owned by Claude; ASDG never writes them.
Locally edited files, and files whose origin cannot be proven, are conflicts and are never overwritten. Repair of a definition used by an active team is refused.
No other path becomes writable. This allowance grants no stage, application, unrelated project-state or general filesystem authority.

## Authority stays with each session

A team is a working agreement, not a role. Each member acts under its own role receipt and that role's ownership.
Membership, a lead's assignment, a teammate's message and an automatic plan approval never widen a role and never count as human approval.
The run claim records which team is active. It is not shared active-role state and never selects, restores or proves anyone's role.
Governance as lead coordinates and integrates results; it gains no specialist write authority.
Tool and path limits apply to workers only. In the first version the lead remains bound by instruction, so never describe a whole team as enforced.

## One active managed team

At most one managed team runs in a project on one host. A start while a claim exists is refused and names the active run.
Unknown or interrupted activity blocks switching until it is reconciled or the human releases the claim.
Sessions outside the managed run, including ordinary focused chats, are neither blocked nor controlled by the claim.

## Observation

Observer setup is its own explicit request: a preview and exact-token apply for the exact owned entries, preserving unrelated settings and existing trust decisions. Create Team and Start never install a hook or grant hook trust.
The observer records minimal public metadata, and only for the active run's owner session and its registered members.
Other sessions and unidentified agents are not recorded and receive no decision from it. Missing evidence is reported as Unknown.
Observation is evidence. It is never approval, project state or proof of enforcement.

## Missing capability

A team type whose runtime support is absent or unverified on the current surface stays unavailable. Report that, keep the saved team and its type, and never substitute another type or simulate members in prose.
The types are Sessions, Subagents and Teammates; each names how members exist, and all three collaborate. Sessions teams use existing Focus sessions the user can address directly, and their activity is declared by the human. Other clients keep their existing Create Team flow unchanged.
