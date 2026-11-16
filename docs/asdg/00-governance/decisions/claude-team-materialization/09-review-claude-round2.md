# Claude Code review — round 2

Status: **REVIEW**, recorded 2026-11-14 at the user's request, relayed by Codex. It covers the [README](README.md), pages 01–05, the [response](07-review-response.md) and the [writer inventory](08-writer-and-policy.md) as they were on disk at that time. It is feedback, not approval, and no other page was changed.

**Verdict: no original blocker is still blocked, and no new blocker stops increment 1.** The design is review-ready for the read-only feasibility gate once corrections 1–3 below are made. Corrections 4–7 must be in the plan before increments 3 and 4. Review agreement is not user acceptance, and nothing here is natively verified.

## Original blockers

| Blocker | Status | Remaining |
| --- | --- | --- |
| 1. Surface support | Resolved in plan | The Desktop exclusion is confirmed in the official page. `claude` is not installed on this machine, so Collaborative is unavailable here until the user chooses to install the CLI. Delegated in Desktop needs native evidence at Gate 1. |
| 2. Definition reload | Resolved in plan | The fresh-session rule is safe. Note the documented behaviour: an existing `.claude/agents/` is reloaded within seconds, so a repair on disk reaches running sessions. That makes "no repair while active" necessary, not optional. |
| 3. Missing enforcement | Resolved in plan by scope | Read-only first and deferred application coding remove the gap for increments 1–3. Document writes need native evidence, and corrections 4–6. |
| 4. State writer and policy | Resolved in plan | One writer is named and the inventory is adequate. See corrections 1, 3 and 4. |
| 5. Claim and recovery | Resolved in plan | Type-specific ends and human-confirmed recovery are sound. See corrections 2 and 3. |
| 6. Shared templates | Resolved in plan | One wording contradiction remains; see correction 1. |

## Corrections before increment 1

1. **Chooser wording and invocation.** [01](01-team-contract.md) says `/asdg-create-team` "remains a Claude-only type chooser". It is a shared canonical skill and is not a chooser today. Say that its Claude client mode becomes a chooser and the other client's flow is unchanged. Its explicit-only setting comes from the shared `agents/openai.yaml`, so state how the Claude adapter gets `disable-model-invocation` without editing that file.
2. **Claim owner and foreign hosts.** Name the source of the owner session: skills can pass `${CLAUDE_SESSION_ID}`, and hooks receive `session_id`. Both ASDG repositories live in a Drive-synced folder, so the Git common directory is synchronized whether intended or not. Add a rule: a claim recorded by another host blocks start and is released only through human-confirmed recovery; a conflict copy of the claim file is reported as Interrupted.
3. **Sandboxed writes.** Claude's [sandbox](https://code.claude.com/docs/en/sandboxing#protected-paths) denies shell writes to `.claude/agents`, `.claude/skills` and the `.claude` settings files, and to anything outside the working directory, which includes the common directory of a linked worktree. Add both to Gate 1 and give every apply step a human-run fallback command. An installer apply did write `.claude/skills` from a shell command in the user's Desktop session, so the restriction is surface-dependent, not universal.

## Corrections before increments 3 and 4

4. **The hook adapter has no writer, increment or scope.** [08](08-writer-and-policy.md) lists it, but the team CLI's stores exclude settings, and the [response](07-review-response.md) says ASDG never edits runtime configuration. Say which reviewed command writes the hook block in `.claude/settings.json` and in which increment. Limit it to managed runs: a project hook fires in every Claude session, including ordinary Focus sessions and internal agents, so the recorder must drop events whose `session_id` is not the claim owner.
5. **The lead is outside the boundary.** 08 says an unrestricted shell invalidates a scoped write boundary, yet the lead needs a shell to call the team CLI. State that boundary claims cover workers only and the lead stays instruction-bound, or gate the lead's shell and writes through the hook.
6. **Role-loading receipt.** 02 rejects a model's assertion, but read-only workers have no shell to call the CLI. Define the receipt: the lead's native invocation record, a fingerprint from the generated definition body returned by the worker, and `SubagentStart` with `agent_type` once the recorder exists. Before the recorder, report the weaker evidence level.
7. **Teammate identity in hooks.** `agent_id` is documented for in-process teammates. `agent_type` is documented only for `--agent` sessions and subagents. A path control keyed on role must map `agent_id` or `teammate_name` to a member; this needs native evidence before Collaborative document writes.

## Smaller points

- Manual "validates or repairs its existing Focus adapter" gives that file two writers. Validate only, and send repair to the existing adapter refresh.
- The status list in 01 omits Unknown and Unsupported, which 02 and 03 use.
- Gate 1 runs before the generator exists; say that it uses hand-made, disposable definitions.

## Evidence corrections

Both corrections in the response are right, and my round 1 was wrong on three points. [Desktop](https://code.claude.com/docs/en/desktop#whats-not-available-in-desktop) says agent teams "are available in the CLI, not in Desktop". [Subagents](https://code.claude.com/docs/en/sub-agents) documents the restart after a first file in a new `agents` directory. [Hooks](https://code.claude.com/docs/en/hooks#common-input-fields) names in-process teammates for `agent_id`.

## What was checked

All pages are within 50 nonblank lines, relative links resolve, and the latest hash of every file in `review.json` matched disk, with the round 1 receipt preserved. Canonical's checks were not run. No code, setting, native trial, commit or push was made.
