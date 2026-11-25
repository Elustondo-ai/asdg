"""Fail-closed replacement inventories in disposable Git repositories."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import cli_push_inventory as inventory
from cli_files import Conflict


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else inventory.canonical(data))


def receipt():
    return {
        'schema_version': 1, 'kind': 'asdg-installation-ownership',
        'evidence_status': 'LOCAL_UNAUTHENTICATED_EVIDENCE', 'catalog_schema_version': 2,
        'catalog_sha256': 'a' * 64, 'plan_basis_sha256': 'b' * 64,
        'source': {'repository': inventory.CANONICAL, 'commit': None,
                   'package_sha256': 'c' * 64, 'manifest_sha256': 'd' * 64},
        'target': {'repository': 'github.com/example/project', 'root': '/fixture/client',
                   'git_common_dir': '/fixture/client/.git', 'project_id': 'fixture',
                   'binding_sha256': 'e' * 64},
        'clients': ['codex'],
        'provenance': {'method': 'reviewed_legacy_adoption', 'inventory_basis_sha256': 'f' * 64},
        'entries': [{'entity_id': 'codex-skills', 'client': 'codex',
                     'path': '.agents/skills/asdg-help/SKILL.md', 'ownership_kind': 'whole_file',
                     'installed_sha256': '1' * 64,
                     'generator': {'id': 'codex_skill_adapters', 'version': '1'}}],
    }


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='asdg-push-inventory-')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        git(self.source, 'init', '-q')
        git(self.source, 'remote', 'add', 'origin', 'https://github.com/Elustondo-ai/asdg.git')
        design = ROOT / 'docs/asdg/07-planning'
        for name, old in ((inventory.CATALOG, '02.25-push-replace-catalog.json'),
                          (inventory.SCHEMA, '02.25-push-replace-ownership.schema.json')):
            shipped = ROOT / name
            write(self.source, name, (shipped if shipped.exists() else design / old).read_bytes())
        for name in (inventory.DESCRIPTOR, '00-governance/types/agent-catalog.json',
                     'AGENTS.md', 'scripts/cli.py', 'scripts/hook.py',
                     'skills/asdg-focus/session-policy.md', 'templates/.agents/skills/asdg-focus/SKILL.md'):
            write(self.source, name, (ROOT / name).read_bytes())
        self.names = sorted([p.relative_to(self.source).as_posix() for p in self.source.rglob('*')
                             if p.is_file() and '.git' not in p.relative_to(self.source).parts]
                            + [inventory.INDEX, inventory.MANIFEST])
        self.seal()
        git(self.source, 'add', '.')
        git(self.source, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')

    def seal(self):
        write(self.source, inventory.INDEX, {'schema_version': 1, 'files': self.names})
        write(self.source, inventory.MANIFEST, {
            'schema_version': 1, 'version': '0.3.0-pilot.4',
            'files': {name: inventory.digest((self.source / name).read_bytes())
                      for name in self.names if name != inventory.MANIFEST}})

    def validate(self, value, **kwargs):
        with patch.object(inventory, 'CORE', self.source):
            return inventory.validate_ownership(value, **kwargs)

    def test_source_requires_integrity_and_reports_exact_commit_only(self):
        source = inventory.validated_source(self.source)
        self.assertEqual(source['identity']['commit'], git(self.source, 'rev-parse', 'HEAD'))
        write(self.source, 'AGENTS.md', b'changed methodology')
        with self.assertRaisesRegex(Conflict, 'integrity'):
            inventory.validated_source(self.source)
        self.seal()
        changed = inventory.validated_source(self.source)
        self.assertIsNone(changed['identity']['commit'])
        self.assertNotEqual(source['identity']['package_sha256'], changed['identity']['package_sha256'])

    def test_source_origin_and_root_cannot_be_spoofed_by_descriptor(self):
        git(self.source, 'remote', 'set-url', 'origin', 'https://github.com/example/foreign')
        with self.assertRaisesRegex(Conflict, 'origin'):
            inventory.validated_source(self.source)
        with self.assertRaises(Conflict):
            inventory.validated_source(self.source / 'metadata')

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.subTest(value=value), self.assertRaises(Conflict):
                inventory.strict_json(value)
        self.assertEqual(inventory.canonical({'b': 2, 'a': True}), b'{"a":true,"b":2}')

    def test_reads_reject_links_traversal_and_nested_repositories(self):
        write(self.root, 'original', b'x')
        os.link(self.root / 'original', self.root / 'hardlink')
        (self.root / 'symlink').symlink_to(self.root / 'original')
        write(self.root, 'nested/.git', b'gitdir: elsewhere')
        write(self.root, 'nested/file', b'x')
        for name in ('hardlink', 'symlink', '../original', 'nested/file', 'a//b', '.git/config'):
            with self.subTest(name=name), self.assertRaises(Conflict):
                inventory.read_safe(self.root, name)

    def test_legacy_inventory_preserves_extra_files_and_binds_evidence(self):
        client = self.root / 'client'
        shutil.copytree(self.source, client / 'asdg', ignore=shutil.ignore_patterns('.git'))
        write(client, 'asdg/docs/my-unknown.md', b'keep')
        result = inventory.legacy_distribution_inventory(client, self.source)
        self.assertNotIn('asdg/docs/my-unknown.md', result['paths'])
        self.assertEqual(result['index_sha256'], inventory.digest((client / 'asdg' / inventory.INDEX).read_bytes()))
        value = inventory.strict_json((client / 'asdg' / inventory.INDEX).read_bytes())
        value['files'].append('docs/my-unknown.md')
        write(client, 'asdg/' + inventory.INDEX, value)
        with self.assertRaises(Conflict):
            inventory.legacy_distribution_inventory(client, self.source)

    def test_closed_schema_and_binding_for_both_clients(self):
        value = receipt()
        self.assertEqual(self.validate(value, target=value['target'], clients=['codex']), value)
        for mutate in (lambda v: v.update(timestamp='now'), lambda v: v.update(schema_version=True),
                       lambda v: v['source'].update(repository='github.com/foreign/source'),
                       lambda v: v['entries'][0].update(extra=True)):
            candidate = copy.deepcopy(value)
            mutate(candidate)
            with self.assertRaises(Conflict):
                self.validate(candidate)
        with self.assertRaises(Conflict):
            self.validate(value, target=dict(value['target'], root='/other'))
        with self.assertRaises(Conflict):
            self.validate(value, clients=['claude'])
        value['clients'] = ['claude']
        value['entries'][0].update(entity_id='claude-skills', client='claude', path='.claude/skills/asdg-help/SKILL.md')
        self.validate(value)

    def test_semantic_scope_cannot_claim_preserved_files_or_other_clients(self):
        for path in ('asdg/.env', 'asdg/docs/asdg/notes.md', 'asdg/metadata/build.json',
                     'asdg/metadata/sync-state.json', '.asdg/sprint.json', 'app.py'):
            value = receipt()
            value['entries'][0].update(entity_id='distribution', client='shared', path=path)
            with self.subTest(path=path), self.assertRaises(Conflict):
                self.validate(value)
        value = receipt()
        value['entries'][0]['path'] = '.agents/skills/user-skill/SKILL.md'
        with self.assertRaises(Conflict):
            self.validate(value)
        value = receipt()
        value['entries'].append(copy.deepcopy(value['entries'][0]))
        value['entries'][-1]['installed_sha256'] = '2' * 64
        with self.assertRaises(Conflict):
            self.validate(value)

    def test_owned_values_require_exact_selectors_and_original_hashes(self):
        value = receipt()
        entry = value['entries'][0]
        entry.update(entity_id='codex-config', path='.codex/config.toml', ownership_kind='toml_key',
                     selector={'key_path': ['features', 'hooks']},
                     original={'present': True, 'value': False, 'sha256': inventory.digest(b'false')})
        self.validate(value)
        entry['selector'] = {'key_path': ['permissions', 'trust']}
        with self.assertRaises(Conflict):
            self.validate(value)
        entry['selector'] = {'key_path': ['features', 'hooks']}
        entry['original']['sha256'] = 'f' * 64
        with self.assertRaises(Conflict):
            self.validate(value)

    def test_target_identity_preserves_state_and_rejects_incompatible_binding(self):
        client = self.root / 'client'
        shutil.copytree(self.source, client / 'asdg', ignore=shutil.ignore_patterns('.git'))
        git(client, 'init', '-q')
        git(client, 'remote', 'add', 'origin', 'git@github.com:example/project.git')
        agents = inventory.strict_json((self.source / '00-governance/types/agent-catalog.json').read_bytes())['agents']
        binding = {'schema_version': 1, 'provider': 'elustondo.ai/asdg',
                   'installation_mode': 'embedded-distribution', 'distribution_root': 'asdg',
                   'artifacts_root': 'docs/asdg', 'project_id': 'fixture',
                   'stages': [row['folder'].removeprefix('asdg/') for row in sorted(agents, key=lambda row: row['stage'])]}
        write(client, '.asdg/project.json', binding)
        write(client, '.asdg/sprint.json', {'status': 'inactive', 'sprint_id': None, 'objective': None,
                                         'scope': [], 'acceptance_criteria': []})
        write(client, '.asdg/lifecycle.json', {'schema_version': 1, 'stages': {}, 'project_status': 'new', 'release': None})
        before = {name: (client / name).read_bytes() for name in
                  ('.asdg/project.json', '.asdg/sprint.json', '.asdg/lifecycle.json')}
        result = inventory.target_identity(client)
        self.assertEqual(result['repository'], 'github.com/example/project')
        self.assertEqual(result['binding_sha256'], inventory.digest(before['.asdg/project.json']))
        self.assertEqual(before, {name: (client / name).read_bytes() for name in before})
        binding['stages'][2] = {'malformed': True}
        write(client, '.asdg/project.json', binding)
        with self.assertRaises(Conflict):
            inventory.target_identity(client)


if __name__ == '__main__':
    unittest.main()
