"""Freeze a selected portable package; optionally prove its local canonical commit."""
from __future__ import annotations

import json
import re
from pathlib import Path

from build_identity import commit_build, commit_mismatch, package_build
from cli_files import Conflict, read_bytes
from cli_model import distribution_core, git_value, json_bytes, sha
from cli_project import distribution
from cli_sync_manifest import methodology_path, repository_id
from distribution_files import MANIFEST, package_files


def git_root(path: Path, *, exact=True) -> Path:
    path = path.expanduser().resolve(strict=True)
    found = git_value(path, 'rev-parse', '--show-toplevel')
    if not found or (exact and Path(found).resolve() != path):
        raise Conflict('Expected an existing Git project root: ' + str(path))
    return Path(found).resolve(strict=True)


def package(repo: Path, *, local_changes: bool = False) -> tuple[dict, dict]:
    """Manifest equality establishes integrity, not release approval or authenticity.

    `local_changes` is for an initialized client refreshing its own integration files: its
    methodology was edited in place, so a mismatch is reported as LOCAL_CHANGES instead of refused.
    The delivery manifest is never rewritten; it stays as provenance of what was delivered.
    """
    metadata = distribution(repo)
    core = distribution_core(repo)
    entries = {methodology_path(p.relative_to(core).as_posix()): read_bytes(p)
               for p in package_files(core)}
    manifest = json.loads(entries[MANIFEST])
    hashes = {name: sha(data) for name, data in entries.items() if name != MANIFEST}
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != 1
            or manifest.get('version') != metadata['version']):
        raise Conflict('Package integrity failed: delivery manifest is invalid or names another version. '
                       'Obtain a matching package.')
    matched = manifest.get('files') == hashes
    if not matched and not local_changes:
        raise Conflict('Package integrity failed: delivery manifest is stale or invalid; '
                       'working-tree snapshots cannot be installed. Obtain a matching package.')
    info = {'version': metadata['version'], 'manifest_sha256': sha(entries[MANIFEST]),
            'snapshot_sha256': sha(json_bytes({n: sha(b) for n, b in entries.items()})),
            'integrity': 'MANIFEST_MATCHED' if matched else 'LOCAL_CHANGES', 'release_approval': 'NOT_ESTABLISHED',
            'canonical_repository': metadata.get('canonical_repository')}
    return info, entries


def source_snapshot(repo: Path, commit: str | None, *, local_changes: bool = False) -> tuple[dict, dict]:
    info, entries = package(repo, local_changes=local_changes and commit is None)
    info.update(kind='EXTRACTED_PACKAGE', commit=None, path=str(repo))
    if commit is None:
        if not local_changes:
            info['build'] = package_build(distribution_core(repo), info)
            return info, entries
        try:  # Locally changed bytes are never attributed to a build; the stored record is left alone.
            info['build'] = package_build(distribution_core(repo), info) if info['integrity'] == 'MANIFEST_MATCHED' else None
        except Conflict:
            info.update(build=None, integrity='LOCAL_CHANGES')
        return info, entries
    git_root(repo)
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise Conflict('--commit must be an explicit full lowercase commit ID, not a branch or tag.')
    if git_value(repo, 'rev-parse', 'HEAD') != commit:
        raise Conflict('Source HEAD does not match the explicitly selected commit.')
    origin = git_value(repo, 'remote', 'get-url', 'origin')
    if not origin or repository_id(origin) != repository_id(info['canonical_repository'] or ''):
        raise Conflict('Source origin does not identify the canonical methodology repository.')
    prefix = '' if distribution_core(repo) == repo else 'asdg/'
    mismatch = commit_mismatch(repo, commit, entries, prefix)
    if mismatch == '(commit tree unavailable)':
        raise Conflict('Cannot inspect the selected source commit.')
    if mismatch:
        raise Conflict('Selected package file does not match source commit: ' + mismatch)
    info['build'] = commit_build(repo, commit, info['version'], entries, prefix)
    info.update(kind='VERIFIED_LOCAL_CLONE', commit=commit)
    return info, entries
