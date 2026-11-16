# Team names, IDs and specifications

[Source](cli_team_model.py). Pure rules for saved teams under [team workflows](../../00-governance/docs/team-workflows.md). It reads no file, runs no command and knows no runtime; a later writer and CLI call it.
[`cli_team`](cli_team.md) and the other client's initialization plan are untouched.

| Interface | Responsibility |
| --- | --- |
| `clean_name(raw)` | Display name: trimmed, single spaces, NFC, at most 80 characters. Keeps the user's casing. |
| `name_key(raw)` | Comparison identity: NFKC and case-folded. Never stored as an ID and never used as a path. |
| `find_collision(name, specs)` | The saved specification with the same identity, or `None`. |
| `new_team_id(existing=())` | `team-` plus sixteen random hex digits. It takes no name. |
| `validate_spec(spec, *, project_id, role_ids, coordinator)` | A validated deep copy of a version 1 specification, or `Conflict`. |

## Names

A name is data. Lifecycle words such as `start`, path-like text and shell characters are valid names, because only the opaque ID ever names a file.
Rejected: non-text, empty or blank names, more than 80 characters, and any control, format, private-use or line-separator character, including tab, newline and zero-width characters.
`Architecture Review`, ` architecture   REVIEW ` and full-width `ＡＲＣＨＩＴＥＣＴＵＲＥ review` share one identity.

## Specification, version 1

Every object has exactly its listed fields; unknown or missing fields are rejected.

| Field | Rule |
| --- | --- |
| `schema_version` | Exactly the integer `1`. Any other value, including `1.0`, `"1"` and `true`, is refused as unsupported, not guessed. |
| `team_id`, `revision` | An opaque ID as above; a positive integer. |
| `name`, `purpose` | Already in saved form: what `clean_name` or the text rule returns. Purpose is at most 600 characters. |
| `project_id` | Equals the caller's project binding ID. |
| `type` | `sessions`, `subagents` or `teammates`: how members exist. All three collaborate. Earlier labels are refused. Several teams may share a type. |
| `members` | At least one of `slot`, `role_id`, `responsibility`. Slots are unique lowercase words joined by hyphens; several slots may hold one role. Roles come from the caller's catalogue, so Admin is excluded. |
| `lead` | The native dispatch lead. `null` for sessions, which forbids no coordinator: `rules.integration_owner` still names that slot. Otherwise a slot held by the coordinator role. |
| `rules` | `collaboration`, `outputs`, `completion`, `handoff` as text; `integration_owner` as a slot; `work` as `read-only` or `documents`. |
| `provenance` | `generator`, `asdg_build` or `null`, `created_at`, and `definitions`. `created_at` is an existing UTC date and time in the exact form `2026-11-14T20:00:00Z`; impossible dates and times are refused. |
| `provenance.definitions` | Empty for sessions. Otherwise `path` matching `.claude/agents/asdg-*.md`, a member's `role_id`, `sha256` and `template_sha256`. |

## Limits

Validation proves shape only. It does not show that a role is loaded, a definition exists on disk, a team can run on a surface, or that any rule is enforced.

```python
checked = validate_spec(spec, project_id='client', role_ids=roles, coordinator='ASDG-COORDINATOR')
```
