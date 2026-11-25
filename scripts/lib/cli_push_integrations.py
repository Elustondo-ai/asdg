"""Pure, ownership-bounded integration planning and verification for push replace."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from cli_files import Conflict, read_bytes, safe_path
from cli_clients import BRIDGE_BEGIN, BRIDGE_END, MOD_FILES, _imports_agents
from cli_project import BRIDGE, BEGIN, END, IGNORE, IGNORE_BEGIN, IGNORE_END, LEGACY_BRIDGES, hook_config
from distribution_files import package_files

GENERATOR = {'id': 'asdg-push-integrations', 'version': '1'}
WHOLE = {'codex-skills', 'codex-roles', 'claude-skills', 'claude-mods'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Conflict('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(Conflict('Non-finite JSON value.')))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Conflict('Invalid integration JSON: ' + str(exc)) from exc


def _read(root, relative, observations):
    path = safe_path(root, relative)
    if path.is_file() and path.stat().st_nlink != 1:
        raise Conflict('Refusing a multiply linked integration file: ' + str(relative))
    raw = read_bytes(path)
    observations[str(relative)] = digest(raw)
    return raw


def _entry(entity, client, path, kind, raw, selector=None, original=None):
    value = {'entity_id': entity, 'client': client, 'path': str(path), 'ownership_kind': kind,
             'installed_sha256': digest(raw), 'generator': dict(GENERATOR)}
    if selector is not None:
        value.update(selector=selector, original=original or {'present': False})
    return value


def _prior(entries, path, entity=None):
    return [entry for entry in entries if entry.get('path') == str(path)
            and (entity is None or entry.get('entity_id') == entity)]


def _original(prior, present, value, raw=None):
    if prior:
        return copy.deepcopy(prior[0]['original'])
    if not present:
        return {'present': False}
    return {'present': True, 'value': value, 'sha256': digest(raw if raw is not None else canonical(value))}


def _render(core, clients):
    """Render selected source members directly; never import a target's Python."""
    selected = {p.relative_to(core).as_posix(): p for p in package_files(core)}
    result = {}
    for name, path in selected.items():
        if name.startswith('templates/.agents/skills/') and 'codex' in clients:
            result[name[len('templates/'):]] = (path.read_bytes(), 'codex-skills', 'codex')
        elif name.startswith('templates/.codex/agents/') and 'codex' in clients:
            result[name[len('templates/'):]] = (path.read_bytes(), 'codex-roles', 'codex')
    if 'claude' in clients:
        names = sorted(Path(name).parent.name for name in selected
                       if name.startswith('templates/.agents/skills/') and name.endswith('/SKILL.md'))
        for name in names:
            prefix = 'templates/.agents/skills/' + name + '/'
            text = selected[prefix + 'SKILL.md'].read_bytes().decode('utf-8')
            match = re.match(r'---\n(.*?)\n---\n', text, re.DOTALL)
            fields = dict(line.split(': ', 1) for line in match.group(1).splitlines() if ': ' in line) if match else {}
            if not match or set(fields) != {'name', 'description'} or fields['name'] != name:
                raise Conflict('Invalid source skill adapter: ' + name)
            head = f"---\nname: {name}\ndescription: {fields['description']}\n"
            policy = selected.get(prefix + 'agents/openai.yaml')
            if policy and re.search(rb'^\s+allow_implicit_invocation:\s*false\s*$', policy.read_bytes(), re.MULTILINE):
                head += 'disable-model-invocation: true\n'
            result['.claude/skills/' + name + '/SKILL.md'] = (
                (head + '---\n' + text[match.end():]).encode(), 'claude-skills', 'claude')
        mods = sorted(Path(name).parents[1].name for name in selected
                      if name.startswith('mods/') and name.endswith('/.claude-plugin/plugin.json'))
        for name in mods:
            if name in names:
                raise Conflict('Source skill and mod share a name: ' + name)
            for suffix in MOD_FILES:
                member = selected.get('mods/' + name + '/' + suffix)
                if member is None:
                    raise Conflict('Missing source mod runtime member: ' + name + '/' + suffix)
                data = member.read_bytes()
                if suffix == '.claude-plugin/plugin.json' and _json(data).get('name') != name:
                    raise Conflict('Source mod manifest name differs: ' + name)
                result['.claude/skills/' + name + '/' + suffix] = (data, 'claude-mods', 'claude')
    return result


