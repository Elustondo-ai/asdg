"""Derive, verify and read the commit-based ASDG build identity."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from cli_files import Conflict, read_bytes
from cli_model import json_bytes, sha

BUILD = 'metadata/build.json'
SHORT = 7
ATTRIBUTION = 'PACKAGE_MATCHES_COMMIT'
FIELDS = {'schema_version', 'build_id', 'commit', 'commit_short', 'committed_at', 'release',
          'snapshot_sha256', 'attribution'}


def _git(repo: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def snapshot_sha256(entries: dict) -> str:
    """Same digest as the installer's package snapshot: path → SHA-256 in package order."""
    return sha(json_bytes({name: sha(data) for name, data in entries.items()}))


def commit_mismatch(repo: Path, commit: str, entries: dict, prefix: str = '') -> str | None:
    """Return the first selected path whose bytes or mode differ from the commit, else None."""
    listing = _git(repo, 'ls-tree', '-rz', commit, '--', prefix or '.')
    if listing is None:
        return '(commit tree unavailable)'
    tree = {}
    for row in listing.split(b'\0'):
        if row:
            attributes, name = row.split(b'\t', 1)
            mode, kind, oid = attributes.decode().split()
            tree[name.decode()] = (mode, kind, oid)
    algorithm = hashlib.sha1 if len(commit) == 40 else hashlib.sha256
    for name, data in entries.items():
        mode, kind, oid = tree.get(prefix + name, ('', '', ''))
        actual = algorithm(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if mode not in ('100644', '100755') or kind != 'blob' or oid != actual:
            return prefix + name
    return None


def commit_build(repo: Path, commit: str, release: str, entries: dict, prefix: str = '') -> dict:
    """Attribute exactly these package bytes to a commit; the identity uses only commit metadata."""
    out = _git(repo, 'show', '-s', '--format=%H %ct', commit + '^{commit}')
    if out is None or len(out.split()) != 2:
        raise Conflict('Cannot read the selected commit for a build identity: ' + commit)
    full, seconds = out.decode().split()
    if full != commit:
        raise Conflict('Build identity requires the full commit ID; got ' + commit)
    mismatch = commit_mismatch(repo, commit, entries, prefix)
    if mismatch:
        raise Conflict('Packaged source does not match commit ' + commit[:SHORT] + ': ' + mismatch)
    moment = datetime.fromtimestamp(int(seconds), timezone.utc)
    return {'schema_version': 1, 'build_id': moment.strftime('%Y%m%dT%H%M%SZ') + '-' + full[:SHORT],
            'commit': full, 'commit_short': full[:SHORT], 'committed_at': moment.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'release': release, 'snapshot_sha256': snapshot_sha256(entries), 'attribution': ATTRIBUTION}


def commit_package(repo: Path, commit: str, prefix: str = '') -> dict | None:
    """Read the selected package exactly as a commit recorded it, or None when unavailable."""
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit or ''):
        return None
    listing = _git(repo, 'show', f'{commit}:{prefix}metadata/package-files.json')
    try:
        names = sorted(json.loads(listing)['files']) if listing is not None else None
    except (ValueError, KeyError, TypeError):
        return None
    if not names or not all(isinstance(n, str) and '\n' not in n for n in names):
        return None
    request = ''.join(f'{commit}:{prefix}{name}\n' for name in names).encode()
    try:
        result = subprocess.run(['git', '-C', str(repo), 'cat-file', '--batch'], input=request,
                                capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output, position, entries = result.stdout, 0, {}
    for name in names:
        end = output.find(b'\n', position)
        header = output[position:end].split()
        if result.returncode or len(header) != 3 or header[1] != b'blob':
            return None
        size = int(header[2])
        entries[name] = output[end + 1:end + 1 + size]
        position = end + 2 + size
    return entries


def record_bytes(record: dict) -> bytes:
    return (json.dumps(record, indent=2, sort_keys=True) + '\n').encode('utf-8')


def validate(record) -> dict:
    """Reject malformed or internally inconsistent records instead of displaying them."""
    ok = (isinstance(record, dict) and set(record) == FIELDS and record['schema_version'] == 1
          and isinstance(record['commit'], str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', record['commit'])
          and record['commit_short'] == record['commit'][:SHORT]
          and isinstance(record['committed_at'], str)
          and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', record['committed_at'])
          and record['build_id'] == re.sub(r'[-:]', '', record['committed_at']) + '-' + record['commit_short']
          and isinstance(record['release'], str) and record['attribution'] == ATTRIBUTION
          and isinstance(record['snapshot_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', record['snapshot_sha256']))
    if not ok:
        raise Conflict('Invalid ASDG build record: ' + BUILD)
    return record


def read_record(core: Path) -> dict | None:
    raw = read_bytes(core / BUILD)
    if raw is None:
        return None
    try:
        return validate(json.loads(raw))
    except ValueError as exc:
        raise Conflict('Invalid ASDG build record: ' + BUILD) from exc


def package_build(core: Path, info: dict) -> dict | None:
    """A shipped record counts only when it describes exactly the frozen package bytes."""
    record = read_record(core)
    if record is not None and (record['snapshot_sha256'] != info['snapshot_sha256']
                               or record['release'] != info['version']):
        raise Conflict('Package build record does not match its files; obtain a matching package.')
    return record


def label(record: dict) -> str:
    return f"ASDG build {record['committed_at']} · {record['commit_short']}"


def installed_build(core: Path, entries: dict, release: str, legacy_commit: str | None = None) -> dict:
    """Describe the recorded build of an installed distribution; never consults its Git history."""
    try:
        record = read_record(core)
    except Conflict as exc:
        return {'state': 'INVALID', 'display': 'ASDG build record invalid', 'release': release, 'problem': str(exc)}
    if record is None:
        return {'state': 'NOT_RECORDED', 'release': release, 'commit': legacy_commit,
                'display': 'ASDG build not recorded' + (f' · {legacy_commit[:SHORT]}' if legacy_commit else '')}
    matches = record['snapshot_sha256'] == snapshot_sha256(entries)
    return dict(record, state='RECORDED' if matches else 'LOCAL_CHANGES',
                display=label(record) + ('' if matches else ' (local methodology changes)'))
