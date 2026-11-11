"""Provider-only scope, starting state and Git patch inspection."""
import json
import os
import re
import stat
import subprocess
import unicodedata
from pathlib import Path

from cli_model import sha
from cli_ownership import local_path
from distribution_files import package_files

ORIGINS = {'https://github.com/Elustondo-ai/asdg.git', 'git@github.com:Elustondo-ai/asdg.git'}


def git(root, *args, data=None, private_index=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env['LC_ALL'] = 'C'  # Git’s mode summary below is a localized display format.
    if private_index is not None:
        env.update(GIT_INDEX_FILE=str(private_index / 'index'),
                   GIT_OBJECT_DIRECTORY=str(private_index / 'objects'),
                   GIT_ALTERNATE_OBJECT_DIRECTORIES=json.dumps(str(root / '.git/objects'), ensure_ascii=False))
    result = subprocess.run(['/usr/bin/git', '--literal-pathspecs', '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.fsmonitor=false', '-C', str(root), *args],
                            env=env, input=data, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip() or 'Git rejected the operation.')
    return result.stdout


def provider(root):
    if (not (root / '.git').is_dir() or (root / '.git').is_symlink()
            or any(os.path.lexists(p / '.asdg') for p in (root, *root.parents))
            or git(root, 'rev-parse', '--show-toplevel').decode().rstrip('\n') != str(root)
            or git(root, 'remote', 'get-url', 'origin').decode().strip() not in ORIGINS):
        raise ValueError('Expected the canonical standalone provider.')


def validate_target(root, component, value):
    path = local_path(root, value)
    if (value != path.as_posix() or len(path.parts) < 3
            or path.parts[:2] != ('components', component)):
        raise ValueError('Target outside the assigned component.')
    for part in path.parts:
        name = unicodedata.normalize('NFKC', part).casefold()
        if (name.startswith('.') or name in {'asdg', 'agents.md', 'skill.md'}
                or name != name.strip() or any(not c.isprintable() for c in name)):
            raise ValueError('Protected target.')
    target = root / path
    for directory in target.parents:
        if directory == root:
            break
        if any(os.path.lexists(directory / marker) for marker in ('.git', '.asdg')):
            raise ValueError('Nested checkout or client boundary.')
    if target.exists() and (not target.is_file() or target.stat().st_nlink != 1):
        raise ValueError('Expected a single regular file.')


def evaluate(root, paths, context, job):
    try:
        provider(root)
        if (context.get('role_id') != 'ASDG-09' or job['role_id'] != 'ASDG-09'
                or job['root'] != str(root) or not paths
                or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', job['component'])
                or not isinstance(job['objective'], str) or not job['objective'].strip()
                or not isinstance(job['acceptance'], list) or not job['acceptance']
                or not all(isinstance(c, str) and c.strip() for c in job['acceptance'])):
            raise ValueError('Expected a bounded ASDG-09 provider assignment.')
        if not isinstance(job['targets'], list) or not job['targets']:
            raise ValueError('Exact assignment targets required.')
        inputs = job.get('inputs', [])
        if not isinstance(inputs, list):
            raise ValueError('Expected exact read-only component inputs.')
        approved = set(job['targets'])
        if not set(paths) <= approved:
            raise ValueError('Assignment does not cover every patch endpoint.')
        portable = {p.relative_to(root).as_posix().casefold() for p in package_files(root)}
        for name in approved.union(inputs):
            validate_target(root, job['component'], name)
            if name.casefold() in portable:
                raise ValueError('Portable distribution target.')
        return True, 'Provider patch scope checked.'
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return False, str(exc)


def starting_state(root, job):
    targets = set(job['targets']).union(job.get('inputs', []))
    files = {}
    for name in sorted(targets):
        path = root / name
        files[name] = {'mode': stat.S_IMODE(path.stat().st_mode),
                       'sha256': sha(path.read_bytes())} if path.exists() else None
    entries = git(root, 'ls-files', '--stage', '-z', '--', *sorted(targets))
    if any(line.split(b'\t', 1)[0].split()[-1] != b'0' for line in entries.split(b'\0') if line):
        raise ValueError('Resolve the assigned files’ index conflicts before preparation.')
    return {'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
            'files': files, 'index_sha256': sha(entries)}


def endpoints(root, patch):
    # Git reports the destination in forward numstat and the source in reverse.
    names = set()
    for direction in ([], ['--reverse']):
        raw = git(root, 'apply', '-p1', '--numstat', '-z', *direction, '-', data=patch)
        for row in raw.split(b'\0'):
            if row:
                names.add(row.split(b'\t', 2)[2].decode('utf-8'))
    if not names:
        raise ValueError('Empty patch.')
    # Only ordinary file modes can enter a component (including mode-only changes).
    summary = git(root, 'apply', '-p1', '--summary', '-', data=patch)
    for line in summary.splitlines():
        modes = re.match(rb' (?:create mode|delete mode|mode change) ([0-7]+)(?: => ([0-7]+))? ', line)
        if modes and any(m and m not in (b'100644', b'100755') for m in modes.groups()):
            raise ValueError('Unsupported patch file mode.')
    return sorted(names)


def token(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
