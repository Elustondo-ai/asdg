"""Deterministic replacement of an initialized client's ASDG-owned entities."""
from __future__ import annotations

import base64
import copy
import os
import stat
from pathlib import Path

from build_identity import commit_build, record_bytes
from cli_clients import INTEGRATIONS, integrations_bytes, resolve_clients
from cli_files import Conflict
from cli_model import CORE, now
from cli_push_inventory import (canonical, digest, legacy_distribution_inventory, load_ownership,
                                read_safe, strict_json, target_identity, validated_source,
                                validate_ownership)
from cli_sync_manifest import encoded, git, read_state

OWNERSHIP = '.asdg/installation-ownership.json'
LEDGER = '.asdg/document-reviews.json'
SYNC = 'asdg/metadata/sync-state.json'
BUILD = 'asdg/metadata/build.json'


def _state(root, path):
    data = read_safe(root, path)
    mode = stat.S_IMODE((root / path).stat().st_mode) if data is not None else None
    return {'sha256': digest(data), 'mode': mode}


def _preserved(root, mutable):
    """Observe bounded state/document/integration trees, never worktrees or Git metadata."""
    result = {}
    for folder in ('.asdg', 'docs/asdg', '.agents', '.codex', '.claude'):
        start = root / folder
        if start.is_symlink():
            result[folder] = {'symlink': os.readlink(start)}
            continue
        if not start.exists():
            continue
        for directory, dirs, files in os.walk(start, followlinks=False):
            rel = Path(directory).relative_to(root)
            dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink()
                             and d != '.git' and (rel / d).as_posix() not in
                             ('.asdg/backups', '.claude/worktrees'))
            for name in sorted(files):
                path = (rel / name).as_posix()
                if path in mutable or path == '.asdg/cache/push-replace.lock':
                    continue
                file = root / path
                if file.is_symlink():
                    result[path] = {'symlink': os.readlink(file)}
                else:
                    result[path] = _state(root, path)
    return result


def _changes(root, desired):
    changes = []
    for path, after in sorted(desired.items()):
        before = _state(root, path)
        if before['sha256'] == digest(after):
            continue
        changes.append({'path': path, 'before_sha256': before['sha256'],
                        'before_mode': before['mode'], 'after': after,
                        'after_mode': (before['mode'] if before['mode'] is not None else 0o644) if after is not None else None})
    return changes


def _description(change):
    return {k: v for k, v in change.items() if k != 'after'} | {
        'after_sha256': digest(change['after']),
        'action': 'delete' if change['after'] is None else
                  'create' if change['before_sha256'] is None else 'replace'}


def _receipt_material(receipt):
    return {key: value for key, value in receipt.items()
            if key not in ('plan_basis_sha256', 'provenance')}


