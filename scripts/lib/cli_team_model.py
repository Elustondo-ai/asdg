"""Pure name, ID and specification rules for saved ASDG teams; no filesystem, Git or runtime access."""
from __future__ import annotations

import copy
import re
from datetime import datetime
import secrets
import unicodedata

from cli_files import Conflict

SCHEMA_VERSION = 1
TEAM_TYPES = ('sessions', 'subagents', 'teammates')
WORK_MODES = ('read-only', 'documents')
NAME_MAX, TEXT_MAX, SLOT_MAX = 80, 600, 40
TEAM_ID = re.compile(r'team-[0-9a-f]{16}')
SLOT = re.compile(r'[a-z0-9]+(-[a-z0-9]+)*')
DEFINITION = re.compile(r'\.claude/agents/asdg-[a-z0-9]+(-[a-z0-9]+)*\.md')
SHA = re.compile(r'[0-9a-f]{64}')
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')
FIELDS = {'schema_version', 'team_id', 'revision', 'name', 'project_id', 'type', 'purpose',
          'members', 'lead', 'rules', 'provenance'}
MEMBER = {'slot', 'role_id', 'responsibility'}
RULES = {'collaboration', 'outputs', 'completion', 'handoff', 'integration_owner', 'work'}
PROVENANCE = {'generator', 'asdg_build', 'created_at', 'definitions'}
DEFINITION_FIELDS = {'path', 'role_id', 'sha256', 'template_sha256'}


def _text(value, label, limit=TEXT_MAX):
    """One line of readable text: nonempty, bounded, no control, format or line-separator characters."""
    if not isinstance(value, str):
        raise Conflict(f'{label} must be text.')
    if any(unicodedata.category(ch)[0] == 'C' or unicodedata.category(ch) in ('Zl', 'Zp') for ch in value):
        raise Conflict(f'{label} contains a control or invisible character.')
    cleaned = ' '.join(unicodedata.normalize('NFC', value).split())
    if not cleaned:
        raise Conflict(f'{label} is empty.')
    if len(cleaned) > limit:
        raise Conflict(f'{label} is longer than {limit} characters.')
    return cleaned


def clean_name(raw):
    """Display name: the user's casing and characters, trimmed, with single spaces. Data, never a path."""
    return _text(raw, 'Team name', NAME_MAX)


def name_key(raw):
    """Identity used only to compare names: compatibility-normalized and case-folded."""
    folded = unicodedata.normalize('NFKC', clean_name(raw)).casefold()
    return ' '.join(unicodedata.normalize('NFKC', folded).split())


def new_team_id(existing=()):
    """Opaque random ID. It takes no name, so nothing in it can derive from one."""
    taken = set(existing)
    while True:
        value = 'team-' + secrets.token_hex(8)
        if value not in taken:
            return value


def find_collision(name, specs):
    """Return the saved specification whose name has the same identity as `name`, or None."""
    key = name_key(name)
    return next((spec for spec in specs if name_key(spec['name']) == key), None)


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise Conflict(f'{label} must have exactly these fields: ' + ', '.join(sorted(expected)))


def _saved(holder, key, label, limit=TEXT_MAX):
    if _text(holder[key], label, limit) != holder[key]:
        raise Conflict(f'{label} is not in its saved form.')


def _member_of(value, collection):
    return isinstance(value, str) and value in collection


def _utc_stamp(value):
    """True for an existing calendar date and clock time in the exact form YYYY-MM-DDTHH:MM:SSZ."""
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        return False
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        return False
    return True


