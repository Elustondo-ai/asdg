"""Pure, field-wise three-way merge for the Project Plan Sync cache."""
from __future__ import annotations

from copy import deepcopy
import re

from cli_files import Conflict


ISSUE_FIELDS = ('title', 'body', 'state')
PROJECT_FIELDS = ('status', 'priority', 'team', 'sprint')
FIELDS = ISSUE_FIELDS + PROJECT_FIELDS
_REPOSITORY = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+\Z')
_OWNER = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*\Z')
_ID = re.compile(r'(?:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}|github:[1-9][0-9]*)\Z')


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Conflict(label + ' must contain exactly: ' + ', '.join(keys) + '.')


def _number(value, label, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not int or value < 1:
        raise Conflict(label + ' must be a positive integer' + (' or null.' if nullable else '.'))


def _string(value, label, nonempty=False):
    if not isinstance(value, str) or '\x00' in value or (nonempty and not value.strip()):
        raise Conflict(label + ' must be ' + ('a nonempty' if nonempty else 'a') + ' string without NUL.')


def _fields(value, label):
    _object(value, FIELDS, label)
    for name in FIELDS:
        _string(value[name], label + '.' + name, nonempty=name == 'title')
    if value['state'] not in ('OPEN', 'CLOSED'):
        raise Conflict(label + '.state must be OPEN or CLOSED.')


def _identity(identifier, number, label):
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise Conflict(label + '.id must be a marker-safe stable ID or github:N.')
    _number(number, label + '.issue_number', nullable=True)
    if identifier.startswith('github:') and identifier != 'github:' + str(number):
        raise Conflict(label + '.id github:N must agree with its bound issue number.')


def validate_cache(cache):
    """Validate the exact portable schema and return an independent copy.

    Notes and source references are deliberately local; they are never projected
    into remote mutation fields. This function performs no I/O or normalization.
    """
    _object(cache, ('schema_version', 'repository', 'project', 'items'), 'Cache')
    if type(cache['schema_version']) is not int or cache['schema_version'] != 1:
        raise Conflict('Unsupported Project Plan Sync cache schema_version.')
    if not isinstance(cache['repository'], str) or not _REPOSITORY.fullmatch(cache['repository']):
        raise Conflict('Cache.repository must be owner/repository on GitHub.')
    project = cache['project']
    _object(project, ('owner', 'number', 'title'), 'Cache.project')
    if not isinstance(project['owner'], str) or not _OWNER.fullmatch(project['owner']):
        raise Conflict('Cache.project.owner must be a GitHub owner login.')
    _number(project['number'], 'Cache.project.number', nullable=True)
    _string(project['title'], 'Cache.project.title', nonempty=True)
    if not isinstance(cache['items'], list):
        raise Conflict('Cache.items must be a list.')
    ids, numbers = set(), set()
    for index, item in enumerate(cache['items']):
        label = 'Cache.items[' + str(index) + ']'
        _object(item, ('id', 'issue_number', 'fields', 'base', 'notes', 'sources'), label)
        _identity(item['id'], item['issue_number'], label)
        if item['id'] in ids:
            raise Conflict('Duplicate cache item ID: ' + item['id'])
        ids.add(item['id'])
        number = item['issue_number']
        if number is not None:
            if number in numbers:
                raise Conflict('Duplicate cache issue number: ' + str(number))
            numbers.add(number)
        _fields(item['fields'], label + '.fields')
        if item['base'] is not None:
            _fields(item['base'], label + '.base')
            if number is None:
                raise Conflict(label + '.base requires a bound issue number.')
        _string(item['notes'], label + '.notes')
        if not isinstance(item['sources'], list):
            raise Conflict(label + '.sources must be a list of strings.')
        for source in item['sources']:
            _string(source, label + '.sources entry', nonempty=True)
    return deepcopy(cache)


def empty_cache(repo, owner=None, title=None, number=None):
    """Build a validated, empty cache; do not infer items from prose or Git."""
    if not isinstance(repo, str):
        raise Conflict('Repository must be owner/repository on GitHub.')
    return validate_cache({
        'schema_version': 1, 'repository': repo,
        'project': {'owner': owner if owner is not None else repo.split('/')[0],
                    'number': number, 'title': title if title is not None else 'ASDG Plan — ' + repo},
        'items': [],
    })


def _snapshot(snapshot, repository):
    if not isinstance(snapshot, dict) or not all(k in snapshot for k in ('repository', 'project', 'issues')):
        raise Conflict('Remote snapshot must contain repository, project and issues.')
    if not isinstance(snapshot['repository'], str) or snapshot['repository'].casefold() != repository.casefold():
        raise Conflict('Remote snapshot repository does not match the local cache.')
    project = snapshot['project']
    if project is not None:
        if not isinstance(project, dict) or not all(k in project for k in ('id', 'number', 'title', 'url', 'owner')):
            raise Conflict('Remote project identity is incomplete.')
        _number(project['number'], 'Remote project number')
        for key in ('id', 'title', 'url', 'owner'):
            _string(project[key], 'Remote project ' + key, nonempty=True)
    if not isinstance(snapshot['issues'], list):
        raise Conflict('Remote snapshot issues must be a list.')
    ids, numbers = set(), set()
    for row in snapshot['issues']:
        if not isinstance(row, dict) or not all(k in row for k in ('id', 'issue_number', 'fields', 'item_id')):
            raise Conflict('Remote issue identity, fields or membership is incomplete.')
        _identity(row['id'], row['issue_number'], 'Remote issue')
        _number(row['issue_number'], 'Remote issue number')
        _fields(row['fields'], 'Remote issue fields')
        if row['item_id'] is not None:
            _string(row['item_id'], 'Remote item_id', nonempty=True)
        if row['id'] in ids or row['issue_number'] in numbers:
            raise Conflict('Remote snapshot has duplicate issue numbers or marker IDs.')
        ids.add(row['id'])
        numbers.add(row['issue_number'])
    return snapshot


def _conflict(identifier, kind, **details):
    return dict({'id': identifier, 'kind': kind}, **details)


def _op(kind, item, fields=None):
    operation = {'kind': kind, 'id': item['id'], 'issue_number': item['issue_number']}
    if fields is not None:
        operation['fields'] = fields
    return operation


def _outbound(item, remote, merged):
    """Describe minimum changed fields; Project membership is non-destructive."""
    result = []
    issue_changes = {key: merged[key] for key in ISSUE_FIELDS if merged[key] != remote['fields'][key]}
    if issue_changes:
        result.append(_op('update_issue', item, issue_changes))
    if remote['item_id'] is None:
        result.append(_op('add_item', item))
    project_changes = {key: merged[key] for key in PROJECT_FIELDS if merged[key] != remote['fields'][key]}
    if project_changes:
        result.append(_op('update_fields', item, project_changes))
    return result


def reconcile(cache, snapshot):
    """Return a candidate cache, operations and explicit conflicts, without I/O.

    The candidate is not a receipt: the caller may publish it only after applying
    mutations and verifying a fresh remote readback. If conflicts are nonempty,
    no part of this result is authorized for automatic application.
    """
    candidate = validate_cache(cache)
    _snapshot(snapshot, candidate['repository'])
    remote_project = snapshot['project']
    conflicts, operations, imports = [], [], []
    project = candidate['project']
    if remote_project is None:
        if project['number'] is not None:
            conflicts.append(_conflict('project', 'missing_bound_project', number=project['number']))
    elif remote_project['owner'].casefold() != project['owner'].casefold() or (
            project['number'] is not None and project['number'] != remote_project['number']):
        conflicts.append(_conflict('project', 'project_identity_changed'))
    else:
        project.update({'number': remote_project['number'], 'title': remote_project['title']})

    by_id = {row['id']: row for row in snapshot['issues']}
    by_number = {row['issue_number']: row for row in snapshot['issues']}
    consumed = set()
    for item in sorted(candidate['items'], key=lambda row: row['id']):
        identifier, number = item['id'], item['issue_number']
        remote = by_number.get(number) if number is not None else by_id.get(identifier)
        if remote is None:
            if number is not None:
                conflicts.append(_conflict(identifier, 'missing_bound_issue', issue_number=number))
                continue
            created_fields = {key: item['fields'][key] for key in ISSUE_FIELDS}
            # GitHub's createIssue mutation always creates an open issue. A
            # requested closed state needs a separate, journalled update after
            # the caller has observed and bound the actual creation.
            created_fields['state'] = 'OPEN'
            operations.append(_op('create_issue', item, created_fields))
            operations.append(_op('add_item', item))
            fields = {key: item['fields'][key] for key in PROJECT_FIELDS if item['fields'][key]}
            if fields:
                operations.append(_op('update_fields', item, fields))
            continue
        consumed.add(remote['issue_number'])
        if identifier != remote['id'] or (identifier in by_id and by_id[identifier] is not remote):
            conflicts.append(_conflict(identifier, 'issue_identity_changed', issue_number=number,
                                       remote_id=remote['id'], remote_number=remote['issue_number']))
            continue
        merged, item_conflicts = {}, []
        for key in FIELDS:
            local, other = item['fields'][key], remote['fields'][key]
            if item['base'] is None:
                if local == other:
                    merged[key] = local
                elif key in PROJECT_FIELDS and remote['item_id'] is None and other == '':
                    # Identical marker-bearing issue after an interrupted create;
                    # absent Project membership has no prior field to overwrite.
                    merged[key] = local
                else:
                    item_conflicts.append(_conflict(identifier, 'unbased_field_conflict', field=key,
                                                    local=local, remote=other))
                continue
            base = item['base'][key]
            if local == other or other == base:
                merged[key] = local
            elif local == base:
                merged[key] = other
            else:
                item_conflicts.append(_conflict(identifier, 'field_conflict', field=key,
                                                base=base, local=local, remote=other))
        if item_conflicts:
            conflicts.extend(item_conflicts)
            continue
        item['issue_number'] = remote['issue_number']
        operations.extend(_outbound(item, remote, merged))
        item['fields'] = merged
        item['base'] = deepcopy(merged)

    for remote in sorted(snapshot['issues'], key=lambda row: row['id']):
        if remote['issue_number'] in consumed:
            continue
        if remote['id'] in {item['id'] for item in candidate['items']}:
            conflicts.append(_conflict(remote['id'], 'issue_identity_changed', remote_number=remote['issue_number']))
            continue
        item = {'id': remote['id'], 'issue_number': remote['issue_number'],
                'fields': deepcopy(remote['fields']), 'base': deepcopy(remote['fields']),
                'notes': '', 'sources': []}
        candidate['items'].append(item)
        imports.append(item['id'])
        if remote['item_id'] is None:
            operations.append(_op('add_item', item))
    candidate['items'].sort(key=lambda row: row['id'])
    return {'cache': candidate, 'operations': operations, 'conflicts': conflicts, 'imports': imports}
