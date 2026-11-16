# Claude Code review — round 3

Status: **REVIEW**, recorded 2026-11-14 at the user's request, relayed by Codex. It covers the [README](README.md), pages 01–05, the [writer inventory](08-writer-and-policy.md) and the [correction map](10-round2-corrections.md) as they were on disk at that time. No other page was changed.

**Verdict: no blocker remains. The design is ready for Gate 1.** It is not user-approved and not natively verified. Gate 1 itself, any CLI installation and every later increment still need the user's explicit go-ahead.

## Round 2 corrections

| Correction | Result |
| --- | --- |
| 1. Chooser and client policy | Incorporated in [01](01-team-contract.md) and 08. |
| 2. Session ID and foreign-host claims | Incorporated in [02](02-runtime-and-state.md), with the single-host limit stated. |
| 3. Protected apply paths | Incorporated in [03](03-delivery-and-acceptance.md), [04](04-evidence.md) and 08. |
| 4. Hook writer, increment and filter | Incorporated in 08 and 03: `setup-observer` in increment 3, controls in increment 4. |
| 5. Lead boundary | Incorporated in 02, 03, [05](05-concurrency-and-ownership.md) and 08. |
| 6. Role-loading receipt | Incorporated in 02, with the weaker early evidence level named. |
| 7. Teammate identity | Incorporated in 02 and 08; no assumed teammate `agent_type`. |

The three smaller points are also incorporated: Manual validates only, the status list includes Unknown and Unsupported, and Gate 1 uses hand-made definitions.

## Residual corrections, none blocking Gate 1

1. **Before increment 2: complete the store list.** 08 gives the team CLI two more stores, the user-local host identity and the owned block in `.claude/settings.json`. The store table in 02 and the write-exceptions row in 08 name neither. Add both, and add the user-local path to the Gate 1 write tests, since it is outside the working directory.
2. **Before increment 2: session ID evidence level.** 02 requires the skill's session ID to be correlated with hook `session_id`, but the recorder arrives in increment 3. Say that until then the ID is accepted when present and not literal, and labelled uncorrelated.
3. **Before increment 4: scope and failure mode of the control hook.** 08 states the filter for recording only. State it for controls too: the hook returns no decision for the lead, for unregistered agents and for sessions outside the active run, so ordinary Claude sessions are unchanged. Claude treats a failing hook as a [non-blocking error](https://code.claude.com/docs/en/hooks#exit-code-output) unless the hook is configured to block on failure, so a control that fails open is not enforcement. Add that case to the increment 4 tests.
4. **Wording.** 08 should say the Claude explicit-only metadata also covers the shared chooser, not only the new Claude-only templates. The "Review status" section of 04 still describes round 2 as pending. Gate 1's event-coverage probe needs a hand-made hook; say it lives only in the disposable project.

## Notes for Gate 1

- Hooks run outside Claude's sandbox, so recorder writes are not limited by it. The lead's shell calls to the team CLI are. If the claim cannot be written from a linked worktree on a surface, report managed runs from that worktree as Unsupported there.
- `claude` is not installed on this machine. The Collaborative trial cannot run until the user chooses to install the CLI.

## What was checked

All pages are within 50 nonblank lines and relative links resolve. The latest hash of every file in `review.json` matched disk, and the round 1 and round 2 receipts are preserved with their original hashes. Canonical's checks were not run. No code, setting, native trial, commit or push was made.
