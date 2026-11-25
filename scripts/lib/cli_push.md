# Coordinate ASDG replacement

[Source: cli_push.py](cli_push.py) joins source/ownership validation, client integration rendering and recoverable transactions into the replacement command.

![Preview, locked recheck, backup/write, verification and publication remain distinct phases.](../../docs/images/push-replace-flow.svg)

| Collaborator | Responsibility |
| --- | --- |
| [Inventory](cli_push_inventory.md) | Strict JSON, source integrity, ownership and target binding. |
| [Integrations](cli_push_integrations.md) | Shared blocks, TOML, hooks and native adapter files. |
| [Transaction](cli_push_transaction.md) | Cooperative lock, durable backups, publication and recovery. |
| [Project](cli_project.md) | Initialized-client structure and integration status. |

## Interface

`preview(source_path, target_path)` returns a timeless plan with exact bytes, hashes, conflicts, audit intent and verification inputs. `replace(..., apply=False, expected_plan=None)` previews or requires the exact digest, rechecks under the lock and executes.

`recover(target, transaction_id, mode)` resumes the saved transaction or requests guarded rollback. `verify_payload(root, verification)` checks bytes/modes, preserved evidence, target identity and integrations before publication. `verify_installed(target)` checks recorded ownership and client structure.

`serializable(report)` represents bytes as base64 for JSON. `render(report)` summarizes changes, conflicts, recovery or verification. The CLI handles exceptions as operational failure.

## State and effects

Ownership has no clock value. Material equality excludes transaction provenance so repeat runs do not recursively replace receipts. The plan binds fixed audit intent; timestamps and realized ledger bytes belong to execution.

The synchronization record remains an `upgrade` with a `push-replace` method, preserving other upstreams. A matching commit establishes build identity; a working snapshot removes stale attribution. Project binding, sprint state and documents remain unchanged.

Unproven ownership, unsafe paths, incompatible state, ambiguous integrations, stale plans and conflicting recovery raise `Conflict`. Native sessions, discovery and trust remain separately observable. See the [operator guide](../../docs/push-replace.md).
