# Operations

Native name: `asdg_11`. Stable role: `ASDG-11`.
This folder owns the specialization, not the consuming project's results.

| Entry | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Role entry point, boundaries and self-explanation |
| [types](types/contract.md) | Input/output contract; no mandated type language |
| [tests](tests/acceptance.md) | Role interview and negative-boundary acceptance cases |
| [local skill](skills/assess-operations/SKILL.md) | Bounded procedure, explicitly loaded by this agent |

Shared [documentation](../skills/asdg-documentation/SKILL.md) remains single-source.
Using a capability does not grant its caller a new responsibility or write authority.

## Review

Ask Codex to spawn `asdg_11`, read this package and introduce itself.
Ask an in-scope question, then request an excluded deliverable.
Expect a truthful proposal or an `OUT_OF_SCOPE` return, never fabricated execution.
Owned documentation is writable without a sprint under [role ownership](../00-governance/docs/documentation-authority.md); application execution and native enforcement require separate evidence.
See [package catalogue](../README.md) and [runtime rules](../00-governance/docs/runtime-contract.md).

## Project artifacts

Document operating procedures, observed deployment conditions and acceptance evidence. See the [stage layout](../00-governance/docs/stage-layout.md).

Review supplied staging test logs and an acceptance checklist; a request to deploy the release is blocked by evaluation mode and separate authority.
