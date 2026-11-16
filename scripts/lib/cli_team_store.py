"""Saved team specifications: read-only listing and preview, and a token-checked apply under one write lock."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # No cooperative lock on this platform, so no writes.
    fcntl = None

from cli_files import Conflict, apply as apply_changes, plan, safe_path
from cli_team_model import SCHEMA_VERSION, name_key, new_team_id, validate_spec

SPECS = Path('.asdg/teams/specs')
BINDING = Path('.asdg/project.json')
RECEIPTS = Path('.asdg/cache/teams/spec-writes')
CLAIM = Path('asdg/teams/active-run.json')
LOCK = Path('asdg/teams/write.lock')
SPEC_FILE = re.compile(r'(team-[0-9a-f]{16})\.json')
LIMIT = 256 * 1024
FORMAT = 'team-spec-preview-1'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def spec_bytes(spec):
    """The saved serialization. Matching it shows format only, never who wrote a file or what it replaced."""
    return (json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')


def _git(root, *arguments):
    try:
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', *arguments],
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _regular(path):
    """Bytes of a bounded regular file that is not a symlink, or the reason it was not read."""
    if path.is_symlink():
        return None, 'SYMLINK'
    if not path.is_file():
        return None, 'NOT_A_FILE'
    if path.stat().st_size > LIMIT:
        return None, 'TOO_LARGE'
    return path.read_bytes(), None


def project(root):
    """Filesystem evidence for where the store lives: resolved root, Git common directory, project binding."""
    root = Path(root)
    if not root.is_absolute():
        raise Conflict('Project root must be an absolute path.')
    root = root.resolve()
    top = _git(root, '--show-toplevel')
    if top is None or Path(top).resolve() != root:
        raise Conflict('Team stores need the root of a Git project; other folders are unsupported.')
    common = _git(root, '--git-common-dir')
    common = (root / common).resolve() if common else None
    if common is None or not common.is_dir():
        raise Conflict('The Git common directory could not be resolved.')
    data, _ = _regular(safe_path(root, BINDING))
    try:
        binding = json.loads(data.decode('utf-8')) if data is not None else None
    except (UnicodeDecodeError, ValueError):
        binding = None
    project_id = binding.get('project_id') if isinstance(binding, dict) else None
    if not isinstance(project_id, str) or not project_id:
        raise Conflict('Project binding .asdg/project.json is missing or unreadable; initialize ASDG first.')
    return {'root': str(root), 'git_common_dir': str(common), 'project_id': project_id, 'binding_sha256': _sha(data)}


def run_state(common):
    """What the claim path shows. Only a valid tombstone with nothing beside it counts as INACTIVE; the rest stays opaque."""
    try:
        path = safe_path(Path(common), CLAIM)
    except Conflict:
        return {'state': 'UNSAFE', 'sha256': None}
    if not path.exists():
        return {'state': 'NONE', 'sha256': None}
    data, _ = _regular(path)
    if data is None:
        return {'state': 'UNREADABLE', 'sha256': None}
    from cli_team_claim import read_claim  # Imported here because the claim module imports this one.
    found = read_claim(common)
    inactive = found['state'] == 'RELEASED' and not found['suspects']
    return {'state': 'INACTIVE' if inactive else 'PRESENT_UNINTERPRETED', 'sha256': _sha(data)}


def _classify(data, team_id, project_id, role_ids, coordinator):
    try:
        spec = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return 'MALFORMED', 'Not UTF-8 JSON.', None
    if not isinstance(spec, dict):
        return 'MALFORMED', 'Not a JSON object.', None
    version = spec.get('schema_version')
    if type(version) is not int or version != SCHEMA_VERSION:
        return 'UNSUPPORTED_VERSION', f'Version {version!r}; this build reads version {SCHEMA_VERSION}.', None
    if spec.get('project_id') != project_id:
        return 'FOREIGN_PROJECT', 'Saved for a different project.', None
    try:
        checked = validate_spec(spec, project_id=project_id, role_ids=role_ids, coordinator=coordinator)
    except Conflict as error:
        return 'INVALID', str(error), None
    if checked['team_id'] != team_id:
        return 'INVALID', 'File name and team ID differ.', None
    if spec_bytes(checked) != data:
        return 'NOT_SAVED_FORM', 'Valid content, but not in the saved serialization.', checked
    return 'VALID', None, checked  # Valid shape and format. Origin and prior content remain unverified.


def scan(root, *, role_ids, coordinator):
    """List the store as found. Every file is reported; none is changed, moved or trusted by its name alone."""
    where = project(root)
    folder = safe_path(Path(where['root']), SPECS)
    if folder.exists() and not folder.is_dir():
        raise Conflict(f'Expected a directory: {folder}')
    teams, problems, strays, entries, named = [], [], [], [], []
    for name in sorted(item.name for item in folder.iterdir()) if folder.is_dir() else []:
        data, reason = _regular(folder / name)
        row = {'file': name, 'sha256': _sha(data) if data is not None else None}
        match = SPEC_FILE.fullmatch(name)
        if reason is None and not match and not name.endswith('.json'):
            state = 'STRAY'
            strays.append(row)
        elif reason or not match:
            state = reason or 'UNKNOWN_FILE'
            problems.append(dict(row, state=state, reason='Not a saved specification this build can read.'))
        else:
            state, detail, spec = _classify(data, match[1], where['project_id'], role_ids, coordinator)
            if spec is not None:
                row.update(team_id=spec['team_id'], name=spec['name'], type=spec['type'], revision=spec['revision'],
                           provenance='UNVERIFIED')
                named.append(row)
            if state == 'VALID':
                teams.append(row)
            else:
                problems.append(dict(row, state=state, reason=detail))
        entries.append({'file': name, 'sha256': row['sha256'], 'state': state})
    groups = {}
    for row in named:
        groups.setdefault(name_key(row['name']), []).append(row['team_id'])
    duplicates = sorted(ids for ids in groups.values() if len(ids) > 1)
    return {'project': where, 'store': SPECS.as_posix(), 'exists': folder.is_dir(), 'teams': teams,
            'problems': problems, 'strays': strays, 'duplicate_names': duplicates, 'entries': entries,
            'named': named, 'clean': not problems and not duplicates}


def unused_team_id(root):
    """A new opaque ID that no file in the store already uses. The caller fixes it before any preview."""
    base = Path(project(root)['root'])
    folders = [folder for folder in (safe_path(base, SPECS), safe_path(base, RECEIPTS)) if folder.is_dir()]
    return new_team_id({item.name.split('.')[0] for folder in folders for item in folder.iterdir()})


def receipt_bytes(where, team_id, revision, digest):
    """Local write evidence for one saved file. Not approval, authority or tamper-proof security."""
    return spec_bytes({'schema_version': 1, 'kind': 'asdg-team-spec-write', 'project_id': where['project_id'],
                       'root': where['root'], 'git_common_dir': where['git_common_dir'], 'team_id': team_id,
                       'revision': revision, 'sha256': digest})


def receipt_state(where, team_id, revision=None, digest=None):
    """MATCH only when the receipt is exactly what this writer records for the stored revision and bytes."""
    path = safe_path(Path(where['root']), RECEIPTS / (team_id + '.json'))
    if not path.exists():
        return {'state': 'NONE', 'sha256': None}
    data, _ = _regular(path)
    if data is None:
        return {'state': 'UNREADABLE', 'sha256': None}
    exact = revision is not None and data == receipt_bytes(where, team_id, revision, digest)
    return {'state': 'MATCH' if exact else 'MISMATCH', 'sha256': _sha(data)}


@contextlib.contextmanager
def write_lock(common, wait=10.0):
    """Hold the one cooperative lock for team configuration and claim transitions. The file is reused."""
    if fcntl is None:
        raise Conflict('Team writes need POSIX file locking, which this platform lacks.')
    safe_path(Path(common), LOCK).parent.mkdir(parents=True, exist_ok=True)
    path = safe_path(Path(common), LOCK)
    try:
        handle = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise Conflict(f'Team write lock is unusable: {path}') from error
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise Conflict('Another team write is in progress; try again.')
                time.sleep(0.02)
        yield path
    finally:
        os.close(handle)  # Closing releases the lock; the file stays for reuse.


def _supplied(role_ids, coordinator, context):
    context = {} if context is None else context
    if (not isinstance(context, dict) or len(context) > 20 or any(
            not isinstance(key, str) or not isinstance(value, str) or len(key) > 80 or len(value) > 600
            for key, value in context.items())):
        raise Conflict('Supplied context must be a small mapping of text labels to text values.')
    return {'role_catalogue_sha256': _sha(_canonical([sorted(role_ids), coordinator])),
            'context': dict(sorted(context.items()))}


def preview(root, candidate, *, role_ids, coordinator, context=None):
    """Deterministic preview of saving `candidate`: exact path, bytes and token. Writes nothing."""
    listing = scan(root, role_ids=role_ids, coordinator=coordinator)
    where = listing['project']
    checked = validate_spec(candidate, project_id=where['project_id'], role_ids=role_ids, coordinator=coordinator)
    supplied = _supplied(role_ids, coordinator, context)
    data = spec_bytes(checked)
    if len(data) > LIMIT:  # A larger file could be previewed but never read back.
        raise Conflict(f'Team specification is {len(data)} bytes when saved; the limit is {LIMIT}.')
    file = checked['team_id'] + '.json'
    run = run_state(where['git_common_dir'])
    lock = safe_path(Path(where['git_common_dir']), LOCK)
    if lock.exists() and not lock.is_file():
        raise Conflict(f'Team write lock is not a regular file: {lock}')
    conflicts = []
    if listing['problems']:
        conflicts.append({'code': 'STORE_NEEDS_RECONCILIATION', 'files': [row['file'] for row in listing['problems']]})
    if listing['duplicate_names']:
        conflicts.append({'code': 'DUPLICATE_NAMES', 'team_ids': listing['duplicate_names']})
    key = name_key(checked['name'])
    others = [row['team_id'] for row in listing['named']
              if name_key(row['name']) == key and row['team_id'] != checked['team_id']]
    if others:
        conflicts.append({'code': 'NAME_IN_USE', 'team_ids': others})
    current = next((row for row in listing['teams'] if row['team_id'] == checked['team_id']), None)
    before = next((row['sha256'] for row in listing['entries'] if row['file'] == file), None)
    receipt = receipt_state(where, checked['team_id'], *((current['revision'], current['sha256']) if current else ()))
    if current is None:
        action = 'create'
        if receipt['state'] != 'NONE':  # A receipt without its file is not ours to overwrite.
            conflicts.append({'code': 'RECEIPT_PRESENT', 'receipt': receipt['state']})
        if checked['revision'] != 1:
            conflicts.append({'code': 'REVISION', 'expected': 1})
    elif current['sha256'] == _sha(data):
        action = 'unchanged'
    else:
        action = 'replace'
        if receipt['state'] != 'MATCH':  # Nothing shows this writer saved these bytes; a local agreement could be lost.
            conflicts.append({'code': 'PROVENANCE_UNVERIFIED', 'stored_sha256': current['sha256'],
                              'receipt': receipt['state']})
        if checked['revision'] != current['revision'] + 1:
            conflicts.append({'code': 'STALE_REVISION', 'expected': current['revision'] + 1})
        if run['state'] not in ('NONE', 'INACTIVE'):  # Only no claim or a clean tombstone shows no run is agreed.
            conflicts.append({'code': 'RUN_STATE_UNPROVEN', 'state': run['state']})
    if run['state'] in ('UNSAFE', 'UNREADABLE'):
        conflicts.append({'code': 'RUN_STATE_UNREADABLE', 'state': run['state']})
    path = (SPECS / file).as_posix()
    receipt_path, saved = (RECEIPTS / file).as_posix(), receipt_bytes(where, checked['team_id'], checked['revision'], _sha(data))
    effects = [] if action == 'unchanged' else [
        {'path': path, 'action': action, 'before_sha256': before, 'sha256': _sha(data)},
        {'path': receipt_path, 'action': 'replace' if receipt['sha256'] else 'create',
         'before_sha256': receipt['sha256'], 'sha256': _sha(saved)}]
    helpers = {'lock': str(lock), 'temporary': 'A .asdg-tmp-* file beside a replaced output, removed when the write ends.'}
    evidence = {'project': where, 'store_exists': listing['exists'], 'store': listing['entries'],
                'target': {'path': path, 'before_sha256': before}, 'run': run,
                'receipt': dict(receipt, path=receipt_path)}
    bound = {'format': FORMAT, 'evidence': evidence, 'supplied_unverified': supplied, 'effects': effects, 'helpers': helpers,
             'candidate': {'team_id': checked['team_id'], 'revision': checked['revision'], 'type': checked['type'],
                           'action': action, 'sha256': _sha(data)}}
    outcome = 'CONFLICT' if conflicts else 'UNCHANGED' if action == 'unchanged' else 'READY'
    return {'outcome': outcome, 'action': action, 'path': path, 'bytes': data, 'sha256': _sha(data),
            'token': FORMAT + '.' + _sha(_canonical(bound)) if outcome == 'READY' else None,
            'conflicts': conflicts, 'evidence': evidence, 'supplied_unverified': supplied, 'effects': effects,
            'helpers': helpers, 'receipt_bytes': saved, 'applied': False, 'changed_files': []}


def apply(root, candidate, token, *, role_ids, coordinator, context=None, wait=10.0):
    """Save `candidate` and its receipt only if a fresh preview under the write lock yields exactly `token`."""
    if not isinstance(token, str) or not re.fullmatch(re.escape(FORMAT) + r'\.[0-9a-f]{64}', token):
        raise Conflict('Invalid team preview token.')
    where = project(root)
    with write_lock(where['git_common_dir'], wait):
        fresh = preview(root, candidate, role_ids=role_ids, coordinator=coordinator, context=context)
        if fresh['outcome'] != 'READY' or fresh['token'] != token:
            raise Conflict('Team preview changed; review a fresh preview before applying.')
        base, replacing = Path(where['root']), fresh['action'] == 'replace'
        changes = [plan(base, effect['path'], data, replace=replacing)
                   for effect, data in zip(fresh['effects'], (fresh['bytes'], fresh['receipt_bytes']))]
        for effect, change in zip(fresh['effects'], changes):  # The bytes about to be replaced are the previewed ones.
            found = _sha(change.before) if change is not None and change.before is not None else None
            if change is None or found != effect['before_sha256']:
                raise Conflict('Team store changed during apply; review a fresh preview.')
        team_id = json.loads(fresh['bytes'])['team_id']

        def verify():
            rows = scan(root, role_ids=role_ids, coordinator=coordinator)['teams']
            row = next((item for item in rows if item['team_id'] == team_id), None)
            if (row is None or row['sha256'] != fresh['sha256']
                    or receipt_state(where, team_id, row['revision'], row['sha256'])['state'] != 'MATCH'):
                raise Conflict('Saved team specification did not read back as written.')

        changed = apply_changes(changes, verify=verify)
    return {'outcome': 'APPLIED', 'action': fresh['action'], 'path': fresh['path'], 'sha256': fresh['sha256'],
            'receipt': fresh['effects'][1]['path'], 'lock': fresh['helpers']['lock'], 'applied': True,
            'changed_files': changed}
