# Team sidebar ordering

Use only within [Create team](SKILL.md).

## Keep lifecycle order stable

After setup, arrange only the verified target project's ASDG team chats by role selector in this fixed sequence. Human-facing stage names follow the [lifecycle table](../../docs/lifecycle-baseline.md):

00 Governance → 01 Context → 02 Purpose → 03 UseCases → 04 EvalStrategy →
05 Architecture → 06 POC → 07 Planning → 08 Specs → 09 Coding →
10 ReviewQA → 11 Operations → 12 Observability.

Discover supported sidebar tools and current sorting preferences (`list_threads` in Codex); never assume returned recency order is sidebar display order.
If manual sorting changes a shared preference, explain that it affects Recents and chats across projects and Codex/Work; obtain explicit approval before changing it. Existing manual sorting needs no preference change.
Prefer supported app tools with their current schemas. Project-list or section reordering is not project-chat reordering; never invent a project-chat API or edit internal app databases or configuration stores.
Apply a supported fixed order only to confirmed role-to-chat IDs; unresolved roles or ambiguous matches stay unresolved. Preserve unrelated sidebar items and their positions; decline operations whose scope cannot preserve them.
Reuse existing chats; preserve contents, identities, role selections, subjects, attitudes, native notification dots and unread states. Do not open/mark chats read, send activity to simulate order, rename, pin or move them to force sorting.
If supported tools cannot set fixed project-chat order, explain the limitation and provide manual instructions: inspect the sidebar sort control, select manual order only after approval of any shared scope, then drag verified team chats into the sequence above without moving unrelated items. If the UI lacks fixed ordering too, report it unavailable.
Record intended order, target IDs, preference approval if needed, attempted operations and acknowledgements. Separate tool readback from visually verified results; say when visual verification was unavailable. An acknowledgement alone never proves visible order or stability after activity.
Creation and ordering must not start project work or a sprint; editing this policy authorizes neither team creation nor reordering.

## In Claude

Use this part only on a surface with native sidebar tools, such as the Claude desktop app, after the roster is confirmed.
Role chats started from the team lead chat are listed under it, and role titles begin with 01–12, so sorting the sidebar by name shows lifecycle order. No drag order, pin or numeric prefix on the lead is needed.
Read the current sidebar sort first. If it is already by name, change nothing and say so.
Otherwise offer this as the default step, once: set the sort to name (`sort_by: alpha` in the desktop app's sidebar view tool). Say that the setting is shared by every project in the sidebar, and change it only on the user's yes; a no leaves it as it is.
Title the calling chat as the [team lead](../asdg-focus/rename-chat.md#team-lead-title).
Report the setting's readback separately from what was visually verified; a readback of `alpha` does not prove the visible order.