def preview(source_path, target_path):
    from cli_push_integrations import integration_plan
    from cli_push_transaction import assert_idle
    source = validated_source(Path(source_path))
    for name, data in source['files'].items():
        if (name.startswith('scripts/') and name.endswith('.py')) or name in (
                'metadata/push-replace-catalog.json', 'metadata/push-replace-ownership.schema.json'):
            if read_safe(CORE, name) != data:
                raise Conflict('Run the selected source checkout\'s own CLI; generator differs: ' + name)
    root = Path(target_path).expanduser().resolve()
    target = target_identity(Path(target_path))
    assert_idle(root)
    origin = source['root']
    if root == origin or root in origin.parents or origin in root.parents:
        raise Conflict('Source and target must be separate, non-nested repositories.')
    if target['repository'] == source['identity']['repository']:
        raise Conflict('The canonical repository cannot be its own replacement client.')
    for path in (INTEGRATIONS.as_posix(), SYNC):
        raw = read_safe(root, path)
        if raw is not None:
            value = strict_json(raw)  # Legacy validators must never silently collapse duplicate keys.
            if path == INTEGRATIONS.as_posix() and isinstance(value, dict) and value.get('clients') == {}:
                raise Conflict('Recorded integration selection is empty; initialize it separately.')
    recorded, clients, notes = resolve_clients(root, None, True)
    if not clients:
        raise Conflict('No recorded integration; initialize the client separately.')
    prior = load_ownership(root, target=target, clients=clients)
    legacy = legacy_distribution_inventory(root, origin) if prior is None else None
    owned = {entry['path'] for entry in prior['entries'] if entry['entity_id'] == 'distribution'} if prior else set(legacy['paths'])
    desired, entries, conflicts, observations = {}, [], [], {}
    for name, data in sorted(source['files'].items()):
        path = 'asdg/' + name
        old = read_safe(root, path)
        if old is not None and path not in owned:
            conflicts.append('Unproven existing distribution file: ' + path)
        desired[path] = data
        entries.append({'entity_id': 'distribution', 'client': 'shared', 'path': path,
                        'ownership_kind': 'whole_file', 'installed_sha256': digest(data),
                        'generator': {'id': 'package_manifest_files', 'version': '1'}})
    for path in sorted(owned - set(desired)):
        desired[path] = None
    integration = integration_plan(root, origin, clients, prior['entries'] if prior else [])
    desired.update(integration['desired'])
    entries.extend(integration['entries'])
    conflicts.extend(integration['conflicts'])
    observations.update(integration['observations'])
    desired[INTEGRATIONS.as_posix()] = (read_safe(root, INTEGRATIONS.as_posix()) or integrations_bytes(recorded))
    # Keep the existing compatible upgrade schema and all other upstream records.
    state = read_state(root / 'asdg')
    hashes = {path: digest(data) for path, data in source['files'].items()}
    descriptor = strict_json(source['files']['metadata/distribution.json'])
    head = git(origin, 'rev-parse', 'HEAD')
    record = {'operation': 'upgrade', 'method': 'push-replace',
              'target_repository': target['repository'], 'target_binding_sha256': target['binding_sha256'],
              'source_repository': source['identity']['repository'], 'source_commit': head,
              'version': descriptor['version'], 'snapshot_sha256': digest(encoded(hashes)),
              'files': hashes, 'source_snapshot_kind': 'MANIFEST_MATCHED_DISTRIBUTION',
              'human_approval_status': 'NOT_ESTABLISHED'}
    state['upstreams'][source['identity']['repository']] = record
    desired[SYNC] = encoded(state)
    build = None
    if source['identity']['commit']:
        build = commit_build(origin, source['identity']['commit'], descriptor['version'], source['files'])
    desired[BUILD] = record_bytes(build) if build else None
    entries.sort(key=lambda entry: (entry['path'], canonical(entry.get('selector', {}))))
    ledger_raw = read_safe(root, LEDGER)
    ledger = strict_json(ledger_raw) if ledger_raw is not None else None
    if not isinstance(ledger, dict) or ledger.get('schema_version') != 1 or not isinstance(ledger.get('events'), list):
        raise Conflict('Restore the existing document review history before replacement.')
    observations.update({OWNERSHIP: digest(read_safe(root, OWNERSHIP)), LEDGER: digest(ledger_raw)})
    for path in desired:
        observations[path] = digest(read_safe(root, path))
    preserved = _preserved(root, set(desired) | {OWNERSHIP, LEDGER})
    material = {'schema_version': 1, 'kind': 'asdg-installation-ownership',
                'evidence_status': 'LOCAL_UNAUTHENTICATED_EVIDENCE',
                'catalog_schema_version': 2, 'catalog_sha256': source['catalog_sha256'],
                'source': source['identity'], 'target': target, 'clients': clients, 'entries': entries}
    payload_changes = _changes(root, desired)
    unchanged = prior is not None and _receipt_material(prior) == material and not payload_changes
    basis = {'schema_version': 1, 'source': source['identity'], 'target': target, 'clients': clients,
             'catalog_sha256': source['catalog_sha256'], 'generator_sha256': source['generator_sha256'],
             'legacy_evidence': legacy, 'observations': observations, 'preserved': preserved,
             'changes': [_description(change) for change in payload_changes], 'conflicts': sorted(conflicts)}
    basis_digest = digest(canonical(basis))
    if unchanged:
        desired[OWNERSHIP] = read_safe(root, OWNERSHIP)
    else:
        receipt = dict(material, plan_basis_sha256=basis_digest,
                       provenance={'method': 'exact_plan_apply' if prior else 'reviewed_legacy_adoption',
                                   'inventory_basis_sha256': digest(canonical(entries))})
        validate_ownership(receipt, target=target, clients=clients)
        desired[OWNERSHIP] = canonical(receipt)
    changes = _changes(root, desired)
    events = []
    for change in changes:
        if change['path'].endswith('.md'):
            events.append({'path': change['path'], 'sha256': digest(change['after']),
                           'event': 'AI-REMOVED' if change['after'] is None else 'AI-MODIFIED',
                           'human_approval': None, 'previous_sha256': change['before_sha256'],
                           'provenance': {'role_id': 'ASDG-ADMIN', 'generator': 'asdg push-replace'}})
    intent = {'kind': 'append-review-events', 'path': LEDGER, 'before_sha256': digest(ledger_raw),
              'events': events, 'runtime_fields': ['recorded_at', 'plan_id']}
    plan_id = digest(canonical({'basis': basis, 'changes': [_description(c) for c in changes],
                                'audit_intent': intent}))
    expected = {}
    for path, data in desired.items():
        if path == OWNERSHIP:
            continue
        mode = _state(root, path)['mode']
        expected[path] = {'sha256': digest(data),
                          'mode': (mode if mode is not None else 0o644) if data is not None else None}
    verification = {'target': target, 'clients': clients, 'expected': expected, 'preserved': preserved}
    return {'operation': 'push-replace', 'source': source['identity'], 'target': target,
            'clients': clients, 'plan_id': plan_id, 'plan_basis_sha256': basis_digest,
            'changes': changes, 'audit_intent': intent, 'conflicts': sorted(conflicts),
            'unchanged': unchanged, 'notes': notes, 'verification': verification,
            'ownership_inventory': entries, 'preserved_paths': sorted(preserved),
            'native_runtime': 'NOT_VERIFIED', 'hook_trust': 'NOT_ASSESSED'}


