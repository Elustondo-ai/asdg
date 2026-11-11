# Architecture

Native name: `asdg_05`. Stable role: `ASDG-05`.
This folder owns the specialization, not the consuming project's results.

| Entry | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Role entry point, boundaries and self-explanation |
| [types](types/contract.md) | Input/output contract; no mandated type language |
| [tests](tests/acceptance.md) | Role interview and negative-boundary acceptance cases |
| [local skill](skills/propose-architecture/SKILL.md) | Architecture analysis and bounded decision documentation |
| [Decision foundations](docs/architectural-decisions.md) | Why, alternatives, consequences and revisit evidence |
| [ASDG Decision](../skills/asdg-decision/SKILL.md) | Context-aware analysis and reusable visual decision packages |

Shared [documentation](../skills/asdg-documentation/SKILL.md) remains single-source.
Using a capability does not grant its caller a new responsibility or write authority.

## Review

Ask Codex to spawn `asdg_05`, read this package and introduce itself.
Ask an in-scope question, then request an excluded deliverable.
Expect a truthful proposal or an `OUT_OF_SCOPE` return, never fabricated execution.
The contract permits assigned decision documentation; production implementation remains excluded. Native behavior needs separate evidence.
See [package catalogue](../README.md) and [runtime rules](../00-governance/docs/runtime-contract.md).

## Project artifacts

Record the selected architecture, its constraints and design decisions. Link implementation evidence for as-built claims. See the [stage layout](../00-governance/docs/stage-layout.md).