def _old_render(root, clients):
    core = root / 'asdg'
    try:
        manifest = _json(read_bytes(safe_path(core, 'metadata/MANIFEST.json')) or b'{}').get('files', {})
        values = _render(core, clients)
        # Only bytes sourced from an intact delivered template/mod establish a legacy match.
        for path in package_files(core):
            name = path.relative_to(core).as_posix()
            if name.startswith(('templates/', 'mods/')) and manifest.get(name) != digest(path.read_bytes()):
                return {}
        return values
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def _block(raw, block, begin, end, prior, path, first=False, alternatives=()):
    """Replace one unambiguous owned block, retaining all bytes outside its span."""
    text = (raw or b'').decode('utf-8')
    if first and text.startswith('---\n'):
        raise Conflict('YAML-first bootstrap requires explicit reconciliation: ' + path)
    marker = begin
    if first:
        possible = [item for item in alternatives if item in text]
        if possible:
            marker = possible[0].splitlines()[0]
        if text.count('<!-- ASDG:BEGIN') > 1:
            raise Conflict('Ambiguous ASDG bootstrap markers: ' + path)
        if text.count('<!-- ASDG:BEGIN') != text.count(marker):
            raise Conflict('Unknown ASDG bootstrap marker requires reconciliation: ' + path)
    count = (text.count(marker), text.count(end))
    for boundary in (marker, end):
        if text.count(boundary) != len(re.findall(r'^' + re.escape(boundary) + r'\r?$', text, re.MULTILINE)):
            raise Conflict('Managed markers must occupy complete lines: ' + path)
    if count == (0, 0):
        if prior:
            raise Conflict('Previously owned block markers are missing: ' + path)
        remainder = text
        data = block + remainder if first else text + ('\n' if text and not text.endswith('\n') else '') + block
        original = {'present': False}
    elif count == (1, 1):
        start, finish = text.index(marker), text.index(end) + len(end)
        if finish <= start:
            raise Conflict('Reversed managed markers: ' + path)
        if text[finish:finish + 2] == '\r\n':
            finish += 2
        elif text[finish:finish + 1] == '\n':
            finish += 1
        # Recognized markers bound a methodology block; the reviewed plan shows overwritten content.
        original = _original(prior, False, None)
        if first:
            data = block + text[:start] + text[finish:]
        else:
            data = text[:start] + block + text[finish:]
    else:
        raise Conflict('Ambiguous or incomplete managed block: ' + path)
    return data.encode(), original


def _toml(raw, prior):
    if tomllib is None:
        raise Conflict('UNSUPPORTED_TOML: Codex push replace requires Python 3.11+ or an installed tomli parser; no files changed.')
    text = (raw or b'').decode('utf-8')
    try:
        current = tomllib.loads(text)
    except (ValueError, TypeError) as exc:
        raise Conflict('Invalid Codex TOML: ' + str(exc)) from exc
    features = current.get('features', {})
    if not isinstance(features, dict):
        raise Conflict('Codex features must be a TOML table.')
    present = 'hooks' in features
    before = features.get('hooks')
    original = _original(prior, present, before)
    if before is True:
        return raw, original
    if present and not prior:
        raise Conflict('Existing features.hooks differs without prior ASDG ownership; explicit adoption required.')
    lines = text.splitlines(keepends=True)
    section = ''
    locations, feature_header = [], None
    for index, line in enumerate(lines):
        header = re.fullmatch(r'\s*\[([^\[\]]+)\]\s*(?:#.*)?(?:\r?\n)?', line)
        if header:
            section = header.group(1).strip()
            if section == 'features':
                feature_header = index
        pattern = r'^(\s*hooks\s*=\s*)([^#\r\n]*)(.*)$' if section == 'features' else (
            r'^(\s*features\.hooks\s*=\s*)([^#\r\n]*)(.*)$' if not section else r'(?!)')
        found = re.match(pattern, line, re.DOTALL)
        if found:
            locations.append((index, found))
    if present:
        if len(locations) != 1:
            raise Conflict('Codex features.hooks uses unsupported or ambiguous TOML syntax; preserve and reconcile.')
        index, found = locations[0]
        whitespace = re.search(r'\s*$', found.group(2)).group()
        lines[index] = found.group(1) + 'true' + whitespace + found.group(3)
        result = ''.join(lines)
    elif feature_header is not None:
        line = lines[feature_header]
        if not line.endswith('\n'):
            lines[feature_header] += '\n'
        lines.insert(feature_header + 1, 'hooks = true\n')
        result = ''.join(lines)
    elif 'features' not in current:
        result = text + ('\n' if text and not text.endswith('\n') else '') + '[features]\nhooks = true\n'
    else:
        raise Conflict('Codex features table uses unsupported TOML syntax; preserve and reconcile.')
    wanted = copy.deepcopy(current)
    wanted.setdefault('features', {})['hooks'] = True
    try:
        if tomllib.loads(result) != wanted:
            raise Conflict('TOML edit would change unrelated settings.')
    except ValueError as exc:
        raise Conflict('Cannot safely edit Codex TOML: ' + str(exc)) from exc
    return result.encode(), original