def verify_payload(root, verification):
    if target_identity(root) != verification['target']:
        raise Conflict('Target identity changed during replacement.')
    for path, expected in verification['expected'].items():
        if _state(root, path) != expected:
            raise Conflict('Installed content or mode differs: ' + path)
    for path, expected in verification['preserved'].items():
        actual = {'symlink': os.readlink(root / path)} if 'symlink' in expected and (root / path).is_symlink() else _state(root, path)
        if actual != expected:
            raise Conflict('Preserved content changed: ' + path)
    # Verify structural compatibility without requiring a newly published ownership receipt.
    # Shared-file validation is performed by the new integration verifier below.
    from cli_push_integrations import integration_problems
    problems = integration_problems(root, root / 'asdg', verification['clients'])
    if problems:
        raise Conflict('Client integration verification failed: ' + '; '.join(problems))
    return {'files': 'VERIFIED', 'preserved': 'VERIFIED', 'native_runtime': 'NOT_VERIFIED'}


def replace(source, target, *, apply=False, expected_plan=None):
    from cli_push_transaction import execute
    report = preview(source, target)
    if not apply:
        return dict(report, applied=False, dry_run=True)
    if expected_plan != report['plan_id']:
        raise Conflict('Apply requires the exact --plan digest from the reviewed preview.')
    if report['conflicts']:
        raise Conflict('Unproven ownership or ambiguous integration blocks replacement: ' + '; '.join(report['conflicts']))
    if report['unchanged']:
        return dict(report, applied=False, dry_run=False, transaction=None)
    root = Path(report['target']['root'])
    transaction = {'plan_id': report['plan_id'], 'changes': list(report['changes']),
                   'verification': report['verification'], 'publish_paths': [OWNERSHIP, LEDGER]}
    if report['audit_intent']['events']:
        ledger = strict_json(read_safe(root, LEDGER))
        timestamp = now()
        ledger['events'].extend(dict(event, recorded_at=timestamp, plan_id=report['plan_id'])
                                for event in report['audit_intent']['events'])
        transaction['changes'].extend(_changes(root, {LEDGER: canonical(ledger)}))
    changed_paths = {change['path'] for change in transaction['changes']}
    transaction['publish_paths'] = [path for path in transaction['publish_paths'] if path in changed_paths]
    def recheck():
        if preview(source, target)['plan_id'] != report['plan_id']:
            raise Conflict('Inputs changed after preview; review a new plan.')
    outcome = execute(root, transaction, verify_callback=lambda: verify_payload(root, report['verification']),
                      preflight_callback=recheck)
    return dict(report, applied=True, dry_run=False, transaction=outcome)


