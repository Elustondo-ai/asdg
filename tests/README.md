# ASDG test guides

These guides explain what the automated tests and continuation fixtures exercise, how their helpers work, and where their evidence stops.
They describe the maintained code; an execution result must come from an actual test run.

- [Disposable continuation scenarios](continuation_fixture.md): Builds isolated client repositories for trying ASDG continuation behavior against empty, partial, accepted or stale Purpose evidence.
- [Agent configuration compatibility tests](test_agent_config.md): Checks that packaged role adapters parse consistently through the portable fallback, while unsupported syntax and duplicate keys fail.
- [Purpose-only project tests](test_purpose_only_status.md): Checks that an accepted Purpose stands alone while Actual and Planned stay unknown without evidence or a Stage 07 plan.
- [Portable integration tests](test_portable.md): Exercises initialization, relocation, preservation, permission boundaries, logging and advice/report handling in disposable Git repositories.
- [Purpose acceptance tests](test_purpose_review.md): Checks that document presence, agent readiness and human acceptance remain separate, and that edits invalidate acceptance without rewriting history.
- [Stage acceptance tests](test_stage_review.md): Checks stage-local documentation acceptance, dependency hashing and readback without mutating lifecycle state.
- [Distribution tests](test_distribution.md): Builds the real ZIP and checks isolated installation, relocation, file exclusion and reproducibility.
- [Build identity tests](test_build_identity.md): Builds, ZIP and clone installs, client-only commits, legacy installs and update after a fresh install, keyed by canonical commit.
- [Claude mod setup tests](test_claude_mods.md): Checks that setup installs Claude mods unchanged and that an initialized client can refresh integrations after local methodology edits.
- [OpenSpec setup tests](test_openspec_setup.md): Checks that setup adds OpenSpec's missing project files for the selected clients, add-only, and never depends on that tool.
- [Pre-code review skill tests](test_pre_code_review.md): Checks outline parsing, validation, packaging and, when `python-pptx` is present, that every rendered slide has notes.
- [Numbered team tests](test_numbered_teams.md): Checks the next team's number, branch and worktree in disposable Git repositories, and that both team skills are packaged.
- [Sprint align skill tests](test_sprint_align_skill.md): Checks the skill's pages, cross-references, scenario list and both client adapters; no workflow is executed.
- [Synchronization tests](test_sync.md): Exercises promote/upgrade, conflicts, deletion protection, dry runs and adopted versions in disposable Git repositories.

Return to the [runtime modules](../scripts/lib/README.md).
