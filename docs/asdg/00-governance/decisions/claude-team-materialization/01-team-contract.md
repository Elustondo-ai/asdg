# Create a reusable working agreement

The three typed skills assemble Sessions, Subagents, or Teammates teams. All collaborate; the type describes how members are materialized. A goal later supplies the assignment; creation alone launches no workers.

![Named team definitions share roles; only one definition has an active run.](images/team-types.svg)

```text
/asdg-create-team-sessions
/asdg-create-team-subagents --name "Architecture review"
/asdg-create-team-teammates --name "Security review"
/asdg-team start --name "Architecture review"
```

These are proposed interfaces, not installed commands. The shared canonical `/asdg-create-team` is not a chooser today: its proposed Claude client mode becomes a type chooser while the other client flow stays unchanged. A separate proposed `/asdg-team` handles list, status, start, pause, stop, recovery release, and archive; `--name` prevents lifecycle words being interpreted as positional team names.

## Questions and specification

If `--name` is absent, ask the team name immediately and wait without mutations. Blank input repeats the question; cancellation changes nothing. A supplied name skips that question. Without an interactive channel, return the missing requirement and retry syntax.

Then propose a small roster and ask only unresolved questions about purpose, roles/subspecialties, read-only or document work, output ownership, messaging, integration, and success criteria. Explain unsupported capabilities before any preview. Prefer a small useful roster; warn above five active native teammates and explain the cost. Saved membership need not all run at once.

Parse raw skill arguments in the CLI using documented quoting rules, never shell evaluation. Generate an opaque team ID independent of its name. Normalize names for case-insensitive uniqueness; preserve the display name. Reject empty/control-character names; names are never paths. With explicit `--name`, words such as "start" remain valid names rather than reserved team names.

A matching name refers to the existing specification. Changed rules/type require a visible reconciliation preview, not silent replacement. Save schema version, ID, name, project identity, type, purpose, member slots, collaboration rules, output defaults, completion/handoff rules, and generation provenance. Do not save transcripts or infer native activity from the specification.

## Configuration and later goals

Each creation skill delegates writes to the [single team writer](08-writer-and-policy.md): preview exact effects, apply the reviewed token, and preserve custom content. Sessions validates the existing Focus adapter; any repair uses the ownership-aware extension of the existing adapter-refresh workflow planned in roadmap step 2, avoiding a second writer. Sessions creates no native agent definition. Native types generate only needed definitions. Dirty tracked setup files are reported for normal review and commit, never silently committed.

Creation returns Configured, not Running. V1 requires a fresh session after adding or changing native definitions; start verifies the expected definitions are loaded. A pre-existing unchanged definition still needs runtime evidence. No reliance on `/agents` as a reload command.

Starting requires a goal, relevant context, concrete outputs, dependencies, permitted tools, integration owner, and completion criteria within the saved agreement. If the selected type is unavailable, retain it and explain the compatible surface; ask before changing type or surface. A small task may use fewer members without changing team type.

All three types collaborate. Sessions may use human coordination or explicitly authorized message relays where supported, while preserving direct user access to each chat; this adds no native chat-automation guarantee. Use messages for questions, coordination, and transient findings. Save decisions, deliverables, and restart handoffs in role-owned files when persistence is needed. A Subagents member normally returns findings to the lead; native Teammates can exchange them directly. Neither messages nor teammate plan approval substitutes for human authorization.

## Lifecycle and switching

Many definitions can exist, but one project-wide active claim covers all types and linked worktrees on the same host. Ordinary independent Focus sessions are not blocked by this ASDG claim; they are outside the managed team, so unexpected external edits still need reconciliation.

Sessions starts when the user explicitly activates its roster for a goal and remains active until a human-confirmed pause/stop. Subagents acquires the claim before dispatch and ends after all children finish and the lead returns the integrated result. Teammates remains active until its members and lead run have completed shutdown, not merely become idle.

Pause records a durable handoff and stops work before releasing the claim. Resume creates or reconciles a run; it does not promise native transcript restoration. Unknown liveness blocks automatic switching. [Human-confirmed recovery](02-runtime-and-state.md) handles abandoned claims without pretending it terminated workers.

Archive retains definitions/evidence after activity ends. Status separates Configured, Reload required, Capability unverified, Active, Paused, Interrupted, Unknown, and Unsupported. Report evidence and missing capability explicitly; no self-reported "ready" shortcut.
