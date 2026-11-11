# ASDG Coordinator — package

Native name: `asdg_coordinator`. Stable role: `ASDG-COORDINATOR`.
This folder owns the specialization, not the consuming project's results.

| Entry | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Role entry point, boundaries and self-explanation |
| [docs](docs/README.md) | Package guide and relevant shared material |
| [types](types/contract.md) | Input/output contract; no mandated type language |
| [src](../scripts/lib/README.md) | Package-specific operations, when implemented |
| [tests](../tests/acceptance.md) | Role interview and negative-boundary acceptance cases |
| [local skill](skills/review-routing/SKILL.md) | Bounded procedure, explicitly loaded by this agent |

Shared [documentation](../skills/asdg-documentation/SKILL.md) remains single-source.
Using a capability does not grant its caller a new responsibility or write authority.

## Review

Ask Codex to spawn `asdg_coordinator`, read this package and introduce itself.
Ask an in-scope question, then request an excluded deliverable.
Expect a truthful proposal or an `OUT_OF_SCOPE` return, never fabricated execution.
Owned documentation is writable without a sprint under [role ownership](../00-governance/docs/documentation-authority.md); application execution and native enforcement require separate evidence.
See [package catalogue](../README.md) and [runtime rules](docs/runtime-contract.md).

## Project status

Read the [domain artifacts](docs/stage-layout.md), operational evidence and Stage 07 plan to produce the [Intended / Actual / Planned assessment](docs/stage-perspectives.md). Cite the source of each claim and report missing evidence as unknown.
