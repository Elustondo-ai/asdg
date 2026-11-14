# Build identity

[Source](build_identity.py). Name every build by its canonical commit, so nobody has to bump a pilot number to tell builds apart.

| Responsibility | Collaborators |
| --- | --- |
| Derive `ASDG build <UTC committer time> · <short hash>` from one commit | Git (`show`, `ls-tree`), read-only |
| Attribute only package bytes that equal that commit's blobs | [`cli_install_source`](cli_install_source.md), [`build_distribution`](../build_distribution.md), [`cli_sync`](cli_sync.md) |
| Read, validate and describe a client's own `asdg/metadata/build.json` | [`cli_project.inspect`](cli_project.md), [`cli_status`](cli_status.md) |

```text
commit ──► commit_build ──► build.json ──► ZIP / clone install / upgrade ──► client asdg/metadata/build.json ──► status
             ▲ refuses unless every selected file equals the commit's blob
```

## Interfaces

- `commit_build(repo, commit, release, entries, prefix='')` returns the record below or raises `Conflict` when the commit cannot be read, is not a full ID, or any selected file differs (`commit_mismatch`).
- `commit_mismatch(repo, commit, entries, prefix)` returns the first differing path, `'(commit tree unavailable)'`, or `None`.
- `package_build(core, info)` accepts a shipped record only when its `snapshot_sha256` and `release` equal the frozen package; a mismatch raises.
- `installed_build(core, entries, release, legacy_commit)` never reads Git. States: `RECORDED`, `LOCAL_CHANGES` (selected files differ from the recorded snapshot), `NOT_RECORDED` (legacy install; displays `ASDG build not recorded`, plus the binding commit when still valid) and `INVALID`.
- `commit_package(repo, commit, prefix='')` reads the package list and every selected file as the commit recorded them (one `git cat-file --batch`), or returns `None`; update uses it to recover an installed baseline.
- `snapshot_sha256(entries)` equals the installer's package snapshot digest; `label(record)` gives the display text.

## Record (`metadata/build.json`)

`build_id` (`20261114T013334Z-1a2b3c4`), full `commit`, `commit_short` (7), `committed_at` (UTC, from the committer timestamp), `release` (the named version label, unchanged), `snapshot_sha256` and `attribution: PACKAGE_MATCHES_COMMIT`.
Only commit metadata and package bytes feed it, so rebuilding the same commit tomorrow yields the same identifier and bytes; two commits with the same timestamp differ by hash.
The record is never a package-list member: `distribution_files` and `methodology_path` reject it, so it cannot reference its own digest.

## Use

```python
record = commit_build(repo, head, '0.3.0-pilot.4', entries)
print(label(record))  # ASDG build 2026-11-14T01:33:34Z · 1a2b3c4
```

Client commits never change the record; only an install or upgrade writes it. The named release label stays internal (`metadata/distribution.json`, `VERSION`, the binding and `release`) for compatibility checks and deliberate releases; status views never display it.
