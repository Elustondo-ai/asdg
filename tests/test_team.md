# Team plan regressions

[Source](test_team.py). Tests the deterministic preview boundary used by the single [Create team workflow](../skills/asdg-create-team/SKILL.md).

| Evidence | Coverage |
| --- | --- |
| Fresh inventory | Thirteen create effects, Governance first, Admin excluded |
| Complete inventory | Exact IDs reused, no state mutation, stable re-run |
| Partial inventory | Only confirmed missing roles planned |
| Invalid inventory | Duplicate IDs/roles, wrong project, pending activation and scoped sessions rejected |
| Unknown inventory | No assumed missing roles or speculative creation |
| Client modes | Claude adapters, Codex native chats; no invented Claude API |
| Workflow contract | APPROVE before apply, team after files, existing activation checks retained |

`test_install` verifies team effects enter the init approval digest, stale inventories fail before writes, Governance adapters exist and repeat setup preserves bytes.
These automated tests validate plans, file transactions and instruction contracts. They do not demonstrate native creation, role activation, UI ordering, Claude loading or hook trust. Fresh-project trials remain required.