def _hooks(raw, expected, prior):
    current = _json(raw) if raw is not None else {}
    if not isinstance(current, dict) or not isinstance(current.get('hooks', {}), dict):
        raise Conflict('Codex hooks must contain an object of event arrays.')
    result = copy.deepcopy(current)
    events = result.setdefault('hooks', {})
    if any(not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
           for items in events.values()):
        raise Conflict('Codex hook events must be arrays of objects.')
    commands = {hook['command'] for items in expected['hooks'].values()
                for item in items for hook in item.get('hooks', []) if isinstance(hook.get('command'), str)}
    def suspected(value):
        if isinstance(value, dict):
            command = value.get('command')
            if isinstance(command, str) and (command in commands or 'asdg/scripts/hook.py' in command):
                return True
            return any(suspected(item) for item in value.values())
        return isinstance(value, list) and any(suspected(item) for item in value)
    # A recognizable command can require reconciliation; it never establishes ownership.
    # Otherwise an edited or moved legacy hook would survive beside an appended current hook.
    for event, items in events.items():
        identities = {digest(canonical(item)) for item in expected['hooks'].get(event, [])}
        identities.update(entry['selector']['identity_sha256'] for entry in prior
                          if entry['selector']['array_pointer'] == '/hooks/' + event)
        if any(suspected(item) and digest(canonical(item)) not in identities for item in items):
            raise Conflict('Unidentified ASDG-like hook registration requires explicit reconciliation: ' + event)
    entries = []
    for event, expected_items in expected['hooks'].items():
        item = expected_items[0]
        wanted_hash = digest(canonical(item))
        pointer = '/hooks/' + event
        old = [entry for entry in prior if entry['selector']['array_pointer'] == pointer]
        if len(old) > 1:
            raise Conflict('Multiple ownership records for one ASDG hook event: ' + event)
        items = events.setdefault(event, [])
        exact = [i for i, entry in enumerate(items) if digest(canonical(entry)) == wanted_hash]
        owned = [i for i, entry in enumerate(items) if old and digest(canonical(entry)) == old[0]['selector']['identity_sha256']]
        if len(exact) > 1 or len(owned) > 1 or (exact and owned and exact != owned):
            raise Conflict('Duplicate or ambiguous ASDG hook registration: ' + event)
        if exact:
            pass
        elif owned:
            items[owned[0]] = item
        elif old:
            raise Conflict('Previously owned hook is missing or changed; reconcile its identity: ' + event)
        else:
            items.append(item)
        entries.append(_entry('codex-hooks', 'codex', '.codex/hooks.json', 'json_entry', canonical(item),
                              {'array_pointer': pointer, 'identity_sha256': wanted_hash},
                              _original(old, False, None)))
    if raw is None:
        result.setdefault('description', expected['description'])
    return raw if result == current else (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode(), entries


def integration_plan(root: Path, source: Path, clients: list[str], prior_entries: list[dict]) -> dict:
    """Pure plan. Caller validates bound ownership, source identity and explicit apply permission."""
    root, source = Path(root).resolve(), Path(source).resolve()
    desired, observations, entries, conflicts = {}, {}, [], []
    if not clients or set(clients) - {'codex', 'claude'} or len(clients) != len(set(clients)):
        return {'desired': {}, 'entries': [], 'observations': {}, 'conflicts': ['Invalid selected clients.']}
    try:
        rendered = _render(source, clients)
        legacy = _old_render(root, clients)
    except (OSError, ValueError, UnicodeError) as exc:
        return {'desired': {}, 'entries': [], 'observations': {}, 'conflicts': [str(exc)]}
    def attempt(call):
        try:
            call()
        except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
            conflicts.append(str(exc))
    for path, (data, entity, client) in rendered.items():
        def whole(path=path, data=data, entity=entity, client=client):
            old = _read(root, path, observations)
            owned = _prior(prior_entries, path, entity)
            if old not in (None, data) and not owned and (path not in legacy or old != legacy[path][0]):
                raise Conflict('Unknown integration collision; explicit adoption required: ' + path)
            desired[path] = data
            entries.append(_entry(entity, client, path, 'whole_file', data))
        attempt(whole)
    for old in prior_entries:
        path = old.get('path', '')
        if old.get('entity_id') not in WHOLE or old.get('client') not in clients or path in rendered:
            continue
        def retire(old=old, path=path):
            allowed = (path.startswith('.agents/skills/asdg-') if old['client'] == 'codex' and old['entity_id'] == 'codex-skills'
                       else path.startswith('.codex/agents/asdg_') and path.endswith('.toml') if old['entity_id'] == 'codex-roles'
                       else path.startswith('.claude/skills/asdg-'))
            if not allowed or old.get('ownership_kind') != 'whole_file':
                raise Conflict('Out-of-scope prior integration ownership: ' + path)
            _read(root, path, observations)
            desired[path] = None
        attempt(retire)
    for entity, path, block, begin, end, first in (
            ('bootstrap', 'AGENTS.md', BRIDGE, BEGIN, END, True),
            ('ignore', '.gitignore', IGNORE, IGNORE_BEGIN, IGNORE_END, False)):
        def managed(entity=entity, path=path, block=block, begin=begin, end=end, first=first):
            raw = _read(root, path, observations)
            data, original = _block(raw, block, begin, end, _prior(prior_entries, path, entity),
                                    path, first, LEGACY_BRIDGES if first else ())
            desired[path] = data
            entries.append(_entry(entity, 'shared', path, 'marked_block', block.encode(),
                                  {'start': begin, 'end': end}, original))
        attempt(managed)
    if 'codex' in clients:
        def config():
            path = '.codex/config.toml'; raw = _read(root, path, observations)
            data, original = _toml(raw, _prior(prior_entries, path, 'codex-config'))
            desired[path] = data
            entries.append(_entry('codex-config', 'codex', path, 'toml_key', canonical(True),
                                  {'key_path': ['features', 'hooks']}, original))
        attempt(config)
        def hooks():
            path = '.codex/hooks.json'; raw = _read(root, path, observations)
            desired[path], found = _hooks(raw, _json(hook_config(root)), _prior(prior_entries, path, 'codex-hooks'))
            entries.extend(found)
        attempt(hooks)
    if 'claude' in clients:
        def bridge():
            # Always ensure the selected Claude integration imports AGENTS. This avoids an
            # unbound dependency on mutable parent-folder CLAUDE files and preserves user imports.
            path = '.claude/CLAUDE.md' if not (root / 'CLAUDE.md').exists() and (root / '.claude/CLAUDE.md').exists() else 'CLAUDE.md'
            old_bridges = [entry for entry in prior_entries if entry.get('entity_id') == 'claude-bridge']
            if len(old_bridges) > 1 or (old_bridges and old_bridges[0]['path'] != path):
                raise Conflict('Claude bridge destination changed; reconcile prior owned import first.')
            raw = _read(root, path, observations)
            line = '@../AGENTS.md' if path.startswith('.claude/') else '@AGENTS.md'
            block = f'{BRIDGE_BEGIN}\n{line}\n{BRIDGE_END}\n'
            prior = _prior(prior_entries, path, 'claude-bridge')
            text = (raw or b'').decode('utf-8')
            if not prior and BRIDGE_BEGIN not in text and BRIDGE_END not in text and _imports_agents(text, line):
                return
            data, original = _block(raw, block, BRIDGE_BEGIN, BRIDGE_END, prior, path)
            desired[path] = data
            entries.append(_entry('claude-bridge', 'claude', path, 'marked_block', block.encode(),
                                  {'start': BRIDGE_BEGIN, 'end': BRIDGE_END}, original))
        attempt(bridge)
    entries.sort(key=lambda e: (e['path'], canonical(e.get('selector')).decode()))
    return {'desired': desired, 'entries': entries, 'observations': observations, 'conflicts': conflicts}


def integration_problems(root: Path, source: Path, clients: list[str], entries=None) -> list[str]:
    """Verify owned semantics, preserving unrelated settings; never certify native execution."""
    result = integration_plan(root, source, clients, entries or [])
    problems = list(result['conflicts'])
    for path, wanted in result['desired'].items():
        try:
            if read_bytes(safe_path(root, path)) != wanted:
                problems.append(path + ': ASDG-owned integration needs reconciliation')
        except (OSError, ValueError) as exc:
            problems.append(str(exc))
    return problems
