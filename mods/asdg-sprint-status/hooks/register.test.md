# Sprint status mod tests

[Source](register.test.tsx). Runs [the mod](register.md) against Claude Code's own engine with `claude plugin test asdg/mods/asdg-sprint-status`.

| Test | Evidence |
| --- | --- |
| The band names the active sprint and its branch | On the terminal and desktop surfaces the row reads `SPRINT-003 active`, and the second text carries the branch and the objective |
| The pane lists scope and acceptance criteria | The pane shows a scope path and the second criterion with its number |
| An inactive sprint says so | The row reads `No active sprint` |
| With no active sprint, the band and pane show the proposed next one | The row carries `next: SPRINT-004 awaiting approval`; the pane reads `Next sprint: SPRINT-004 · awaiting approval` |
| An active sprint hides the proposed one | With an active record the row carries no `next:` |

## Fixture

`engine(on, files)` stands for the engine beneath the mod: it answers command registration, pane opening and session start, refuses `clock.every` so no timer fires, and serves `fs.read` from an in-memory map.
The engine hands paths over absolute, so the map is matched by path suffix. A path not in the map rejects, as a missing file does.

## Limits

These tests mount the drawing in a test kit. They do not show that the desktop app draws the row, that a project mod is loaded from `.claude/skills/`, or that the 20-second poll runs.
Drawing was observed once, by hand, on 16 November 2026 in the Claude desktop app, with the mod loaded from a session mods folder and not yet from a project's `.claude/skills/`.