def recover(target, transaction_id, mode):
    from cli_push_transaction import inspect, recover as restore
    root = Path(target).expanduser().resolve()
    manifest = inspect(root, transaction_id)
    verification = manifest.get('verification') or manifest.get('manifest', {}).get('verification')
    if mode == 'resume' and not verification:
        raise Conflict('Recovery lacks the original verification contract; rollback remains available.')
    result = restore(root, transaction_id, mode=mode,
                     verify_callback=(lambda: verify_payload(root, verification)) if mode == 'resume' else None)
    return {'operation': 'push-replace', 'recovery': result, 'native_runtime': 'NOT_VERIFIED'}


def verify_installed(target):
    from cli_project import inspect
    from cli_push_transaction import assert_idle
    root = Path(target).expanduser().resolve()
    identity = target_identity(root)
    assert_idle(root)
    receipt = load_ownership(root, target=identity)
    if receipt is None:
        raise Conflict('No push-replace ownership receipt; preview first adoption.')
    from cli_push_integrations import integration_problems
    problems = integration_problems(root, root / 'asdg', receipt['clients'], receipt['entries'])
    for entry in receipt['entries']:
        if entry['ownership_kind'] == 'whole_file' and digest(read_safe(root, entry['path'])) != entry['installed_sha256']:
            problems.append('Owned file changed: ' + entry['path'])
    structure = inspect(root, root)
    problems.extend(structure['missing'])
    return {'operation': 'push-replace', 'verified': not problems, 'problems': sorted(set(problems)),
            'clients': receipt['clients'], 'native_runtime': 'NOT_VERIFIED', 'hook_trust': 'NOT_ASSESSED'}


def serializable(report):
    result = copy.deepcopy(report)
    for change in result.get('changes', []):
        after = change.pop('after')
        change.update(after_sha256=digest(after), after_base64=base64.b64encode(after).decode() if after is not None else None)
    return result


def render(report):
    if 'verified' in report:
        return 'ASDG replacement verification: ' + ('PASS' if report['verified'] else '\n'.join(report['problems']))
    if 'recovery' in report:
        return 'ASDG replacement recovery: ' + str(report['recovery'])
    label = 'no changes' if report['unchanged'] else 'applied' if report['applied'] else 'preview'
    lines = ['ASDG push-replace: ' + label, 'Target: ' + report['target']['root'],
             'Source: ' + report['source']['repository'] + ' / ' + report['source']['package_sha256'],
             'Clients: ' + ', '.join(report['clients']), 'Plan: ' + report['plan_id']]
    lines += [f"{_description(c)['action']}: {c['path']}" for c in report['changes']]
    lines += ['CONFLICT: ' + item for item in report['conflicts']]
    lines += ['Native invocation and hook trust were not verified.']
    return '\n'.join(lines)
