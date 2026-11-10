# Team effects in an initialization plan

[Source](cli_team.py). The canonical [Create team workflow](../../skills/asdg-create-team/SKILL.md) owns creation, reuse, activation and client behavior.

| Collaborator | Responsibility |
| --- | --- |
| `catalogue` | Supplies Governance and stages 01–12; Admin stays excluded |
| `team_plan(root, repo, clients, inventory=None)` | Validates supplied native receipts; returns deterministic create/reuse effects |
| `cli_install` | Includes those effects in the approval digest; installs files only |
| Create team | Reads actual native inventory, executes approved effects and confirms activation |

A native inventory contains `project_root`, native `project_id`, `inventory_complete: true` and `roles`.
Each role receipt contains `role_id`, `thread_id`, `project_root`, `activation: confirmed`, `subject: NoFocus`, and `attitude: NoAttitude`.
The agent supplies this evidence after native discovery; JSON assertions alone do not prove native state.
Distinct subject or attitude sessions remain preserved; unresolved candidates block planning rather than being omitted.
Duplicate roles/IDs, foreign projects, incomplete inventory and unconfirmed activation fail before file writes.
A complete inventory with missing roles plans only those missing roles. A matching team plans reuse of all thirteen IDs.
Absent inventory reports `NATIVE_INVENTORY_REQUIRED`; it never means an empty native project.
Claude uses the installed role/skill sources with manual Focus selection; no automatic Claude chat API exists in ASDG.
No shared active-role state or native chat database is introduced. The inventory is an external temporary review artifact.
Native actions happen after file verification, outside filesystem rollback. A partial native result is preserved and rediscovered before retry.
