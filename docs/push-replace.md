# Replace ASDG-owned client files

Use push replacement when you deliberately want a client to adopt one selected canonical ASDG package and discard customizations to files ASDG owns. Claude Code and Codex integrations are regenerated according to that client's recorded selection.

![A pinned source and bounded inventory produce an exact plan; backups precede writes and verification precedes publication.](images/push-replace-flow.svg)

The [catalog](../metadata/push-replace-catalog.json) defines ownership categories. The command resolves them to exact files, blocks and settings; directory membership never establishes ownership. Application files, `docs/asdg/`, sprint/lifecycle state, team data, existing worktrees and unrelated configuration remain outside replacement.

## Preview and apply

Run the selected canonical checkout's CLI with Python 3.9 or newer. Codex shared TOML configuration additionally needs Python 3.11's `tomllib` or an installed `tomli` parser; unsupported interpreters stop before writes.

```sh
python3 scripts/cli.py push-replace --source /path/to/asdg --target /path/to/client --dry-run --json
python3 scripts/cli.py push-replace --source /path/to/asdg --target /path/to/client --apply --plan DIGEST
python3 scripts/cli.py push-replace --target /path/to/client --verify --json
```

The preview includes exact proposed bytes in base64, before/after hashes, clients and conflicts. Apply requires its exact digest. Changes to source, destination, ownership evidence or review history invalidate the plan. No network lookup selects a version; an uncommitted source snapshot is never attributed to an older commit.

The target must already be initialized. First adoption uses the exact installed package inventory and recognized generated integrations as bounded local evidence; unknown collisions block replacement. Later runs use the validated [ownership receipt](../metadata/push-replace-ownership.schema.json). The receipt is not an authenticated approval.

Shared files retain unrelated content. The bootstrap remains first in `AGENTS.md`; Claude receives an explicit AGENTS import unless a user import already supplies it. Codex's feature key and exact hook registrations are reconciled without claiming hook trust. Unsupported or ambiguous syntax blocks the plan.

## Backups and recovery

Changed runs save original bytes, modes and intended output in `.asdg/backups/push-replace/TRANSACTION_ID/`, then journal progress. A successful no-op creates no backup, event or successor receipt. Existing backups are retained.

```sh
python3 scripts/cli.py push-replace --target /path/to/client --recover TRANSACTION_ID --recovery rollback --json
python3 scripts/cli.py push-replace --target /path/to/client --recover TRANSACTION_ID --recovery resume --json
```

Resume uses the saved transaction and verification contract. Rollback restores only files still matching recorded transaction states. Later user edits, unsafe paths or tampered backups stop recovery. The cooperative lock coordinates this command; it cannot stop arbitrary external editors.

Ownership and review records publish after payload verification. Old review events remain intact and new events transfer no approval. Replacement starts no teams or sprints and does not commit, publish, deploy or trust hooks.

File verification is portable. Refresh the client and try `/asdg-help` in Claude Code or `$asdg-help` in Codex to observe native discovery separately.
