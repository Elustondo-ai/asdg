"""Explicit, recoverable synchronization of a worktree planning cache with GitHub."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from cli_files import Conflict, safe_path
from cli_plan_merge import empty_cache, reconcile, validate_cache

CACHE = 'docs/asdg/07-planning/project-plan-cache.json'
JOURNAL = '.asdg/cache/project-plan-sync/journal.json'
LOCK = '.asdg/cache/project-plan-sync/lock'
FIELD_NAMES = {'status': 'Status', 'priority': 'ASDG Priority',
               'team': 'ASDG Team', 'sprint': 'ASDG Sprint'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Conflict('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as exc:
        raise Conflict('Invalid planning JSON: ' + str(exc)) from exc


def read(root, name):
    path = safe_path(root, name)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_nlink != 1:
        raise Conflict('Planning stores must be single-link regular files: ' + name)
    return path.read_bytes()


def write(root, name, value):
    path = safe_path(root, name)
    read(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.plan-sync-', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git(root, *arguments, optional=False):
    result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True,
                            text=True, timeout=20)
    if result.returncode:
        if optional:
            return None
        raise Conflict('Git planning preflight failed: ' + ' '.join(arguments[:2]))
    return result.stdout.strip()


def binding(root, repository=None):
    top = git(root, 'rev-parse', '--show-toplevel')
    if Path(top).resolve() != root:
        raise Conflict('Run Project Plan Sync from the Git worktree root.')
    origin = git(root, 'remote', 'get-url', 'origin', optional=True)
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?', origin or '')
    inferred = match.group(1) if match else None
    selected = repository or inferred
    if not selected or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', selected):
        raise Conflict('Supply --repo OWNER/REPOSITORY or a github.com origin.')
    if origin and (not inferred or inferred.casefold() != selected.casefold()):
        raise Conflict('--repo must match this worktree\'s github.com origin.')
    return {'root': str(root), 'repository': selected, 'origin': origin,
            'head': git(root, 'rev-parse', 'HEAD'),
            'branch': git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', optional=True)}


def load_cache(root, bound, project_number=None, bootstrap_ref=None):
    raw = read(root, CACHE)
    source = None
    if raw is not None and bootstrap_ref:
        raise Conflict('--bootstrap-ref is only for an absent local cache; it never resets one.')
    if raw is None and bootstrap_ref:
        commit = git(root, 'rev-parse', '--verify', '--end-of-options', bootstrap_ref + '^{commit}')
        value = git(root, 'show', commit + ':' + CACHE)
        cache = validate_cache(decode(value))
        source = {'ref': bootstrap_ref, 'commit': commit}
    elif raw is None:
        cache = empty_cache(bound['repository'])
    else:
        cache = validate_cache(decode(raw))
    if cache['repository'].casefold() != bound['repository'].casefold():
        raise Conflict('Planning cache belongs to a different repository.')
    if project_number is not None:
        if project_number < 1 or isinstance(project_number, bool):
            raise Conflict('Project number must be positive.')
        if cache['project']['number'] not in (None, project_number):
            raise Conflict('Project number differs from the existing cache binding.')
        cache['project']['number'] = project_number
    return cache, raw, source


@contextmanager
def locked(root):
    try:
        import fcntl
    except ImportError as exc:
        raise Conflict('Project Plan Sync currently requires POSIX file locking (macOS/Linux).') from exc
    path = safe_path(root, LOCK)
    read(root, LOCK)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Conflict('Another Project Plan Sync is running in this worktree.') from exc
        yield
    finally:
        os.close(descriptor)


def _snapshot(api, cache):
    return api.snapshot(cache['repository'], cache['project'])


def _plan(api, cache, snapshot):
    result = reconcile(cache, snapshot)
    operations = []
    if not snapshot['project']:
        operations.append({'kind': 'create_project', 'target': copy.deepcopy(cache['project'])})
    operations.extend({'kind': 'create_field', 'name': name}
                      for name in sorted(snapshot.get('missing_fields', [])))
    for operation in result['operations']:
        if operation['kind'] == 'update_fields':
            operations.extend(dict(operation, fields={key: value})
                              for key, value in sorted(operation['fields'].items()))
        else:
            operations.append(operation)
    for item in result['cache']['items']:
        api.validate_fields(snapshot, {key: item['fields'][key] for key in FIELD_NAMES})
    return dict(result, operations=operations)


def _issue(snapshot, operation):
    matches = [issue for issue in snapshot['issues']
               if issue['id'] == operation.get('id') or
               (operation.get('issue_number') is not None and
                issue['issue_number'] == operation['issue_number'])]
    if len(matches) != 1:
        raise Conflict('Cannot uniquely resolve issue for ' + str(operation.get('id')))
    return matches[0]


def _satisfied(operation, before, after):
    kind = operation['kind']
    if kind == 'create_project':
        return after['project'] is not None
    if kind == 'create_field':
        return operation['name'] not in after.get('missing_fields', [])
    if kind == 'create_issue':
        found = [issue for issue in after['issues'] if issue['id'] == operation['id']]
        return len(found) == 1 and all(found[0]['fields'][key] == value
                                      for key, value in operation['fields'].items()
                                      if key in ('title', 'body', 'state'))
    issue = _issue(after, operation)
    if kind == 'add_item':
        return bool(issue['item_id'])
    return all(issue['fields'][key] == value for key, value in operation['fields'].items())


def _execute(api, cache, snapshot, operation):
    kind = operation['kind']
    repo = cache['repository']
    if kind == 'create_project':
        return api.create_project(repo, cache['project'])
    project = snapshot['project']
    if kind == 'create_field':
        return api.create_field(project['id'], operation['name'])
    if kind == 'create_issue':
        item = next(item for item in cache['items'] if item['id'] == operation['id'])
        return api.create_issue(repo, item)
    issue = _issue(snapshot, operation)
    if kind == 'update_issue':
        return api.update_issue(repo, issue['issue_number'], operation['fields'])
    if kind == 'add_item':
        return api.add_item(project['id'], issue['node_id'])
    if kind == 'update_fields':
        return api.update_fields(project['id'], issue['item_id'], operation['fields'])
    raise Conflict('Unsupported sync operation: ' + kind)


def _record_creation(journal, operation, snapshot):
    """Retain desired fields, but bind a verified new issue to its actual provisional base."""
    if operation['kind'] != 'create_issue':
        return
    observed = _issue(snapshot, operation)
    item = next(item for item in journal['cache']['items'] if item['id'] == operation['id'])
    item['issue_number'] = observed['issue_number']
    item['base'] = copy.deepcopy(observed['fields'])


def _journal(root):
    raw = read(root, JOURNAL)
    if raw is None:
        return None
    result = decode(raw)
    if not isinstance(result, dict) or result.get('schema_version') != 1 or result.get('state') not in ('running', 'complete', 'abandoned'):
        raise Conflict('Invalid Project Plan Sync journal; retain it for reconciliation.')
    return result


def _operation_keys(operation):
    prefix = [operation['kind'], operation.get('id'), operation.get('name')]
    if operation['kind'] in ('update_issue', 'update_fields'):
        return [digest(prefix + [key, value]) for key, value in sorted(operation['fields'].items())]
    if operation['kind'] == 'add_item':
        return [digest(prefix)]  # New issues acquire a server number only after creation.
    return [digest(operation)]


def _allowed_operations(plan, cache):
    keys = set()
    for operation in plan['operations']:
        keys.update(_operation_keys(operation))
        if operation['kind'] == 'create_issue':
            item = next(item for item in cache['items'] if item['id'] == operation['id'])
            # Creating OPEN is an API intermediate; the reviewed desired state remains bounded.
            for kind, names in (('update_issue', ('title', 'body', 'state')), ('update_fields', tuple(FIELD_NAMES))):
                keys.update(_operation_keys({'kind': kind, 'id': item['id'],
                                             'fields': {key: item['fields'][key] for key in names}}))
    return sorted(keys)


def _adopt_verified(cache, snapshot):
    """Called only after conflict-free preview verification; never guess identities by title."""
    result = copy.deepcopy(cache)
    for item in result['items']:
        if item['base'] is None:
            matches = [issue for issue in snapshot['issues'] if issue['id'] == item['id']]
            if len(matches) == 1:
                item['issue_number'] = matches[0]['issue_number']
                item['base'] = copy.deepcopy(matches[0]['fields'])
    return validate_cache(result)


def synchronize(root, *, repository=None, project_number=None, bootstrap_ref=None,
                apply=False, expected_plan=None, resume=False, abandon=False,
                acknowledge_uncertain=False, api=None):
    """Preview never writes. Apply pins current local/remote bytes; resume never repeats uncertain writes."""
    root = Path(root).resolve()
    bound = binding(root, repository)
    if acknowledge_uncertain and not abandon:
        raise Conflict('--acknowledge-uncertain is only valid with explicit --abandon.')
    if api is None:
        from cli_plan_github import GitHub
        api = GitHub()
    if abandon:
        if apply or resume or bootstrap_ref or project_number is not None:
            raise Conflict('--abandon uses the recorded scope and --plan only.')
        with locked(root):
            journal = _journal(root)
            if not journal or journal['state'] != 'running' or expected_plan != journal['plan']:
                raise Conflict('Abandon requires an unfinished sync and its exact original --plan digest.')
            if journal['binding'] != bound:
                raise Conflict('Return to the original worktree and revision before abandoning this sync.')
            if journal['pending'] and not _satisfied(journal['pending'], journal['snapshot'], _snapshot(api, journal['cache'])):
                if not acknowledge_uncertain:
                    raise Conflict('Cannot abandon an unobserved write without an explicit human decision: inspect GitHub, then use --acknowledge-uncertain only if accepting that a later retry may duplicate an unseen creation.')
                journal['uncertain_outcome_acknowledged'] = True
            archive = '.asdg/cache/project-plan-sync/history/' + uuid.uuid4().hex + '.json'
            write(root, archive, journal)
            journal['state'] = 'abandoned'
            journal['archive'] = archive
            write(root, JOURNAL, journal)
            return {'status': 'abandoned', 'archive': archive, 'operations': [], 'conflicts': [],
                    'note': 'Local edits and partial GitHub results preserved; reconcile and preview a new plan.'}
    if resume:
        if apply or expected_plan or bootstrap_ref or project_number is not None:
            raise Conflict('--resume uses the recorded scope; do not combine apply/plan/bootstrap/project options.')
        with locked(root):
            journal = _journal(root)
            if not journal or journal['state'] != 'running':
                raise Conflict('No unfinished Project Plan Sync to resume.')
            if journal['binding'] != bound:
                raise Conflict('Worktree, branch or revision changed since interrupted sync.')
            if digest(read(root, CACHE).decode('utf-8') if read(root, CACHE) is not None else None) != journal['cache_digest']:
                # A crash after atomic publication needs only journal completion.
                if journal.get('published_cache') == decode(read(root, CACHE) or b'null'):
                    if _snapshot(api, journal['cache']) != journal['snapshot']:
                        raise Conflict('GitHub changed after cache publication; abandon and preview reconciliation.')
                    journal['state'] = 'complete'
                    write(root, JOURNAL, journal)
                    return {'status': 'complete', 'resumed': True, 'operations': [], 'conflicts': []}
                raise Conflict('Local cache changed during interrupted sync; preserve and reconcile it first.')
            return _apply(root, api, journal)
    cache, raw, source = load_cache(root, bound, project_number, bootstrap_ref)
    old = _journal(root)
    if old and old['state'] == 'running':
        raise Conflict('Unfinished Project Plan Sync; use --resume before a new sync.')
    snapshot = _snapshot(api, cache)
    plan = _plan(api, cache, snapshot)
    token = digest({'binding': bound, 'cache': cache, 'cache_bytes': raw.decode('utf-8') if raw else None,
                    'bootstrap': source, 'snapshot': snapshot, 'operations': plan['operations']})
    report = {'status': 'conflict' if plan['conflicts'] else 'preview', 'plan': token,
              'repository': cache['repository'], 'project': snapshot['project'],
              'project_target': cache['project'],
              'operations': plan['operations'], 'conflicts': plan['conflicts'],
              'imports': plan['imports'], 'cache_path': CACHE, 'bootstrap': source,
              'cache_preview': plan['cache'],
              'cache_will_change': raw is None or decode(raw) != plan['cache']}
    if not apply:
        return report
    if not expected_plan or expected_plan != token:
        raise Conflict('Stale or missing sync plan; run --dry-run and review the current changes.')
    if plan['conflicts']:
        raise Conflict('Resolve the reported field conflicts before applying synchronization.')
    with locked(root):
        current = _journal(root)
        if current and current['state'] == 'running':
            raise Conflict('Another unfinished sync requires --resume.')
        if read(root, CACHE) != raw or binding(root, repository) != bound or _snapshot(api, cache) != snapshot:
            raise Conflict('Local or GitHub state changed after preview; generate a new plan.')
        if not plan['operations'] and not report['cache_will_change']:
            return dict(report, status='unchanged')
        journal = {'schema_version': 1, 'state': 'running', 'binding': bound, 'plan': token,
                   'cache': _adopt_verified(cache, snapshot), 'original_cache': raw.decode('utf-8') if raw is not None else None,
                   'cache_digest': digest(raw.decode('utf-8') if raw is not None else None),
                   'snapshot': snapshot, 'pending': None, 'completed': [],
                   'allowed_operations': _allowed_operations(plan, cache)}
        write(root, JOURNAL, journal)
        return _apply(root, api, journal)


def _apply(root, api, journal):
    cache = validate_cache(journal['cache'])
    snapshot = _snapshot(api, cache)
    if journal['pending']:
        if not _satisfied(journal['pending'], journal['snapshot'], snapshot):
            raise Conflict('Uncertain GitHub write; its result is not visible. Inspect GitHub and retry --resume; no write was repeated.')
        _record_creation(journal, journal['pending'], snapshot)
        cache = validate_cache(journal['cache'])
        journal['completed'].append(journal['pending'])
        journal['pending'] = None
        journal['snapshot'] = snapshot
        write(root, JOURNAL, journal)
    elif snapshot != journal['snapshot']:
        # Reconciliation below permits independent remote changes after interruption.
        journal['snapshot'] = snapshot
    for _ in range(10000):
        plan = _plan(api, cache, snapshot)
        if plan['conflicts']:
            raise Conflict('GitHub changed during sync; unresolved conflicts remain in the journal. Restore/reconcile the recorded scope before --resume.')
        if not plan['operations']:
            final = validate_cache(plan['cache'])
            if _snapshot(api, cache) != snapshot:
                raise Conflict('GitHub changed before final verification; use --resume.')
            current = read(root, CACHE)
            if digest(current.decode('utf-8') if current is not None else None) != journal['cache_digest']:
                raise Conflict('Local cache was edited during sync; no cache changes were overwritten.')
            if binding(root, cache['repository']) != journal['binding']:
                raise Conflict('Branch or revision changed before cache publication; no cache changes were written.')
            journal['published_cache'] = final
            write(root, JOURNAL, journal)
            write(root, CACHE, final)
            journal['state'] = 'complete'
            write(root, JOURNAL, journal)
            return {'status': 'complete', 'plan': journal['plan'], 'repository': cache['repository'],
                    'project': snapshot['project'], 'operations': journal['completed'],
                    'conflicts': [], 'cache_path': CACHE, 'verified': True}
        operation = plan['operations'][0]
        if not set(_operation_keys(operation)).issubset(journal['allowed_operations']):
            raise Conflict('Remote changes require operations outside the reviewed plan; abandon and preview a new sync.')
        if _snapshot(api, cache) != snapshot:
            raise Conflict('GitHub changed before a write; use --resume to reconcile.')
        if binding(root, cache['repository']) != journal['binding']:
            raise Conflict('Branch or revision changed during sync; no further writes were made.')
        current = read(root, CACHE)
        if digest(current.decode('utf-8') if current is not None else None) != journal['cache_digest']:
            raise Conflict('Local cache changed during sync; no further writes were made.')
        journal['pending'] = operation
        journal['snapshot'] = snapshot
        write(root, JOURNAL, journal)
        from cli_plan_github import GitHubRejected
        try:
            _execute(api, cache, snapshot, operation)
        except GitHubRejected:
            journal['pending'] = None
            journal['rejected_operation'] = operation
            write(root, JOURNAL, journal)
            raise
        observed = _snapshot(api, cache)
        if not _satisfied(operation, snapshot, observed):
            raise Conflict('GitHub has not confirmed the write; use --resume after checking its outcome.')
        _record_creation(journal, operation, observed)
        cache = validate_cache(journal['cache'])
        journal['completed'].append(operation)
        journal['pending'] = None
        snapshot = observed
        journal['snapshot'] = snapshot
        write(root, JOURNAL, journal)
    raise Conflict('Sync operation limit reached; retained journal supports --resume.')


def render(result):
    lines = ['Project Plan Sync: ' + result['status'], 'Cache: ' + result.get('cache_path', CACHE)]
    if result.get('plan'):
        lines.append('Plan: ' + result['plan'])
    for operation in result.get('operations', []):
        lines.append(json.dumps(operation, sort_keys=True, ensure_ascii=False))
    for conflict in result.get('conflicts', []):
        lines.append('CONFLICT: ' + json.dumps(conflict, sort_keys=True, ensure_ascii=False))
    return '\n'.join(lines)
