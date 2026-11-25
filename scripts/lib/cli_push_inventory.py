"""Validate replacement inputs without importing or executing a client's code."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from cli_files import Conflict
from cli_model import CORE, PROVIDER, git_value
from cli_sync_manifest import methodology_path, repository_id

INDEX = 'metadata/package-files.json'
MANIFEST = 'metadata/MANIFEST.json'
DESCRIPTOR = 'metadata/distribution.json'
CATALOG = 'metadata/push-replace-catalog.json'
SCHEMA = 'metadata/push-replace-ownership.schema.json'
OWNERSHIP = '.asdg/installation-ownership.json'
CANONICAL = 'github.com/elustondo-ai/asdg'
HASH = re.compile(r'[0-9a-f]{64}')
ENTRY_KINDS = {
    'distribution': ('shared', 'whole_file'), 'codex-skills': ('codex', 'whole_file'),
    'codex-roles': ('codex', 'whole_file'), 'claude-skills': ('claude', 'whole_file'),
    'claude-mods': ('claude', 'whole_file'), 'bootstrap': ('shared', 'marked_block'),
    'claude-bridge': ('claude', 'marked_block'), 'ignore': ('shared', 'marked_block'),
    'codex-config': ('codex', 'toml_key'), 'codex-hooks': ('codex', 'json_entry'),
}
MARKERS = {
    'bootstrap': ('<!-- ASDG:BEGIN bootstrap-v2 -->', '<!-- ASDG:END -->'),
    'claude-bridge': ('<!-- ASDG:BEGIN claude-bridge-v1 -->', '<!-- ASDG:END claude-bridge -->'),
    'ignore': ('# ASDG generated files: BEGIN', '# ASDG generated files: END'),
}
HOOK_EVENTS = {'PreToolUse', 'SubagentStart', 'SubagentStop', 'PostToolUse', 'PostToolUseFailure'}


def canonical(value) -> bytes:
    """Timeless canonical JSON; no trailing newline and no non-finite numbers."""
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Conflict('Value cannot be represented as canonical JSON.') from exc


def digest(raw: bytes | None) -> str | None:
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def strict_json(raw: bytes | str):
    """Read JSON while rejecting duplicate keys and non-finite numbers."""
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise Conflict('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              Conflict('Non-finite JSON number: ' + value)))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise Conflict('Invalid replacement JSON: ' + str(exc)) from exc


def safe_relative(name: str) -> str:
    """Require an exact normalized portable path, never a glob or Git metadata."""
    if not isinstance(name, str) or not name or re.search(r'[:\\*?\[\]\x00-\x1f\x7f]', name):
        raise Conflict('Unsafe replacement path: ' + repr(name))
    path = PurePosixPath(name)
    if (path.is_absolute() or path.as_posix() != name or name.endswith('/')
            or any(part in ('.', '..', '.git') for part in name.split('/'))):
        raise Conflict('Unsafe replacement path: ' + name)
    return name


def read_safe(root: Path, name: str) -> bytes | None:
    """Read one regular single-link file; reject symlinks and nested repositories."""
    safe_relative(name)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise Conflict('Expected a regular replacement root: ' + str(root))
    current = root
    parts = PurePosixPath(name).parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode):
            raise Conflict('Symlink in replacement path: ' + str(current))
        if index < len(parts) - 1:
            if not stat.S_ISDIR(info.st_mode):
                raise Conflict('Non-directory replacement ancestor: ' + str(current))
            if (current / '.git').exists() or (current / '.git').is_symlink():
                raise Conflict('Nested repository in replacement path: ' + str(current))
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16 * 1024 * 1024:
            raise Conflict('Expected a regular single-link file of at most 16 MiB: ' + str(current))
    # Reject a swap to a symlink between inspection and opening when supported.
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(current, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                    or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1):
                raise Conflict('Replacement input changed while opening: ' + str(current))
            return stream.read()
    except OSError as exc:
        raise Conflict('Cannot read replacement input: ' + str(current)) from exc


def _object(raw, name):
    value = strict_json(raw) if raw is not None else None
    if not isinstance(value, dict):
        raise Conflict('Missing or invalid JSON object: ' + name)
    return value


def _package_index(raw):
    value = _object(raw, INDEX)
    names = value.get('files')
    if (set(value) != {'schema_version', 'files'} or type(value['schema_version']) is not int
            or value['schema_version'] != 1 or not isinstance(names, list)
            or not all(isinstance(name, str) for name in names)
            or len(names) != len(set(names)) or not {INDEX, MANIFEST, DESCRIPTOR} <= set(names)):
        raise Conflict('Invalid exact package inventory.')
    for name in names:
        methodology_path(safe_relative(name))
    return sorted(names)


def _manifest(raw, names, version):
    value = _object(raw, MANIFEST)
    hashes = value.get('files')
    if (type(value.get('schema_version')) is not int or value['schema_version'] != 1
            or value.get('version') != version or not isinstance(hashes, dict)
            or set(hashes) != set(names) - {MANIFEST}):
        raise Conflict('Package inventory and manifest do not describe the same distribution.')
    for name, hash_value in hashes.items():
        methodology_path(safe_relative(name))
        if not isinstance(hash_value, str) or not HASH.fullmatch(hash_value):
            raise Conflict('Invalid manifest hash: ' + name)
    return hashes


def _distribution(raw):
    value = _object(raw, DESCRIPTOR)
    if (type(value.get('schema_version')) is not int or value['schema_version'] != 1
            or value.get('provider') != PROVIDER
            or value.get('installation_mode') != 'embedded-distribution'
            or not isinstance(value.get('version'), str)
            or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', value['version'])):
        raise Conflict('Unsupported ASDG distribution descriptor.')
    return value


def validated_source(source: Path) -> dict:
    """Freeze an integrity-checked package; a dirty snapshot gets no commit attribution."""
    requested = Path(source).expanduser()
    if requested.is_symlink() or not requested.is_dir():
        raise Conflict('Source must be a regular directory.')
    root = requested.resolve()
    git_root = git_value(root, 'rev-parse', '--show-toplevel')
    head = git_value(root, 'rev-parse', 'HEAD')
    remote = git_value(root, 'remote', 'get-url', 'origin')
    if not git_root or Path(git_root).resolve() != root or not head or not remote:
        raise Conflict('Source must be a standalone canonical Git root with a committed HEAD and origin.')
    if repository_id(remote) != CANONICAL:
        raise Conflict('Source Git origin is not the canonical ASDG repository.')
    names = _package_index(read_safe(root, INDEX))
    files = {name: read_safe(root, name) for name in names}
    if any(value is None for value in files.values()):
        raise Conflict('Missing file in source package inventory.')
    descriptor = _distribution(files[DESCRIPTOR])
    identity = repository_id(descriptor.get('canonical_repository', ''))
    if identity != CANONICAL:
        raise Conflict('Source does not identify the canonical ASDG repository.')
    hashes = _manifest(files[MANIFEST], names, descriptor['version'])
    if hashes != {name: digest(raw) for name, raw in files.items() if name != MANIFEST}:
        raise Conflict('Source package integrity failed; refresh/review the manifest before replacement.')
    for required in (CATALOG, SCHEMA, '00-governance/types/agent-catalog.json', 'AGENTS.md',
                     'scripts/cli.py', 'scripts/hook.py', 'skills/asdg-focus/session-policy.md',
                     'templates/.agents/skills/asdg-focus/SKILL.md'):
        if required not in files:
            raise Conflict('Source package is missing replacement metadata: ' + required)
    catalog = _object(files[CATALOG], CATALOG)
    entities = catalog.get('entities')
    if (catalog.get('schema_version') != 2 or catalog.get('catalog_id') != 'asdg-client-ownership'
            or catalog.get('scope') != 'initialized_client'
            or set(catalog.get('supported_clients', [])) != {'claude', 'codex'}
            or not isinstance(entities, list) or not all(isinstance(row, dict) and isinstance(row.get('id'), str) for row in entities)
            or len({row.get('id') for row in entities}) != len(entities)):
        raise Conflict('Unsupported or ambiguous replacement catalog.')
    by_id = {row['id']: row for row in entities}
    if not set(ENTRY_KINDS) <= set(by_id) or any(
            by_id[key].get('ownership_kind') != kind for key, (_, kind) in ENTRY_KINDS.items()):
        raise Conflict('Replacement catalog changes implemented ownership categories.')
    roles = _object(files['00-governance/types/agent-catalog.json'], 'agent catalogue').get('agents')
    if (not isinstance(roles, list) or len(roles) != 13
            or not all(isinstance(role, dict) and type(role.get('stage')) is int for role in roles)
            or sorted(role['stage'] for role in roles) != list(range(13))
            or any(role.get('role_id') != ('ASDG-COORDINATOR' if role['stage'] == 0 else
                                         'ASDG-%02d' % role['stage']) for role in roles)):
        raise Conflict('Source must preserve governance 00 and all twelve specialists.')
    from build_identity import commit_mismatch
    commit = head if commit_mismatch(root, head, files) is None else None
    generator_files = {name: digest(raw) for name, raw in files.items()
                       if name.startswith('scripts/') and name.endswith('.py')}
    return {'root': root, 'files': files, 'descriptor': descriptor, 'catalog': catalog,
            'catalog_sha256': digest(files[CATALOG]),
            'generator_sha256': digest(canonical(generator_files)),
            'identity': {'repository': identity, 'commit': commit,
                         'package_sha256': digest(canonical({name: digest(raw) for name, raw in files.items()})),
                         'manifest_sha256': digest(files[MANIFEST])}}


def target_identity(root: Path) -> dict:
    """Validate existing project/state and bind its actual Git repository and directory."""
    requested = Path(root).expanduser()
    if requested.is_symlink() or not requested.is_dir():
        raise Conflict('Target must be an existing regular directory.')
    root = requested.resolve()
    detected = git_value(root, 'rev-parse', '--show-toplevel')
    if not detected or Path(detected).resolve() != root:
        raise Conflict('Target must be the root of an existing Git worktree.')
    remote = git_value(root, 'remote', 'get-url', 'origin')
    if not remote:
        raise Conflict('Target needs an identifiable origin repository.')
    repository = repository_id(remote)
    if repository == CANONICAL:
        raise Conflict('The canonical source cannot be initialized/replaced as a client.')
    raw = read_safe(root, '.asdg/project.json')
    binding = _object(raw, '.asdg/project.json')
    if (type(binding.get('schema_version')) is not int or binding['schema_version'] != 1
            or binding.get('provider') != PROVIDER
            or binding.get('installation_mode') != 'embedded-distribution'
            or binding.get('distribution_root') != 'asdg' or binding.get('artifacts_root') != 'docs/asdg'
            or not isinstance(binding.get('project_id'), str) or not binding['project_id'].strip()
            or not isinstance(binding.get('stages'), list) or len(binding['stages']) != 13
            or not all(isinstance(stage, str) for stage in binding['stages'])
            or len(set(binding['stages'])) != 13):
        raise Conflict('Target needs a compatible initialized embedded ASDG binding.')
    for index, stage in enumerate(binding['stages']):
        if not isinstance(stage, str) or not re.fullmatch(r'%02d-[a-z0-9-]+' % index, stage):
            raise Conflict('Target stage identities require a separate migration.')
    _distribution(read_safe(root, 'asdg/' + DESCRIPTOR))
    from cli_sprint import validate as validate_sprint
    validate_sprint(root, _object(read_safe(root, '.asdg/sprint.json'), '.asdg/sprint.json'))
    _object(read_safe(root, '.asdg/lifecycle.json'), '.asdg/lifecycle.json')
    from cli_status import lifecycle_rules, read_lifecycle
    read_lifecycle(root, lifecycle_rules(CORE))
    common = git_value(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if not common:
        raise Conflict('Cannot establish target shared Git directory.')
    return {'repository': repository, 'root': str(root), 'git_common_dir': str(Path(common).resolve()),
            'project_id': binding['project_id'], 'binding_sha256': digest(raw)}


def legacy_distribution_inventory(root: Path, source: Path | None = None) -> dict:
    """Resolve exact legacy candidates; the explicit plan reviews unauthenticated evidence."""
    index_raw = read_safe(root, 'asdg/' + INDEX)
    manifest_raw = read_safe(root, 'asdg/' + MANIFEST)
    names = _package_index(index_raw)
    descriptor = _distribution(read_safe(root, 'asdg/' + DESCRIPTOR))
    hashes = _manifest(manifest_raw, names, descriptor['version'])
    if hashes[INDEX] != digest(index_raw):
        raise Conflict('Legacy inventory is not bound by its installed manifest.')
    if source is not None:
        source = Path(source)
        evidence_keys = (DESCRIPTOR, '00-governance/types/agent-catalog.json')
        candidates = [{key: digest(read_safe(source, key)) for key in evidence_keys}]
        deliveries = source / 'metadata/deliveries'
        if deliveries.is_symlink():
            raise Conflict('Symlink in historical distribution evidence.')
        if deliveries.is_dir():
            for item in sorted(deliveries.glob('*.json')):
                candidate = _object(read_safe(source, item.relative_to(source).as_posix()), item.name)
                if isinstance(candidate.get('files'), dict):
                    candidates.append(candidate['files'])
        if not any(all(hashes.get(key) == candidate.get(key) and hashes.get(key)
                       for key in evidence_keys) for candidate in candidates):
            raise Conflict('Legacy distribution cannot be linked to known canonical descriptor and catalogue bytes.')
    # An index is exact local evidence, not a directory wildcard or authenticated approval.
    for name in names:
        read_safe(root, 'asdg/' + name)
    return {'paths': ['asdg/' + name for name in names],
            'evidence_sha256': digest(canonical({'index': digest(index_raw), 'manifest': digest(manifest_raw)})),
            'index_sha256': digest(index_raw), 'manifest_sha256': digest(manifest_raw),
            'evidence_status': 'LOCAL_UNAUTHENTICATED_EVIDENCE'}


def _schema_matches(value, schema, document):
    """Evaluate the fixed receipt schema subset using the standard library only."""
    if '$ref' in schema:
        referred = document
        for part in schema['$ref'].removeprefix('#/').split('/'):
            referred = referred[part]
        return _schema_matches(value, referred, document)
    types = {'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
             'string': lambda x: isinstance(x, str), 'null': lambda x: x is None,
             'boolean': lambda x: type(x) is bool, 'integer': lambda x: type(x) is int}
    if 'type' in schema and not types[schema['type']](value):
        return False
    if 'const' in schema and canonical(value) != canonical(schema['const']):
        return False
    if 'enum' in schema and canonical(value) not in [canonical(item) for item in schema['enum']]:
        return False
    if isinstance(value, str) and (len(value) < schema.get('minLength', 0)
                                  or ('pattern' in schema and re.search(schema['pattern'], value) is None)):
        return False
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        if not set(schema.get('required', [])) <= set(value):
            return False
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            return False
        if any(not _schema_matches(value[key], rule, document) for key, rule in properties.items() if key in value):
            return False
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', len(value)):
            return False
        if schema.get('uniqueItems') and len({canonical(item) for item in value}) != len(value):
            return False
        if 'items' in schema and any(not _schema_matches(item, schema['items'], document) for item in value):
            return False
    for operator, predicate in (('allOf', all), ('anyOf', any)):
        if operator in schema and not predicate(_schema_matches(value, row, document) for row in schema[operator]):
            return False
    if 'oneOf' in schema and sum(_schema_matches(value, row, document) for row in schema['oneOf']) != 1:
        return False
    if 'not' in schema and _schema_matches(value, schema['not'], document):
        return False
    if 'if' in schema and _schema_matches(value, schema['if'], document):
        if not _schema_matches(value, schema.get('then', {}), document):
            return False
    return True


def _entry_scope(entry):
    name, entity = safe_relative(entry['path']), entry['entity_id']
    client, kind = ENTRY_KINDS[entity]
    if (entry['client'], entry['ownership_kind']) != (client, kind):
        raise Conflict('Ownership category/client mismatch: ' + name)
    if entity == 'distribution':
        if not name.startswith('asdg/'):
            raise Conflict('Distribution entry is outside asdg/: ' + name)
        methodology_path(name[5:])
    elif entity == 'codex-skills':
        if not re.fullmatch(r'\.agents/skills/asdg-[a-z0-9-]+/(?:SKILL\.md|agents/openai\.yaml)', name):
            raise Conflict('Outside exact Codex adapter scope: ' + name)
    elif entity == 'codex-roles':
        if not re.fullmatch(r'\.codex/agents/asdg_(?:coordinator|0[1-9]|1[0-2])\.toml', name):
            raise Conflict('Outside exact Codex role scope: ' + name)
    elif entity == 'claude-skills':
        if not re.fullmatch(r'\.claude/skills/asdg-[a-z0-9-]+/SKILL\.md', name):
            raise Conflict('Outside exact Claude adapter scope: ' + name)
    elif entity == 'claude-mods':
        if not re.fullmatch(r'\.claude/skills/asdg-[a-z0-9-]+/(?:\.claude-plugin/plugin\.json|hooks/hooks\.json|hooks/register\.tsx|types/index\.d\.ts)', name):
            raise Conflict('Outside exact Claude mod scope: ' + name)
    else:
        allowed = {'bootstrap': {'AGENTS.md'}, 'ignore': {'.gitignore'},
                   'claude-bridge': {'CLAUDE.md', '.claude/CLAUDE.md'},
                   'codex-config': {'.codex/config.toml'}, 'codex-hooks': {'.codex/hooks.json'}}
        if name not in allowed[entity]:
            raise Conflict('Owned section has the wrong destination: ' + name)
        selector = entry['selector']
        if entity in MARKERS and selector != dict(zip(('start', 'end'), MARKERS[entity])):
            raise Conflict('Unknown owned marker selector: ' + name)
        if entity == 'codex-config' and selector != {'key_path': ['features', 'hooks']}:
            raise Conflict('Only features.hooks is an ASDG configuration requirement.')
        if entity == 'codex-hooks' and (selector['array_pointer'] not in {'/hooks/' + event for event in HOOK_EVENTS}
                                      or selector['identity_sha256'] != entry['installed_sha256']):
            raise Conflict('Invalid exact hook entry identity.')
        original = entry['original']
        if original['present']:
            value = original['value']
            if kind == 'marked_block' and not isinstance(value, str):
                raise Conflict('Original marked block must be text.')
            if kind == 'toml_key' and type(value) is not bool:
                raise Conflict('Original hooks feature value must be a boolean.')
            raw = value.encode('utf-8') if kind == 'marked_block' else canonical(value)
            if digest(raw) != original['sha256']:
                raise Conflict('Original owned value hash mismatch: ' + name)


def validate_ownership(value, target=None, clients=None) -> dict:
    """Check closed shape and exact scope; local receipt validity is not authentication."""
    canonical(value)
    schema = _object(read_safe(CORE, SCHEMA), SCHEMA)
    if not _schema_matches(value, schema, schema):
        raise Conflict('Invalid or unsupported installation ownership receipt.')
    if value['source']['repository'].lower() != CANONICAL:
        raise Conflict('Ownership receipt has a foreign source repository.')
    if target is not None and value['target'] != target:
        raise Conflict('Ownership receipt belongs to another project binding or worktree.')
    if clients is not None and set(value['clients']) != set(clients):
        raise Conflict('Ownership receipt client selection changed; reconcile explicitly.')
    paths = {}
    for entry in value['entries']:
        _entry_scope(entry)
        if entry['client'] != 'shared' and entry['client'] not in value['clients']:
            raise Conflict('Receipt entry belongs to an unselected client.')
        name = entry['path']
        previous = paths.setdefault(name, [])
        if previous and (entry['ownership_kind'] != 'json_entry'
                         or any(row['ownership_kind'] != 'json_entry' for row in previous)):
            raise Conflict('Overlapping ownership entries: ' + name)
        if any(canonical(row.get('selector')) == canonical(entry.get('selector')) for row in previous):
            raise Conflict('Duplicate ownership selector: ' + name)
        previous.append(entry)
    for name in paths:
        if any('/'.join(PurePosixPath(name).parts[:i]) in paths for i in range(1, len(PurePosixPath(name).parts))):
            raise Conflict('Overlapping file and descendant ownership: ' + name)
    return value


def load_ownership(root: Path, target=None, clients=None) -> dict | None:
    raw = read_safe(root, OWNERSHIP)
    return validate_ownership(strict_json(raw), target, clients) if raw is not None else None
