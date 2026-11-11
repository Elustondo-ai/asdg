# Observability

Native name: `asdg_12`. Stable role: `ASDG-12`.
This folder owns the specialization, not the consuming project's results.

| Entry | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Role entry point, boundaries and self-explanation |
| [types](types/contract.md) | Input/output contract; no mandated type language |
| [tests](tests/acceptance.md) | Role interview and negative-boundary acceptance cases |
| [local skill](skills/derive-insights/SKILL.md) | Bounded procedure, explicitly loaded by this agent |

Shared [documentation](../skills/asdg-documentation/SKILL.md) remains single-source.
Using a capability does not grant its caller a new responsibility or write authority.

## Review

Ask Codex to spawn `asdg_12`, read this package and introduce itself.
Ask an in-scope question, then request an excluded deliverable.
Expect a truthful proposal or an `OUT_OF_SCOPE` return, never fabricated execution.
Owned documentation is writable without a sprint under [role ownership](../00-governance/docs/documentation-authority.md); application execution and native enforcement require separate evidence.
See [package catalogue](../README.md) and [runtime rules](../00-governance/docs/runtime-contract.md).

## Project artifacts

Link observations and feedback to measured signals, interpretations and lessons. See the [stage layout](../00-governance/docs/stage-layout.md).

Analyze supplied latency observations and incident feedback; a request to implement a fix or reprioritize approved scope is OUT_OF_SCOPE.
