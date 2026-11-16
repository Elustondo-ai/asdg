"""Local host identity and the one active-run claim per project; no worker is launched or observed here."""
from __future__ import annotations

import copy
import json
import re
import secrets
from pathlib import Path

from cli_files import Conflict, apply as apply_changes, plan, safe_path
from cli_team_model import SHA, TEAM_ID, _text, _utc_stamp
from cli_team_store import CLAIM, LOCK, _canonical, _regular, _sha, project, scan, spec_bytes, write_lock

SCHEMA_VERSION = 1
HOST_KIND, CLAIM_KIND = 'asdg-host-identity', 'asdg-team-run-claim'
HOST_FORMAT, START_FORMAT = 'team-host-preview-1', 'team-start-preview-2'
END_FORMATS = {'RELEASE': 'team-release-preview-1', 'RECOVERY': 'team-recover-preview-1'}
TEMPORARY = 'One .asdg-tmp-* file beside the claim while it is replaced.'
HOST_ID = re.compile(r'host-[0-9a-f]{32}')
RUN_ID = re.compile(r'run-[0-9a-f]{16}')
SESSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{7,199}')
PLACEHOLDERS = {'claude_session_id', 'session_id', 'sessionid', 'undefined', 'unknown_session', 'placeholder',
                'your_session_id', 'not_available'}
SYNC_MARKERS = ('cloudstorage', 'google drive', 'googledrive', 'my drive', 'dropbox', 'onedrive', 'icloud',
                'mobile documents')
HOST_FIELDS = {'schema_version', 'kind', 'host_id', 'created_at'}
CLAIM_FIELDS = {'schema_version', 'kind', 'run_id', 'generation', 'team_id', 'spec_revision', 'spec_sha256',
                'project_id', 'git_common_dir', 'worktree', 'host_id', 'owner_session', 'owner_evidence', 'goal',
                'state', 'started_at'}
END_FIELDS = {'ended_at', 'end_kind', 'ended_by_host', 'ended_by_session', 'ended_by_worktree', 'end_evidence'}
END_KINDS = {'RELEASE': 'OWNER_FIELDS_MATCH_UNCORRELATED', 'RECOVERY': 'HUMAN_DECLARED_UNVERIFIED'}


def default_host_path():
    """The proposed location, outside any project. Nothing here creates it; setup needs its own preview and token."""
    return Path.home() / '.local/state/asdg/host-id.json'


def new_host_id():
    return 'host-' + secrets.token_hex(16)


def new_run_id():
    return 'run-' + secrets.token_hex(8)


