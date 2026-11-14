#!/usr/bin/env python3
"""Build a verified, reproducible ZIP containing exactly one asdg/ folder."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / 'scripts/lib'))
from distribution_files import MANIFEST, package_files
from build_identity import BUILD, commit_build, label, record_bytes
from check import validate
from cli_files import Conflict


def refresh_manifest(core: Path) -> None:
    """Record current selected bytes, never human approval or a historical rewrite."""
    issues = validate(core)
    if issues:
        raise ValueError('\n'.join(issues))
    metadata = json.loads((core / 'metadata/distribution.json').read_text())
    result = {
        'schema_version': 1, 'version': metadata['version'],
        'purpose': 'Consolidated candidate; exact-state human review remains pending.',
        'human_approval': None,
        'sources': metadata['sources'],
        'files': {p.relative_to(core).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in package_files(core) if p != core / MANIFEST},
    }
    (core / MANIFEST).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


def attribute(core: Path, entries: dict, version: str, commit: str | None = None) -> dict | None:
    """Return a build record only when the selected bytes equal the commit; never invent one."""
    def git(*args):
        result = subprocess.run(['git', '-C', str(core), *args], capture_output=True, text=True, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else None
    top = git('rev-parse', '--show-toplevel')
    if top is None:
        if commit:
            raise ValueError('--commit requires a Git checkout of the canonical source.')
        return None
    relative = core.resolve().relative_to(Path(top).resolve()).as_posix()
    prefix = '' if relative == '.' else relative + '/'
    if commit and not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise ValueError('--commit must be a full lowercase commit ID.')
    selected = commit or git('rev-parse', 'HEAD')
    if not selected:
        return None
    try:
        return commit_build(Path(top), selected, version, entries, prefix)
    except Conflict as exc:
        if commit:
            raise ValueError(str(exc)) from exc
        print('UNATTRIBUTED: ' + str(exc) + '; the ZIP carries no build record.', file=sys.stderr)
        return None


def build(core: Path, output: Path, commit: str | None = None) -> Path:
    """Validate before writing; use stable order, timestamps and permissions."""
    issues = validate(core, integrity=True)
    if issues:
        raise ValueError('\n'.join(issues))
    metadata = json.loads((core / 'metadata/distribution.json').read_text())
    version = metadata['version']
    if not isinstance(version, str) or not re.fullmatch(r'[0-9][a-zA-Z0-9.-]*', version):
        raise ValueError('Unsafe distribution version.')
    # Freeze and recheck the selected bytes before creating an output artifact.
    manifest = json.loads((core / MANIFEST).read_text())
    entries = [(p.relative_to(core).as_posix(), p.read_bytes()) for p in package_files(core)]
    for name, data in entries:
        if name != MANIFEST and hashlib.sha256(data).hexdigest() != manifest['files'].get(name):
            raise ValueError('Package changed during build: ' + name)
    record = attribute(core, dict(entries), version, commit)
    if record:
        # Derived only from commit metadata and bytes, so rebuilding that commit is byte-identical.
        entries = sorted(entries + [(BUILD, record_bytes(record))])
    output.mkdir(parents=True, exist_ok=True)
    target = output / ('asdg-' + version + ('-' + record['build_id'] if record else '') + '.zip')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            entry = zipfile.ZipInfo('asdg/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n')
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=(CORE if (CORE / '.git').exists() else CORE.parent) / 'build/distributions')
    parser.add_argument('--commit', help='full canonical commit ID to attribute; defaults to HEAD when it matches')
    parser.add_argument('--refresh-manifest', action='store_true',
                        help='record reviewed candidate bytes before building; grants no approval')
    args = parser.parse_args()
    try:
        if args.refresh_manifest:
            refresh_manifest(CORE)
        target = build(CORE, args.output, args.commit)
        print(target)
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            print(label(json.loads(archive.read('asdg/' + BUILD))) if 'asdg/' + BUILD in names
                  else 'ASDG build: unattributed (packaged bytes do not match a commit)')
        print('Candidate built locally; native trust, acceptance and publication remain separate.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('BUILD FAILED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
