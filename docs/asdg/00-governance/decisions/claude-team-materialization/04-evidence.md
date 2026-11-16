# Evidence and limits of the proposal

ASDG source baseline: `f2b8591a39ff7b65f820baaa2b54b572763363e2`. Source inspection and public documentation are evidence for design, not proof of native runtime behavior. Official pages were checked again on 2026-11-14 after Claude's review. The baseline below predates [Gate 1 observations](16-gate1-native-report.md); [the naming amendment](17-team-materialization-names.md) maps its historical labels to current names.

## Current ASDG sources

- [Team helper](../../../../../scripts/lib/cli_team.py) reports Claude native chats unsupported; replace this with capability-specific reporting, not an unconditional supported flag.
- [Client renderer](../../../../../scripts/lib/cli_clients.py) shares templates across clients and strictly validates `integrations.json`. Keep that schema unchanged by storing new provenance in team records.
- [Project generator](../../../../../scripts/lib/cli_project.py) currently generates the implementation hook for the other client; it does not establish Claude enforcement.
- [Create Team](../../../../../skills/asdg-create-team/SKILL.md), [session policy](../../../../../skills/asdg-focus/session-policy.md), and [runtime contract](../../../../../00-governance/docs/runtime-contract.md) need bounded team-workflow allowances while preserving per-session role authority.
- [Documentation authority](../../../../../00-governance/docs/documentation-authority.md) permits this proposal; [write exceptions](../../../../../00-governance/docs/write-exceptions.md) requires Admin maintenance/human review before new executable exceptions.

## Official Claude findings

[Desktop reference](https://code.claude.com/docs/en/desktop#whats-not-available-in-desktop) explicitly says native agent teams are CLI-only. Desktop documents subagent/background-task panes. This corrects the review's claim that Desktop documentation is silent; installed-version behavior remains untested.

[Subagents](https://code.claude.com/docs/en/sub-agents) documents reusable definitions, bounded tool profiles, and a restart when a newly created agents directory is not detected. Nested subagents are currently allowed by default; exclude spawning tools from worker profiles and test this. Existing watched directories can update the next delegation within seconds. ASDG conservatively requires a fresh session after changes in v1 and forbids repair during an active run. Sessions uses Focus, not an unspecified generated role loader.

[Agent teams](https://code.claude.com/docs/en/agent-teams) supports one team per session, not nested teams. Teammates do not inherit lead conversation history. Definition `skills` is ignored; tool/permission and body behavior differ by display mode. In-process appends the definition body; split panes replace the default body. V1 targets in-process only. Automatic teammate plan approval cannot meet ASDG human-approval requirements. Runtime-owned team configuration is temporary; ASDG must not pre-author it.

The same team guide recommends bounded tasks, separate file sets, small teams, and research/review first. The proposed one-active-team-per-project rule is stricter ASDG policy, not a native guarantee. Creating reusable specifications and matching goals to assignments are ASDG additions.

[Hooks](https://code.claude.com/docs/en/hooks#common-input-fields) now documents identifiers for subagents and in-process teammates. This corrects the review's documentation uncertainty, but event delivery, path enforcement, shell/MCP coverage, and crash recovery still require actual tests. Hooks must be reviewed and trusted; naming one is not proof of enforcement.

[Skills](https://code.claude.com/docs/en/skills) documents arguments and explicit invocation controls. Parse argument text as data with quoted names; render creation/lifecycle adapters with `disable-model-invocation: true`. Use separate Claude templates so this does not change another client's workflow.

## Unverified and deferred

[Sandbox protected paths](https://code.claude.com/docs/en/sandboxing#protected-paths) can prevent shell mutation of Claude configuration and external directories. Gate 1 checks the actual surface; each apply offers a human-run fallback with the same reviewed token. No bypass or blanket permission relaxation is proposed.

At the original design baseline, no native team trial, permission test, reload experiment, or hook test had been performed. The later Gate 1 report records the observed subset and remaining gaps. Earlier shell inspection did not find `claude` on PATH; that says nothing about Desktop's bundled engine. Record actual surface/version in increment 1.

The documented CLI-only Teammates option is a proposal for the user's requested experiment. It is not permission to install the CLI, change security settings, or move an existing session. Desktop dynamic workflows are a distinct capability and are not silently substituted.

Documents, generated definitions, and saved specifications can make Git dirty. Team setup reports that fact; sprint start keeps its clean-tree requirement. Application coding is deferred until a separate enforcement increment.

## Review status

[Claude's review](06-review-claude-code.md) is preserved as received. [Round 2](09-review-claude-round2.md) and [round 3](11-review-claude-round3.md) completed the review loop. The final verdict finds no blocker and readiness for Gate 1, not user approval or native verification. Its non-blocking later-increment clarifications are incorporated; those final editorial additions were not separately re-reviewed.

Existing diagrams were rendered and visually checked. Markdown links, page lengths, and latest exact-hash receipts are checked on each revision; full embedded Markdown rendering and live runtime behavior remain unverified.
