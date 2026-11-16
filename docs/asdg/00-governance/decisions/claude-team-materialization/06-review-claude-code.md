# Independent review by Claude Code

Status: **REVIEW**, recorded 2026-11-14 at the user's request. It is feedback on the [proposal](README.md), not approval, and it changes no other page. The plan is sound but not ready to implement: six points need resolving first, and the first two could change the design.

Checked against canonical `f2b8591`, Alice's installation, and the Claude Code documentation for [subagents](https://code.claude.com/docs/en/sub-agents), [agent teams](https://code.claude.com/docs/en/agent-teams), [skills](https://code.claude.com/docs/en/skills) and [hooks](https://code.claude.com/docs/en/hooks), fetched the same day.

## Resolve before implementation

| Finding | Evidence | Needed |
| --- | --- | --- |
| 1. The target surface is unverified. | The user works in the desktop app; `claude` is not on the shell PATH. The documentation is silent on agent teams and `.claude/agents` there, and per-session enablement is documented only for the CLI (shell variable or a `--settings` payload). | Make increment 1 a go/no-go gate per type and surface. Decide whether Collaborative may be CLI-only. |
| 2. Create and start in one action may fail. | Claude watches `.claude/agents/` only when the directory existed at session start; Alice has none. First creation mid-session is undocumented, and `/agents` does not reload. | Keep creation and start separate whenever definitions were created or changed, or require a restart before start. |
| 3. The sprint gate is not enforced in Claude. | The hook is generated only as `.codex/hooks.json` by [`cli_project`](../../../../../scripts/lib/cli_project.py); Alice has no `.claude/settings.json`. Claude `PreToolUse` hooks run inside subagents with `agent_id` and `agent_type`; teammates are not explicitly documented. | Add a Claude hook adapter to this delivery, or limit version 1 native runs to read-only work and document writes. |
| 4. No named writer, and the rule changes are incomplete. | [Write exceptions](../../../../../00-governance/docs/write-exceptions.md) require Admin maintenance and human review for a new exception. [Create Team](../../../../../skills/asdg-create-team/SKILL.md) forbids shared active-role state. [`cli_team`](../../../../../scripts/lib/cli_team.py) reports Claude as `native_chats: UNSUPPORTED`. The `integrations.json` reader in [`cli_clients`](../../../../../scripts/lib/cli_clients.py) rejects unknown keys. | One writer, `cli.py team …` with preview, token and apply, for specifications, generated definitions and the claim. List every rule and schema change. |
| 5. The active-run claim has no workable home or release. | `.asdg/cache/` is ignored and exists per checkout, so it cannot be common to worktrees. Manual teams have no observable liveness; a crashed lead leaves a claim nothing may release. | Keep the claim in the Git common directory. Define "active" per type, including when a Delegated run starts and ends. Add a human-confirmed release. State that ordinary focused sessions are not blocked. |
| 6. The skill templates are shared with Codex. | One template under `templates/.agents/skills/` renders both clients' adapters. The type chooser would change Codex's thirteen-chat behaviour, and the three new skills would install there too. `asdg-create-team` has no explicit-only policy, so its Claude adapter is model-invocable. | Decide between Claude-only templates and Codex stubs. Give the new skills the explicit-only policy. |

## Corrections to the evidence page

- `--name` and `--roles` arrive as raw argument text; indexed arguments use shell-style quoting, so names with spaces need quotes. Parse and validate in the CLI.
- The lifecycle verbs `list`, `status` and `start` collide with team names. A separate `/asdg-team` skill avoids reserved words.
- Subagents can now spawn subagents by default, up to three layers. Specialists must be prevented from doing so, for example by leaving the Agent tool out of `tools`; this needs a live test.
- For teammates, `skills` is ignored and no per-teammate permission mode exists. In-process appends the definition body to the default prompt; split panes replace it. Support in-process only in version 1.
- A teammate spawned in plan mode has its plan approved automatically, without lead review.
- Native team configuration is deleted when the session ends. Capture observations through the `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted` and `TeammateIdle` hooks, not through model self-reports.
- "Role-loading definitions" for Manual teams are undefined. Manual needs only the installed `/asdg-focus` adapter today. `claude --agent` exists, but it replaces the whole system prompt.

## Gaps and scope

- Generated `.claude/agents/asdg-*.md` files are tracked, so creation dirties Git and sprint start requires a clean tree. Stamp each file with the build and template hash so "outdated" is computable.
- Use a generated team ID, not one derived from the name. Define case-insensitive uniqueness and reserved words.
- The documentation recommends three to five teammates. Add a cap or a warning for Collaborative rosters.
- Defer the path-reservation machinery in [concurrency and ownership](05-concurrency-and-ownership.md) until after the first native trial; without hooks it is advisory.
- Deliver in separately reviewed commits, with Collaborative last so it can be withdrawn if the experimental feature changes.

## What was and was not checked

Every page is within 50 nonblank lines, relative links resolve, the hashes in `review.json` matched the files on disk, and both diagrams' labels match the one-active-team decision. Canonical's integrity check and test suite were not run against this folder. No native Claude behaviour was exercised; documentation gaps are reported as gaps, not as support.
