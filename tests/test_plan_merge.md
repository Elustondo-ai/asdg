# Project plan merge tests

These tests give maintainers evidence that field-wise synchronization preserves intent before a provider or file writer acts.

| Fixture or test group | Responsibility | Collaborator |
| --- | --- | --- |
| `fields`, `item`, `cache` | Construct independent local records with explicit prior values and private notes | Cache schema |
| `remote`, `snapshot` | Construct complete normalized provider records without network access | Provider contract |
| `MergeTests` | Assert merge results, minimal mutation payloads, conflicts, imports and deterministic order | `cli_plan_merge.reconcile` |
| `ValidationTests` | Reject schema errors, duplicate identities, mismatched bindings and partial snapshots | Cache/snapshot validation |

The comparison tests independently change local and remote versions, then inspect observable operations and the proposed cache. They do not assert implementation details or require live GitHub access.

Coverage includes no-op purity, local exports, remote imports, disjoint and equal edits, conflicts, missing bound issues, marker identity changes, new issue creation and post-creation binding, private-note/source preservation, explicit clearing and independent issue/Project state.
First-create recovery is accepted only when existing issue fields agree; conflicting unbased edits remain blocked.
Duplicate IDs, duplicate numbers, invalid states, unknown schema fields, invalid repository names and incomplete remote snapshots fail before producing mutations.
Item order does not change the generated result. A second comparison after successful remote readback produces no operations.

Run `python3 -B -m unittest discover -s tests -p 'test_plan_merge.py' -v` from the source root.
These portable tests prove pure reconciliation behavior; they do not prove GitHub permissions, transport pagination, native skill invocation or an atomic remote transaction.
