# Timeboxed execution plan

Status: **PROPOSED scheduling addendum**, recorded 2026-11-14 by Claude Code at the user's request, relayed by Codex. It schedules the [roadmap](12-implementation-roadmap.md) using the [accepted materialization names](17-team-materialization-names.md). The earlier technical sign-off remains attached to its recorded hashes. It authorizes nothing by itself: a chunk runs only inside a scope the user has already assigned. All times are estimates, not guarantees.

## Timebox rules

- A chunk targets 5–10 minutes of active work and ends with one reviewable deliverable and one focused check.
- **The 10-minute checkpoint is elapsed wall-clock time from the start of the run, including tool and test waiting.** It is not 10 minutes of active work plus unlimited unattended time. I note the start time and check the clock before starting each new piece of work.
- At the checkpoint I start nothing new and report what is done, what remains, any operation still running, and the next estimate. I report even if a test is still running, and I do not continue toward 20.
- I never abandon a dangerous partial write to meet the clock. If reaching a safe state needs extra time, I say so explicitly and say how much.
- Long tests and tools run bounded or in the background where the surface supports it, so they can be polled and do not hold the report.
- One chunk per response is a stopping and reporting boundary, not a new approval. Scope the user has already authorized persists, and a simple "continue" starts the next chunk. Consequential actions still need his own word: commit, push, client updates, hook trust, installation and settings.
- A chunk that proves too large is split, and the split is reported; it is not stretched.
- Full validation (manifest, integrity check, full suite, change record, ledger receipts) is its own chunk, not repeated after each small edit.

## Three kinds of time

| Kind | Meaning |
| --- | --- |
| Active | My own work in one run: reading, editing, focused tests, records. The 5–10 minute target is an effort estimate for this. |
| Unattended | A running test suite or tool. It counts toward the 10-minute wall-clock checkpoint. The full canonical suite was not timed for this estimate; I expect minutes, and the first validation chunk records the real figure. |
| Waiting for Pablo | Opening a fresh session, a trust prompt, a commit or push instruction, approval of an exact update plan, and his own use of a team. Not counted in the active totals; a run ends and reports when it reaches such a wait. |

## Rough totals

| Milestone | Chunks | Active total | Waiting for Pablo | Confidence |
| --- | --- | --- | --- | --- |
| Sessions, including Gate 1 and the shared foundation | 24 | 2.5–4 hours | Two fresh sessions and a trust prompt; one commit instruction; two plan approvals; two team exercises of his own | Medium |
| Subagents | 12 | 1.5–2.5 hours | One commit instruction; two plan approvals; a fresh session and hook trust; one exercise | Medium to low |
| Teammates | 9 | 1–2.5 hours | CLI installation and launch by his choice; one commit instruction; plan approvals; one exercise | Low |

The chunk lists are in [Gate 1, foundation and Sessions](15.1-chunks-gate1-foundation-manual.md) and [Subagents and Teammates](15.2-chunks-delegated-collaborative.md). The optional document-writing checkpoint is not scheduled; I expect four to six more chunks if it is requested.

## Main uncertainties

- **Splits.** Canonical rules add fixed work to every code change: a companion page, the 50-line page limit, the package list and receipts. I expect three to six chunks to split, which the upper ranges allow for.
- **Gate 1 outcome.** A no-go for Subagents on Desktop removes its milestone; an unexpected protected-path result adds a fallback chunk.
- **Native sessions.** Gate 1 and each native exercise run in a session opened on another folder. That session does the probing from a written checklist; I cannot watch it from here, so its time is the least certain.
- **Teammates.** It is experimental; CLI feasibility remains untested in Gate 1.

## First three chunks

1. **G1, probe kit (5–8 minutes).** A disposable Git project with a linked worktree, the probes and a two-part checklist. Useful outcome: Gate 1 is ready to run, and nothing outside that folder has changed.
2. **G2, session A (5–8 minutes plus waiting).** Version, session identity, protected-path writes and first-created `agents` directory behaviour. Useful outcome: we know whether setup writes need the human-run fallback.
3. **G3, session B (6–10 minutes plus waiting).** Discovery, delegation, denied write and spawn, fingerprint and hook events. Useful outcome: the Subagents go/no-go evidence on Desktop.

G4 then turns the results into the Gate 1 report. The prerequisite for G1 is the assignment of roadmap step 1 and an agreed folder outside Alice, canonical and Drive.
