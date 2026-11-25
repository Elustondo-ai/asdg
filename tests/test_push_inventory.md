# Replacement inventory acceptance

These tests exercise the read-only ownership boundary before a replacement plan can reach the transaction writer. They create temporary Git repositories and never target a real project.

| Fixture collaborator | What the fixture supplies | Boundary asserted |
| --- | --- | --- |
| Canonical Git source | Manifest-bound package and canonical origin. | Altered bytes fail integrity; a resealed dirty snapshot loses commit attribution. |
| Legacy embedded client | Exact old index plus an unknown adjacent document. | Only indexed candidates are returned; changing the inventory breaks its manifest binding. |
| Local filesystem | Hard links, symlinks and a nested Git marker. | Every unsafe managed path fails before mutation. |
| Ownership JSON | Both clients, unexpected fields and forged selectors. | Schema validity alone cannot widen writable category scope or move ownership to another project. |

Run `python3 -B -m unittest discover -s tests -p test_push_inventory.py -v` from the canonical source. The fixtures supply the ownership schema locally, allowing source-package assembly to proceed independently of these checks.

The tests cover deterministic JSON, duplicate-key rejection, canonical origin checks, source integrity, exact commit attribution, linked/nested path rejection, unknown-file preservation, receipt closure, target/client binding, overlapping claims and original-value hashes.

They do not authenticate local receipts, test native Claude/Codex discovery, or prove transaction recovery. Those responsibilities belong to separate integration and transaction tests.
