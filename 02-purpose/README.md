# Purpose

Native name: `asdg_02`. Stable role: `ASDG-02`.
This folder owns the specialization, not the consuming project's results.

| Entry | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Role entry point, boundaries and self-explanation |
| [types](types/contract.md) | Input/output contract; no mandated type language |
| [Completion](types/completion.md) | Agent readiness criteria and User acceptance of the exact baseline |
| [tests](tests/acceptance.md) | Role interview and negative-boundary acceptance cases |
| [local skill](skills/elicit-purpose/SKILL.md) | Bounded procedure, explicitly loaded by this agent |

Shared [documentation](../skills/asdg-documentation/SKILL.md) remains single-source.
Using a capability does not grant its caller a new responsibility or write authority.

## Review

Ask Codex to spawn `asdg_02`, read this package and introduce itself.
Ask an in-scope question, then request an excluded deliverable.
Expect a truthful proposal or an `OUT_OF_SCOPE` return, never fabricated execution.
Purpose documentation authoring is allowed under the contract; native behavior after this change is not yet tested.
See [package catalogue](../README.md) and [runtime rules](../00-governance/docs/runtime-contract.md).

## Project artifacts

Explain who needs the system, why it matters and what outcomes would demonstrate value. See the [stage layout](../00-governance/docs/stage-layout.md).
Link the illustrated `01-purpose.md` from the stage README. Register any additional documents used for the [two-gate Purpose review](types/completion.md).
