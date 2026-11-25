# Replacement inventory boundaries

The replacement planner needs exact package membership and a verified client binding before it can decide which files to touch. This module reads those inputs without importing any installed client Python code. It never writes a file or changes Git state.

| Collaborator | Responsibility | Information passed onward |
| --- | --- | --- |
| Canonical package and manifest | Name exact portable files and bind their bytes. | `validated_source` freezes bytes, source identity, catalog and generator digests. |
| Client project, sprint and lifecycle | Establish the initialized target and compatible preserved state. | `target_identity` returns root, normalized Git identity, common directory and binding hash. |
| Existing index and manifest | Identify a reviewable first-adoption inventory. | `legacy_distribution_inventory` returns exact paths and evidence hashes; unknown neighbors are excluded. |
| Ownership receipt schema | Constrain recorded categories, selectors and original values. | `validate_ownership` rejects unknown fields, overlaps, foreign clients and preserved-state targets. |
| Replacement planner | Compare validated inventory with incoming payload. | The planner binds all observed bytes into its plan and obtains explicit apply intent. |

## Public interface

`validated_source(source)` accepts a standalone canonical Git root. It requires an exact manifest, the canonical origin, a committed HEAD and the thirteen lifecycle identities. The returned `files` mapping is package-relative bytes; `identity` records repository, package and manifest digests, with a commit only when the entire package matches that commit. Dirty package snapshots remain usable after manifest reconciliation, with `commit: null`.

`target_identity(root)` requires an initialized embedded client at its Git worktree root. It validates project layout and reads sprint/lifecycle through the executing distribution's validators. It preserves their bytes and rejects the canonical provider as a client.

`legacy_distribution_inventory(root, source=None)` requires a matching installed index/manifest shape and a manifest-bound index hash. When a source is supplied, descriptor and catalogue hashes must match current canonical bytes or a historical delivery. Its candidate list is local unauthenticated evidence, reviewed by the exact apply plan; it cannot authenticate historical ownership.

`validate_ownership(value, target=None, clients=None)` enforces the packaged closed JSON schema plus exact category destinations, selectors, original-value hashes and overlap rules. Optional target and client arguments require exact binding. `load_ownership` reads the client record or returns `None` when absent. Receipt validity never establishes human approval.

`read_safe`, `safe_relative`, `strict_json`, `canonical` and `digest` supply shared read-only primitives. Paths must be normalized and exact; symlinks, multiple hard links, nested repositories, malformed JSON and duplicate keys raise `cli_files.Conflict`. Shared JSON/TOML values hash canonical JSON; marked blocks hash UTF-8 text.

The file readers inspect paths and opened file identities. They are conservative checks, not a sandbox against arbitrary hostile concurrent filesystem changes. The transaction layer must recheck dependencies under its own cooperative lock.

Tests are described in [inventory acceptance](../../tests/test_push_inventory.md). The complete replacement command owns writes, backups and recovery separately.
