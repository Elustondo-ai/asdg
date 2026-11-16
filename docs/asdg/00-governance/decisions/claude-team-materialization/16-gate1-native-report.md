# Gate 1 native report — Claude Desktop

Status: **PARTIAL — conditional verdicts, one accepted exception.** Recorded 2026-11-14 by Claude Code as chunk G4, authorized by Codex under Pablo's delegation. Gate 1 is not passed as a whole, and nothing here shows broad enforcement. This report changes no design, roadmap or sign-off page.

Codex ran parts A and B of the checklist in two fresh Desktop sessions after Pablo approved trusting the disposable folder. I did not re-run any probe; I read the recorded results and the hook log. The [evidence companion](16-gate1-native-report.json) holds the hashes, the session IDs, and the full text of the results file and the hook log.

## What was observed

| Area | Observation |
| --- | --- |
| Surface | App 5.11492.5, Opus 5.5 Medium, Auto; a trust prompt named the folder and its settings file. Version and prompt were relayed by Codex. |
| Skill input | `/gate1-probe` appeared in the slash menu. Raw arguments arrived as `--name "Architecture review"`. The session ID expanded and equalled the hook `session_id`. It is not the Desktop `local_…` ID. |
| Setup writes | Shell writes to `.claude/skills`, `.claude/settings.local.json`, `.git/asdg-gate1`, a path outside the working directory, and a first `.claude/agents` file were all allowed without a prompt. |
| Definition loading | A first-created `.claude/agents/` was not discovered in the same session. A fresh session listed the worker. A second definition added to the existing directory was available after 16 seconds without a restart. |
| Delegation | The named worker ran, returned the role-source canary and its exact fingerprint, and reported Read, Grep, Glob plus a harness report-back tool. |
| Worker limits | The worker had no tool to write or to spawn. Nothing was refused: this is a missing tool, not an exercised policy denial. |
| Hook identity | `SubagentStart`, the worker's `PreToolUse` for Read, and `SubagentStop` carried the same `agent_id`, the definition name as `agent_type`, and the parent `session_id`. |
| Unexplained events | Six `SubagentStop` events had an empty `agent_type` and no matching start. Their origin is unknown. |

## Conditional verdicts

| Type | Verdict | Conditions |
| --- | --- | --- |
| Manual | Conditional go to implement | Nothing observed blocks it. The team CLI, the claim store and the host identity path are untested. |
| Delegated, read-only | Conditional go to implement | Fresh session after a first definition; the recorder must ignore events without a registered `agent_type` and matching start; worker limits rest on tool absence only. |
| Delegated, document writing | Not assessed | Stays Unsupported until its own control checkpoint. |
| Collaborative | Deferred | Roadmap step 9; CLI feasibility is untested. |

## Gaps

- The linked worktree's actual common-directory write and the user-local host identity path are UNTESTED. Probe A4.4 was a stand-in only.
- Hook failure behaviour, other permission modes and other app versions are untested. This is one run on one machine.
- The evidence is under `/private/tmp/asdg-team-gate1-fPAmNA`, which a reboot or cleanup can remove. The companion embeds the full results text and the full hook log, each matching its recorded hash, so the native evidence survives that cleanup.

## Accepted exception — global git ignore

`~/.config/git/ignore` was created at 2026-11-14T19:40:42Z, eleven seconds before session B's first hook event. It holds one line, `**/.claude/settings.local.json`, and is outside the allowed boundary. Probe A4.2 had created that settings file by shell a minute earlier.

Its creator is **unconfirmed**. The line matches documented Claude Code behaviour: the [settings page](https://code.claude.com/docs/en/settings) says Claude Code adds exactly that pattern to the global git excludes the first time it writes the file in a repository that does not ignore it. That is a documentary match, not proof, and the probe file's own timestamp did not change. No worker escape is shown by the evidence.

Codex escalated this to Pablo, who answered: "Leave the rule and continue." The file is left unchanged. His decision accepts this exception and lets the planned implementation continue. It is not proof of who created the file, and it is not permission for other global writes. Whatever the cause, ASDG setup and future probes should not create `.claude/settings.local.json`.

## Carried into later steps

These are implementation notes; no signed page is changed. The claim owner must use the skill or hook session ID. The recorder filter in [02](02-runtime-and-state.md) is confirmed as necessary. The fingerprint receipt works as designed. Setup writes were allowed on this surface, so the human-run fallback was not needed here; it stays in the design because it is surface-dependent.
