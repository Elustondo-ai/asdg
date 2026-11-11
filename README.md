# ASDG — portable methodology

ASDG initialization installs the methodology and prepares the project’s ASDG team through the [canonical init workflow](skills/asdg-init/SKILL.md). Codex gets Governance and twelve specialist chats; Claude gets role adapters with manual specialist selection. One complete-plan APPROVE covers setup; native capability failures remain incomplete initialization.

Twelve specialists maintain the project’s engineering artifacts. Stage 07 integrates priorities and progress. The [project assessment](00-governance/docs/stage-perspectives.md) draws on approved artifacts, observed results and current plans.
The canonical repository is [asdg](https://github.com/Elustondo-ai/asdg).
This consolidated pilot is a review candidate; packaging does not establish human approval or native enforcement.

![A verified ZIP carries one asdg folder into the developer's Git repository, where initialization creates local integrations and state.](docs/images/distribution-flow.svg)

## Standalone source and contributions

This repository root is the intended canonical development and distribution source; consumers receive it under `<project>/asdg/`.
The prepared cutover is pending human review and commit. No release assets are published here by this migration.
For a reviewed local clone, follow [Clone + Prompt](docs/install-clone-prompt.md); the source entry point is `scripts/init.py`.
Source-only migration evidence is retained under `docs/migration/`; review it before cutover.
Maintainers change definitions here, run the [build and verification commands](docs/distribution-build.md), review the resulting manifest and propose a focused change for human review.
Do not initialize the source checkout as an application. Source checks use `scripts/check.py`; installed-client checks use `asdg/scripts/cli.py verify`.
The catalogue's `asdg/` paths describe installed consumers, not a nested source directory.

## Quick Start — give your agent the repository URL

Ask your agent to use this repository's reviewed full commit and [clone installation prompt](docs/install-clone-prompt.md) to prepare installation in an existing Git project.
Review the complete preview before approving apply. Installation creates no sprint, hook trust or permission for project work.
A release ZIP may be built locally with [the documented builder](docs/distribution-build.md); do not assume new-repository release URLs exist.

## Start

Extract the ZIP so your existing Git root contains `asdg/scripts/init.py` beside the application files.
Python 3.9+ and Git are required. From that root, run:

```sh
python3 asdg/scripts/init.py --client codex --dry-run
# After reviewing and explicitly approving that plan:
python3 asdg/scripts/init.py --client codex --apply --plan TOKEN_FROM_PREVIEW
python3 asdg/scripts/cli.py verify
```

Choose `codex`, `claude` or explicitly `both`; preview is the default and application requires the exact plan token.
An existing canonical clone at an explicitly selected commit uses the same engine; see [installation](docs/installation.md).
First setup records a new project without starting a sprint; use `--project-status defining` for an existing project.
Repeat initialization preserves state and authored files. Conflicts stop setup; different versions require a reviewed upgrade.
ZIP installs need no sibling checkout or global command. Review and trust Codex hooks separately in the native client.

## Included

Governance 00, stages 01–12, an explicit methodology Admin role, shared skills, client adapter templates,
the initializer, deterministic status/evidence engine, sprint checks and activity recorder.
Optional SDK advice and OpenSpec integration require their own dependencies and explicit workflows.
Presentation/video production, component authoring and legacy provider automation stay in the canonical repository outside this core ZIP.
Client evidence belongs in `docs/asdg/`; durable workflow state belongs in `.asdg/`; disposable logs belong in `logs/`.

## Read next

- [Installation and ownership](docs/installation.md) and [client integrations](docs/client-integrations.md).
- [Workflow usage](docs/usage.md), [Codex setup prompt](CODEX-PROMPT.md) and [lifecycle baseline](docs/lifecycle-baseline.md).
- [Build and verification](docs/distribution-build.md), [source provenance](docs/provenance.md) and [review loop](docs/review-loop.md).
- [Promote and upgrade](docs/synchronization.md): preview local methodology differences and explicitly apply a reviewed, conflict-free plan.
- [Historical pilot checks](docs/verification.md) and [native integration limits](docs/native-integration.md).

Skill notation is `$name` in Codex and `/name` in Claude Code. Session roles and attitudes grant no extra authority.
Initialization prepares the approved client team; it creates no sprint, release, human acceptance or hook trust.

## Standalone component development

Pablo assigns provider component work to ASDG-09 in a disposable checkout. He reviews the resulting Git patch and applies it from his own terminal. Admin maintains the policy and its checks. The source-only operator procedure is in `scripts/provider_component/review.md`.
