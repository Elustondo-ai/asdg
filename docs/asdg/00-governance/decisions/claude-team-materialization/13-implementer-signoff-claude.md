# Implementer review by Claude Code — changes required

Status: **REVIEW**, recorded 2026-11-14 at the user's request, relayed by Codex. It covers the [roadmap](12-implementation-roadmap.md), its diagram, and the round 3 clarifications in pages 02, 03, 04 and 08 as they were on disk at that time. It is a technical verdict, not permission to implement, and no other page was changed.

**Verdict: CHANGES REQUIRED — one required correction and two small ones.** The sequence, dependencies and exercises are otherwise executable, and step 1 is executable as written. With correction 1 made I can implement from this roadmap and will sign it off.

## Required correction

**1. Milestone 1 cannot be delivered to an existing client as written.** The roadmap delivers new and changed Claude adapters through the existing integration refresh. That refresh only adds missing adapters:

- [`plan_initialization`](../../../../../scripts/lib/cli_project.py) plans every client file without replacement, and [`plan`](../../../../../scripts/lib/cli_files.py) raises "Refusing to overwrite existing file" when an existing file differs.
- [Update](../../../../../skills/asdg-update/SKILL.md) confirms it: differing managed files are conflicts, not refreshed.

[08](08-writer-and-policy.md) changes the rendered Claude adapter of the shared chooser by adding `disable-model-invocation: true`. In Alice and every existing Claude client the refresh then stops on that conflict, so `asdg-create-team-manual` and `asdg-team` are not installed either. For the same reason "repairs stay in adapter refresh" names a workflow that cannot repair a differing Focus adapter.

Smallest correction: choose one and write it into roadmap step 2 and the `cli_clients.py`, `cli_project.py` row of 08.

- **(a) Recommended.** Add an ownership-aware adapter update. A managed adapter is replaced only when its current bytes equal the rendering from the installed build, under the same preview and token. Edited adapters stay conflicts. Acceptance: a disposable update from the installed build to the candidate adds the new adapters and updates the chooser.
- **(b)** Keep every existing adapter byte-identical in version 1. The chooser stays model-invocable and only its canonical workflow changes; amend the chooser-metadata sentence in 08 to match.

## Small corrections

2. **Gate 1 exit.** [03](03-delivery-and-acceptance.md) asks for a per-type go/no-go, but the roadmap defers Collaborative feasibility to step 9. Say that Gate 1 records Collaborative as Deferred.
3. **Delivery rhythm.** It names milestones only. Say that step 2 is reviewed and delivered with Milestone 1, may be split into several reviewed changes, and that step 5 runs in the client after delivery.

## Round 3 clarifications

All are incorporated: both extra stores in 02 and 08, the Uncorrelated session ID, control scope with fail-closed tests, chooser metadata, the disposable hook probe, and the review status in 04. One note for the writing checkpoint: a hook in a worker definition's own front matter is a candidate for the "natively scoped control placement" that 08 requires; whether it applies to teammates is undocumented.

## How I will read authorization

An assigned step authorizes its routine work: disposable files, hand-made probes, canonical edits inside the named paths, tests, reports and receipts. These stay consequential and need the user's own word each time: commit or push, any update of Alice, hook entries or hook trust in a real client, installing the CLI, enabling the experimental teams setting, a real host identity file, and a recovery release. Canonical changes also keep their existing change record and ledger receipts; the milestone report is additional.

## First executable step

**Preparation step 1, Gate 1 on Desktop.** Its remaining prerequisites are:

- the user's assignment of step 1; this review is not that assignment;
- a disposable Git project with one linked worktree, outside Alice and canonical, which I can create under that assignment;
- at least two fresh Desktop sessions opened on that folder, one before its first `.claude/agents/` file exists and one after, since this session cannot observe another project's loading;
- the user accepting the trust prompt there, if the surface shows one, so the probe hook runs.

Nothing needs installing. No native trial, implementation, setting change, commit or push was made for this review.