def validate_spec(spec, *, project_id, role_ids, coordinator):
    """Return a validated deep copy of a version 1 specification; the caller's object is never changed."""
    if not isinstance(spec, dict):
        raise Conflict('Team specification must be an object.')
    version = spec.get('schema_version')
    if type(version) is not int or version != SCHEMA_VERSION:
        raise Conflict(f'Unsupported team specification version {version!r}; this build reads version {SCHEMA_VERSION}.')
    _keys(spec, FIELDS, 'Team specification')
    value = copy.deepcopy(spec)
    if not isinstance(value['team_id'], str) or not TEAM_ID.fullmatch(value['team_id']):
        raise Conflict('Invalid team ID.')
    if type(value['revision']) is not int or value['revision'] < 1:
        raise Conflict('Revision must be a positive integer.')
    _saved(value, 'name', 'Team name', NAME_MAX)
    if not isinstance(project_id, str) or not project_id or value['project_id'] != project_id:
        raise Conflict('Team specification belongs to a different project.')
    if not _member_of(value['type'], TEAM_TYPES):
        raise Conflict('Team type must be one of: ' + ', '.join(TEAM_TYPES))
    _saved(value, 'purpose', 'Purpose')
    slots = _members(value['members'], role_ids)
    if value['type'] == 'sessions':  # No native dispatch lead; rules.integration_owner still coordinates.
        if value['lead'] is not None:
            raise Conflict('A sessions team records no native dispatch lead; its integration owner coordinates.')
    elif not _member_of(value['lead'], slots) or slots[value['lead']] != coordinator:
        raise Conflict('A subagents or teammates team needs a lead slot held by the coordinator role.')
    rules = value['rules']
    _keys(rules, RULES, 'Rules')
    for key in ('collaboration', 'outputs', 'completion', 'handoff'):
        _saved(rules, key, key.capitalize() + ' rule')
    if not _member_of(rules['integration_owner'], slots):
        raise Conflict('Integration owner must be one of the member slots.')
    if not _member_of(rules['work'], WORK_MODES):
        raise Conflict('Work must be one of: ' + ', '.join(WORK_MODES))
    _provenance(value['provenance'], value['type'], set(slots.values()))
    return value


def _members(members, role_ids):
    """Slots are unique; several slots may hold the same role."""
    if not isinstance(members, list) or not members:
        raise Conflict('A team needs at least one member slot.')
    slots = {}
    for member in members:
        _keys(member, MEMBER, 'Member')
        slot = member['slot']
        if not isinstance(slot, str) or not SLOT.fullmatch(slot) or len(slot) > SLOT_MAX:
            raise Conflict(f'Invalid member slot: {slot!r}')
        if slot in slots:
            raise Conflict(f'Duplicate member slot: {slot}')
        if not _member_of(member['role_id'], role_ids):
            raise Conflict(f'Unknown role for slot {slot}: {member["role_id"]!r}')
        _saved(member, 'responsibility', f'Responsibility of {slot}')
        slots[slot] = member['role_id']
    return slots


def _provenance(provenance, kind, member_roles):
    _keys(provenance, PROVENANCE, 'Provenance')
    _saved(provenance, 'generator', 'Generator', NAME_MAX)
    if provenance['asdg_build'] is not None:
        _saved(provenance, 'asdg_build', 'ASDG build', NAME_MAX)
    if not _utc_stamp(provenance['created_at']):
        raise Conflict('Creation time must be a real UTC date and time such as 2026-11-14T20:00:00Z.')
    definitions = provenance['definitions']
    if not isinstance(definitions, list) or (kind == 'sessions' and definitions):
        raise Conflict('Definitions must be a list, and a sessions team records none.')
    paths = set()
    for item in definitions:
        _keys(item, DEFINITION_FIELDS, 'Definition record')
        path = item['path']
        if not isinstance(path, str) or not DEFINITION.fullmatch(path) or path in paths:
            raise Conflict(f'Invalid or repeated definition path: {path!r}')
        paths.add(path)
        if not _member_of(item['role_id'], member_roles):
            raise Conflict(f'Definition {path} names a role no member holds.')
        for key in ('sha256', 'template_sha256'):
            if not isinstance(item[key], str) or not SHA.fullmatch(item[key]):
                raise Conflict(f'Definition {path} needs a 64-character {key}.')