def _match(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _location(host_path, root):
    """Refuse host paths that are relative, inside the project, on a known synced folder or behind a symlink."""
    path = Path(host_path)
    if not path.is_absolute() or '..' in path.parts or path.name != 'host-id.json':
        raise Conflict('Host identity path must be an absolute path to a file named host-id.json.')
    if any(marker in str(path).casefold() for marker in SYNC_MARKERS):  # A name check only; it proves nothing.
        raise Conflict('Host identity path looks like a synced folder; choose a local one.')
    where = project(root)
    for boundary in (Path(where['root']), Path(where['git_common_dir'])):
        if boundary == path or boundary in path.parents:
            raise Conflict('Host identity must live outside the project and its Git directory.')
    anchor = path.parent
    while not anchor.exists():
        anchor = anchor.parent
    if anchor.resolve() != anchor or not anchor.is_dir():
        raise Conflict('Host identity path passes through a symbolic link or a file.')
    return path, anchor


def _host_state(path, anchor):
    none = {'state': 'NONE', 'host_id': None, 'sha256': None}
    try:
        target = safe_path(anchor, path.relative_to(anchor))
    except Conflict:
        return dict(none, state='UNSAFE')
    if not target.exists():
        return none
    data, _ = _regular(target)
    if data is None:
        return dict(none, state='UNSAFE')
    try:
        value = json.loads(data.decode('utf-8'))
    except ValueError:
        value = None
    valid = (isinstance(value, dict) and set(value) == HOST_FIELDS and type(value['schema_version']) is int
             and value['schema_version'] == SCHEMA_VERSION and value['kind'] == HOST_KIND
             and _match(HOST_ID, value['host_id']) and _utc_stamp(value['created_at']) and spec_bytes(value) == data)
    return {'state': 'VALID' if valid else 'INVALID', 'host_id': value['host_id'] if valid else None, 'sha256': _sha(data)}


def read_host(host_path, *, root):
    """What the host identity file shows: NONE, VALID, INVALID or UNSAFE. Read-only; never regenerated."""
    return _host_state(*_location(host_path, root))


def host_preview(host_path, *, root, host_id, created_at):
    """Exact preview of creating the host identity. An existing valid one is kept and reported instead."""
    path, anchor = _location(host_path, root)
    if not _match(HOST_ID, host_id) or not _utc_stamp(created_at):
        raise Conflict('Host identity needs a generated host ID and a real UTC time.')
    found = _host_state(path, anchor)
    data = spec_bytes({'schema_version': SCHEMA_VERSION, 'kind': HOST_KIND, 'host_id': host_id, 'created_at': created_at})
    outcome = {'NONE': 'READY', 'VALID': 'UNCHANGED'}.get(found['state'], 'CONFLICT')
    bound = {'format': HOST_FORMAT, 'path': str(path), 'found': found, 'sha256': _sha(data)}
    return {'outcome': outcome, 'path': str(path), 'found': found, 'bytes': data if outcome == 'READY' else None,
            'host_id': host_id if outcome == 'READY' else found['host_id'],
            'token': HOST_FORMAT + '.' + _sha(_canonical(bound)) if outcome == 'READY' else None,
            'applied': False, 'changed_files': []}


def host_setup(host_path, token, *, root, host_id, created_at):
    """Create the previewed identity once. Never replaces, repairs or regenerates an existing file."""
    fresh = host_preview(host_path, root=root, host_id=host_id, created_at=created_at)
    if fresh['outcome'] != 'READY' or fresh['token'] != token:
        raise Conflict('Host identity preview changed; review a fresh preview before applying.')
    path, anchor = _location(host_path, root)

    def verify():
        if _host_state(path, anchor)['host_id'] != host_id:
            raise Conflict('Host identity did not read back as written.')

    try:
        changed = apply_changes([plan(anchor, path.relative_to(anchor), fresh['bytes'], mode=0o600)], verify=verify)
    except FileExistsError as error:
        raise Conflict('Host identity appeared during setup; it was left untouched.') from error
    return {'outcome': 'CREATED', 'path': str(path), 'host_id': host_id, 'applied': True, 'changed_files': changed}


def validate_claim(value):
    """Return a validated deep copy of a version 1 claim: an ACTIVE agreement to run, or its RELEASED tombstone."""
    ended = isinstance(value, dict) and value.get('state') == 'RELEASED'
    fields = CLAIM_FIELDS | END_FIELDS if ended else CLAIM_FIELDS
    if not isinstance(value, dict) or set(value) != fields:
        raise Conflict('Run claim must have exactly these fields: ' + ', '.join(sorted(fields)))
    version = value['schema_version']
    if type(version) is not int or version != SCHEMA_VERSION:
        raise Conflict(f'Unsupported run claim version {version!r}; this build reads version {SCHEMA_VERSION}.')
    checks = {
        'kind': value['kind'] == CLAIM_KIND, 'run_id': _match(RUN_ID, value['run_id']),
        'generation': type(value['generation']) is int and value['generation'] >= 1,
        'team_id': _match(TEAM_ID, value['team_id']),
        'spec_revision': type(value['spec_revision']) is int and value['spec_revision'] >= 1,
        'spec_sha256': _match(SHA, value['spec_sha256']), 'host_id': _match(HOST_ID, value['host_id']),
        'project_id': isinstance(value['project_id'], str) and bool(value['project_id']),
        'git_common_dir': isinstance(value['git_common_dir'], str) and Path(value['git_common_dir']).is_absolute(),
        'worktree': isinstance(value['worktree'], str) and Path(value['worktree']).is_absolute(),
        'owner_session': _session_ok(value['owner_session']), 'owner_evidence': value['owner_evidence'] == 'UNCORRELATED',
        'state': value['state'] in ('ACTIVE', 'RELEASED'), 'started_at': _utc_stamp(value['started_at']),
    }
    if ended:
        checks.update({
            'ended_at': bool(_utc_stamp(value['ended_at']) and checks['started_at']
                             and value['ended_at'] >= value['started_at']),
            'end_kind': value['end_kind'] in END_KINDS, 'end_evidence': value['end_evidence'] == END_KINDS.get(value['end_kind']),
            'ended_by_host': _match(HOST_ID, value['ended_by_host']), 'ended_by_session': _session_ok(value['ended_by_session']),
            'ended_by_worktree': isinstance(value['ended_by_worktree'], str) and Path(value['ended_by_worktree']).is_absolute()})
    bad = sorted(name for name, passed in checks.items() if not passed)
    if bad:
        raise Conflict('Invalid run claim fields: ' + ', '.join(bad))
    if _text(value['goal'], 'Goal') != value['goal']:
        raise Conflict('Goal is not in its saved form.')
    return copy.deepcopy(value)


def _session_ok(value):
    """Present and not a literal: an unexpanded variable or a placeholder word is not an identity."""
    return _match(SESSION, value) and value.casefold().replace('-', '_') not in PLACEHOLDERS and len(set(value)) > 3


def read_claim(common):
    """NONE, CLAIMED, RELEASED (a tombstone), UNREADABLE or UNSAFE, plus unregistered files beside it. Never proof of activity."""
    result = {'state': 'NONE', 'claim': None, 'sha256': None, 'suspects': []}
    try:
        path = safe_path(Path(common), CLAIM)
    except Conflict:
        return dict(result, state='UNSAFE')
    if path.parent.is_dir():
        result['suspects'] = sorted(item.name for item in path.parent.iterdir() if item.name not in (CLAIM.name, LOCK.name))
    if not path.exists():
        return result
    data, _ = _regular(path)
    if data is None:
        return dict(result, state='UNREADABLE')
    try:
        claim = validate_claim(json.loads(data.decode('utf-8')))
        if spec_bytes(claim) != data:
            raise Conflict('Run claim is not in its saved form.')
    except ValueError:  # Includes Conflict and undecodable bytes.
        return dict(result, state='UNREADABLE', sha256=_sha(data))
    return dict(result, state='CLAIMED' if claim['state'] == 'ACTIVE' else 'RELEASED', claim=claim, sha256=_sha(data))


def describe_suspects(common):
    """Each unregistered file beside the claim, for a human to resolve; nothing here removes or adopts one."""
    rows = []
    for name in read_claim(common)['suspects']:
        data, problem = _regular(safe_path(Path(common), CLAIM).parent / name)
        low = name.casefold()
        kind = ('TEMPORARY_LEFTOVER' if low.startswith('.asdg-tmp-') else
                'CONFLICT_COPY' if 'active-run' in low or 'write' in low else 'UNKNOWN')
        row = {'file': name, 'kind': kind, 'problem': problem, 'sha256': _sha(data) if data is not None else None}
        try:
            other = validate_claim(json.loads(data.decode('utf-8')))
            row['claim'] = {key: other[key] for key in ('run_id', 'generation', 'state', 'host_id', 'owner_session')}
        except (ValueError, AttributeError):  # Not a claim, or unreadable.
            row['claim'] = None
        rows.append(row)
    return rows


def start_preview(root, team_id, *, goal, owner_session, run_id, started_at, host_path, role_ids, coordinator):
    """Bounded preview of claiming one run for a saved team. Writes nothing and launches nothing."""
    listing = scan(root, role_ids=role_ids, coordinator=coordinator)
    where = listing['project']
    row = next((item for item in listing['teams'] if item['team_id'] == team_id), None)
    if row is None:
        raise Conflict('Start needs a saved, valid team; this ID has none.')
    if not _session_ok(owner_session):
        raise Conflict('Start needs the real owner session ID, not a missing value, placeholder or unexpanded variable.')
    if not _match(RUN_ID, run_id) or not _utc_stamp(started_at):
        raise Conflict('Start needs a generated run ID and a real UTC time.')
    if not isinstance(goal, str) or _text(goal, 'Goal') != goal:
        raise Conflict('Goal must be one line of text in its saved form.')
    host = read_host(host_path, root=root)
    common = Path(where['git_common_dir'])
    lock = safe_path(common, LOCK)
    if lock.exists() and not lock.is_file():
        raise Conflict(f'Team write lock is not a regular file: {lock}')
    current = read_claim(common)
    conflicts = []
    if host['state'] != 'VALID':
        conflicts.append({'code': 'HOST_IDENTITY_' + host['state']})
    if current['state'] == 'CLAIMED':
        active = current['claim']
        conflicts.append({'code': 'CLAIM_EXISTS', **{key: active[key] for key in (
            'run_id', 'generation', 'team_id', 'host_id', 'owner_session', 'worktree', 'started_at')}})
    elif current['state'] not in ('NONE', 'RELEASED'):
        conflicts.append({'code': 'CLAIM_' + current['state']})
    last = current['claim'] if current['state'] == 'RELEASED' else None
    if last and last['run_id'] == run_id:  # A finished run never restarts under its own ID.
        conflicts.append({'code': 'RUN_ID_REUSED', 'run_id': run_id, 'generation': last['generation']})
    generation = last['generation'] + 1 if last else 1
    if current['suspects']:  # A conflict copy or leftover may be another run's claim.
        conflicts.append({'code': 'CLAIM_FOLDER_SUSPECT', 'files': current['suspects']})
    claim = validate_claim({
        'schema_version': SCHEMA_VERSION, 'kind': CLAIM_KIND, 'run_id': run_id, 'generation': generation, 'team_id': team_id,
        'spec_revision': row['revision'], 'spec_sha256': row['sha256'], 'project_id': where['project_id'],
        'git_common_dir': where['git_common_dir'], 'worktree': where['root'], 'host_id': host['host_id'] or 'host-' + '0' * 32,
        'owner_session': owner_session, 'owner_evidence': 'UNCORRELATED', 'goal': goal, 'state': 'ACTIVE',
        'started_at': started_at})
    data = spec_bytes(claim)
    evidence = {'project': where, 'team': {'file': row['file'], 'sha256': row['sha256'], 'revision': row['revision']},
                'host': dict(host, path=str(host_path)),
                'claim': dict({key: current[key] for key in ('state', 'sha256', 'suspects')},
                              generation=last['generation'] if last else 0)}  # The epoch every approval is bound to.
    supplied = {'owner_session': owner_session, 'owner_evidence': 'UNCORRELATED',
                'role_catalogue_sha256': _sha(_canonical([sorted(role_ids), coordinator]))}
    helpers = {'lock': str(lock), 'temporary': TEMPORARY if last else 'None for a new claim file.'}
    bound = {'format': START_FORMAT, 'evidence': evidence, 'supplied_unverified': supplied, 'helpers': helpers,
             'effect': {'path': str(common / CLAIM), 'action': 'replace' if last else 'create',
                        'before_sha256': current['sha256'], 'sha256': _sha(data)}}
    ready = not conflicts
    return {'outcome': 'READY' if ready else 'CONFLICT', 'path': str(common / CLAIM), 'claim': claim if ready else None,
            'bytes': data if ready else None, 'sha256': _sha(data) if ready else None,
            'token': START_FORMAT + '.' + _sha(_canonical(bound)) if ready else None, 'conflicts': conflicts,
            'evidence': evidence, 'supplied_unverified': supplied, 'helpers': helpers, 'runtime': 'NOT_OBSERVED',
            'applied': False, 'changed_files': []}


def acquire(root, team_id, token, *, wait=10.0, **start):
    """Write the claim only if a fresh start preview under the shared write lock yields exactly `token`."""
    if not isinstance(token, str) or not re.fullmatch(re.escape(START_FORMAT) + r'\.[0-9a-f]{64}', token):
        raise Conflict('Invalid start preview token.')
    common = Path(project(root)['git_common_dir'])
    with write_lock(common, wait):
        fresh = start_preview(root, team_id, **start)
        active = next((item for item in fresh['conflicts'] if item['code'] == 'CLAIM_EXISTS'), None)
        if active:
            raise Conflict(f"A team run is already claimed: run {active['run_id']}, team {active['team_id']}, "
                           f"generation {active['generation']}. The claim does not show whether workers are running.")
        if fresh['outcome'] != 'READY' or fresh['token'] != token:
            raise Conflict('Start preview changed; review a fresh preview before starting.')

        def verify():
            found = read_claim(common)
            if found['state'] != 'CLAIMED' or found['sha256'] != fresh['sha256'] or found['suspects']:
                raise Conflict('Run claim did not read back as written.')

        replace = fresh['evidence']['claim']['state'] == 'RELEASED'
        changed = apply_changes([plan(common, CLAIM, fresh['bytes'], replace=replace, mode=0o600)], verify=verify)
    return {'outcome': 'ACQUIRED', 'path': fresh['path'], 'run_id': fresh['claim']['run_id'],
            'generation': fresh['claim']['generation'], 'claim': fresh['claim'], 'runtime': 'NOT_OBSERVED',
            'applied': True, 'changed_files': changed}


def _standing(claim, host, where, session):
    """How the caller's supplied fields compare with the claim. Field equality only; it proves no identity."""
    if host['state'] != 'VALID':
        return 'HOST_UNKNOWN'
    if claim['host_id'] != host['host_id']:
        return 'FOREIGN_HOST'
    if (claim['project_id'], claim['git_common_dir']) != (where['project_id'], where['git_common_dir']):
        return 'FOREIGN_PROJECT'
    if claim['owner_session'] != session:
        return 'OTHER_SESSION'
    return 'OWNER_FIELDS_MATCH' if claim['worktree'] == where['root'] else 'OTHER_WORKTREE'


def _end_preview(kind, root, *, run_id, generation, session, ended_at, host_path, confirmation=None):
    where = project(root)
    common = Path(where['git_common_dir'])
    if not _session_ok(session):
        raise Conflict('Ending a run needs the real session ID, not a missing value, placeholder or unexpanded variable.')
    if not _match(RUN_ID, run_id) or type(generation) is not int or generation < 1 or not _utc_stamp(ended_at):
        raise Conflict('Ending a run needs its run ID, its generation and a real UTC time.')
    host = read_host(host_path, root=root)
    lock = safe_path(common, LOCK)
    if lock.exists() and not lock.is_file():
        raise Conflict(f'Team write lock is not a regular file: {lock}')
    current = read_claim(common)
    claim, conflicts, standing, expected, tombstone = current['claim'], [], None, None, None
    if host['state'] != 'VALID':
        conflicts.append({'code': 'HOST_IDENTITY_' + host['state']})
    if current['state'] == 'CLAIMED':
        standing = _standing(claim, host, where, session)
        if (claim['run_id'], claim['generation']) != (run_id, generation):
            conflicts.append({'code': 'STALE_RUN', 'current_run_id': claim['run_id'], 'current_generation': claim['generation']})
        if ended_at < claim['started_at']:
            conflicts.append({'code': 'ENDS_BEFORE_START', 'started_at': claim['started_at']})
        if kind == 'RELEASE' and standing != 'OWNER_FIELDS_MATCH':
            conflicts.append({'code': 'NOT_OWNER', 'standing': standing})
        if kind == 'RECOVERY':
            expected = (f"RECOVER {standing} RUN {claim['run_id']} GENERATION {claim['generation']} "
                        f"HOST {claim['host_id']}")
            if standing == 'OWNER_FIELDS_MATCH':
                conflicts.append({'code': 'OWNER_USES_RELEASE'})
            elif confirmation != expected:  # The preview states the phrase; only a human may supply it back.
                conflicts.append({'code': 'CONFIRMATION_REQUIRED', 'expected': expected, 'standing': standing})
    elif current['state'] == 'RELEASED':
        conflicts.append({'code': 'NOT_ACTIVE', **{key: claim[key] for key in ('run_id', 'generation', 'end_kind', 'ended_at')}})
    else:
        conflicts.append({'code': 'NO_CLAIM' if current['state'] == 'NONE' else 'CLAIM_' + current['state']})
    if current['suspects']:  # Never chosen between here: a conflict copy may be the other side's true claim.
        conflicts.append({'code': 'CLAIM_FOLDER_SUSPECT', 'files': describe_suspects(common)})
    evidence = {'project': where, 'host': dict(host, path=str(host_path)), 'standing': standing,
                'claim': {key: current[key] for key in ('state', 'sha256', 'suspects')}}
    supplied = {'session': session, 'confirmation': confirmation if kind == 'RECOVERY' else None,
                'basis': END_KINDS[kind]}
    helpers = {'lock': str(lock), 'temporary': TEMPORARY}
    ready = not conflicts
    data = None
    if ready:
        tombstone = validate_claim(dict(claim, state='RELEASED', ended_at=ended_at, end_kind=kind,
                                        ended_by_host=host['host_id'], ended_by_session=session,
                                        ended_by_worktree=where['root'], end_evidence=END_KINDS[kind]))
        data = spec_bytes(tombstone)
    bound = {'format': END_FORMATS[kind], 'evidence': evidence, 'supplied_unverified': supplied, 'helpers': helpers,
             'effect': {'path': str(common / CLAIM), 'action': 'replace', 'before_sha256': current['sha256'],
                        'sha256': _sha(data) if ready else None}}
    return {'outcome': 'READY' if ready else 'CONFLICT', 'kind': kind, 'path': str(common / CLAIM), 'tombstone': tombstone,
            'bytes': data, 'sha256': _sha(data) if ready else None, 'standing': standing,
            'confirmation_expected': expected, 'token': END_FORMATS[kind] + '.' + _sha(_canonical(bound)) if ready else None,
            'conflicts': conflicts, 'evidence': evidence, 'supplied_unverified': supplied, 'helpers': helpers,
            'runtime': 'NOT_OBSERVED', 'liveness': 'NOT_ENFORCED', 'applied': False, 'changed_files': []}


def _end(kind, root, token, wait, end):
    if not isinstance(token, str) or not re.fullmatch(re.escape(END_FORMATS[kind]) + r'\.[0-9a-f]{64}', token):
        raise Conflict('Invalid preview token for ending a run.')
    common = Path(project(root)['git_common_dir'])
    with write_lock(common, wait):
        fresh = _end_preview(kind, root, **end)
        if fresh['outcome'] != 'READY' or fresh['token'] != token:
            raise Conflict('The run claim or this preview changed; review a fresh preview before ending the run.')

        def verify():
            found = read_claim(common)
            if found['state'] != 'RELEASED' or found['sha256'] != fresh['sha256'] or found['suspects']:
                raise Conflict('Run tombstone did not read back as written.')

        changed = apply_changes([plan(common, CLAIM, fresh['bytes'], replace=True, mode=0o600)], verify=verify)
    done = fresh['tombstone']
    return {'outcome': 'RELEASED' if kind == 'RELEASE' else 'RECOVERED', 'path': fresh['path'], 'run_id': done['run_id'],
            'generation': done['generation'], 'tombstone': done, 'standing': fresh['standing'], 'runtime': 'NOT_OBSERVED',
            'liveness': 'NOT_ENFORCED', 'applied': True, 'changed_files': changed}


def release_preview(root, **end):
    """Preview the owner ending its own run: the claim becomes a tombstone that keeps the generation. Writes nothing."""
    return _end_preview('RELEASE', root, **end)


def release(root, token, *, wait=10.0, **end):
    """Replace the active claim with its tombstone if a fresh preview under the write lock yields exactly `token`."""
    return _end('RELEASE', root, token, wait, end)


def recover_preview(root, **end):
    """Preview ending a run the caller's fields do not own. It states the phrase a human must give back; stops no worker."""
    return _end_preview('RECOVERY', root, **end)


def recover(root, token, *, wait=10.0, **end):
    """Apply a confirmed recovery. The human's declaration is recorded as unverified; no process is checked or stopped."""
    return _end('RECOVERY', root, token, wait, end)


def check_run(root, run_id, generation):
    """CURRENT only for the exact active run and generation; otherwise STALE, or UNPROVEN when the store is unclear."""
    found = read_claim(Path(project(root)['git_common_dir']))
    if found['state'] in ('UNREADABLE', 'UNSAFE') or found['suspects']:
        return {'outcome': 'UNPROVEN', 'state': found['state'], 'suspects': found['suspects']}
    claim = found['claim']
    current = found['state'] == 'CLAIMED' and (claim['run_id'], claim['generation']) == (run_id, generation)
    return {'outcome': 'CURRENT' if current else 'STALE', 'state': found['state'],
            'generation': claim['generation'] if claim else 0}
