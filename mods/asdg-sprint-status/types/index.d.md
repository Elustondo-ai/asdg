# Sprint status mod state contract

[Source](index.d.ts). Declares the one value [the mod](../hooks/register.md) keeps in Claude's session state, so `claude plugin validate` can hold the module to it.

| Field of `Sprint` | Meaning |
| --- | --- |
| `isAsdgProject` | False when `.asdg/sprint.json` is missing or unreadable; the row then stays empty |
| `status` | The record's `status`, such as `active` or `inactive`; `unknown` when absent |
| `id`, `objective` | `sprint_id` and `objective` from the record, or `null` |
| `scope`, `acceptance` | The record's `scope` and `acceptance_criteria`, strings only |
| `branch` | Checked-out branch, short commit when detached, or `null` |
| `next` | The proposed next sprint (`id`, `state`, `objective`, `plan`, `previous`) from `docs/asdg/07-planning/proposed-sprint.json`; `null` when a sprint is active or the file is absent or has no `sprint_id` |

The module augmentation registers the key `asdg-sprint-status.sprint` as `Shaped<Sprint | null>`.
`Shaped` lets the module tag what it stores (`sprint-2`); change the tag whenever these fields change, so a value stored by earlier code is read as empty instead of trusted.
The value lives for the session only. Nothing is written to `$.store` or to the project.
