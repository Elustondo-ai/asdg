# Sprint status mod

[Source](register.tsx). Keeps the project's ASDG sprint on screen in Claude, so nobody has to ask for status to know which sprint, branch and objective are current.
It is one hooks module, loaded by Claude from `.claude/skills/asdg-sprint-status/`; see [how mods are installed](../../README.md).

| Responsibility | Collaborators |
| --- | --- |
| Read the sprint record and the checked-out branch | `$.fs.read` on `.asdg/sprint.json` and `.git/HEAD`, relative to the session's working folder |
| Read the proposed next sprint while none is active | `$.fs.read` on `docs/asdg/07-planning/proposed-sprint.json`, kept by 07 Planning |
| Keep one `Sprint` value for the session | `$.state` through `atom`, `read`, `update`; contract in [the types](../types/index.d.md) |
| Draw a row above the prompt and a pane | `ui.render` on `AbovePrompt` and on `Pane` with request ID `sprint` |
| Open the pane on request | Command `/asdg-sprint-pane`, and the row's Details button |

## What happens

`load($)` returns a `Sprint`: `isAsdgProject` is false when the record cannot be read or parsed, and every field then holds its empty value.
The branch is the name after `ref: refs/heads/`, or the first seven characters of a detached commit, or `null` outside Git.
`refresh($)` loads and writes the state only when the value changed, so a quiet poll redraws nothing. It never throws.
It runs at `session.start`, every 20 seconds, after each Bash tool call and at `turn.complete`, which covers a sprint started, closed or moved to another branch.

## What the user sees

- Active sprint: `SPRINT-003 active · sprint-03 · <objective>` and a Details button.
- No sprint: `No active sprint · <branch>`, followed by `· next: <id> <state>` when 07 Planning's proposed-sprint file exists.
- No sprint record: nothing; the row is left to the engine.
- Pane: status, branch, objective, scope and numbered acceptance criteria; with no active sprint, the proposed next sprint's id, state, previous sprint, objective and plan path; as a minimized widget, status, branch and the next sprint's line.

## Effects and limits

Read-only. It writes no file, starts no turn and sends nothing outside the machine. It never starts, closes or changes a sprint.
It shows what the record says; it does not check that the branch matches the sprint or that the scope is respected.
The proposed-sprint file is 07 Planning's statement, not sprint state or approval; its `state` text is shown as written. Fields: `sprint_id` (required), `state`, `objective`, `plan`, `previous`.
The row yields to a survey. Colors and layout are the surface's; on the desktop app the row may wrap to several lines.

## Example

```text
/asdg-sprint-pane    → opens the pane and answers "Sprint pane opened."
```

Tests: [register.test](register.test.md).
