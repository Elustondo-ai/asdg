# Plan roles: what each specialist definition would change

This lists, role by role, what the current definitions say and what they would have to say to match the [selected division](README.md); its diagram shows how the roles hand work to each other.
It is a proposal for a maintenance task. Nothing here is applied: changing role definitions needs ASDG Admin, selected by Pablo, with this list as its scope.

## Responsibilities and collaborators

| Role | Its definition says today | Proposed change | Works with |
| --- | --- | --- | --- |
| 07 Planning | "Prepare sprint scope, bounded tasks, dependencies, sequencing, and explicit handoffs"; returns "sprint plan and task proposals" | Assemble epics and stories word for word from the specialists' documents; never write or reword content; report the assembled plan back for review; propose the Product Backlog order and the Sprint Backlog; stop proposing tasks | 02 to 05 for content, 08 for tasks, Pablo for approval |
| 08 Low-Level Design | "Specify concrete interfaces, contracts, behavior, edge cases"; returns "actionable contracts for the implementation agent" | Add: split each approved story into tasks, own the words of every task, and answer the issues and blockers raised on it | 07 for stories, 09 for execution |
| 09 Coding | "Implement only approved component-scoped tasks"; must not "change approved requirements or architecture" | Add: update task status, comment, and signal issues and blockers to 08; never change what a task is | 08 |
| 02 Purpose | "Clarify why the system exists"; desired outcomes, constraints, acceptance questions | Add: owns the why of each epic and story; reviews the assembled plan when 07 reports back | 07 |
| 03 Use Cases | "Define domain model, use cases, actors, interactions, and observable outcomes" | Add: owns the scenarios and observable outcomes quoted in stories; reviews the assembled plan | 07 |
| 04 Benchmarks | "Propose tests, criteria, and decision evidence" | Add: owns the tests and criteria quoted as acceptance; reviews the assembled plan | 07 |
| 05 Architecture | "Design architecture boundaries, components, interfaces, decisions and trade-offs" | Add: owns the constraints and component boundaries quoted in stories; reviews the assembled plan | 07, 08 |
| 01, 06, 10, 11, 12 | No statement about plan items | No ownership change proposed; they follow the shared page below | 07 |

## Files a maintenance task would touch

- **One new shared page** in `00-governance/docs/` with the vocabulary and the ownership table, linked from the runtime contract that every role already loads. This is what lets every specialist know its part without repeating the table thirteen times.
- **Seven role packages:** each role's `AGENTS.md` and `types/contract.md` for 02, 03, 04, 05, 07, 08 and 09, plus Planning's `prepare-plan` procedure.
- **Their generated copies:** the Codex agent templates under `templates/.codex/agents/` repeat each role's responsibility sentence; this was confirmed for 02, 07 and 09.
- **Package records:** the role acceptance pages where they quote the old wording, the manifest, and exact-hash receipts for every edited file.

## Decisions needed before the edit

- Whether copied text carries a source link and hash, and whether Planning must report gaps instead of filling them. Both are proposed in the [record](README.md).
- How a story's status is set.
- Whether Planning's sprint task list, as written in a client today, is replaced by 08's task split or kept as an ordered index of it.
- Whether the sync enforces this ownership per field. That would make story text flow one way, from the owner's document to GitHub.
