"""Portable ownership-bound integration replacement; no live clients or native hooks."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import cli_push_integrations as subject
from cli_clients import claude_files, integrations_bytes
from cli_project import BRIDGE, IGNORE, LEGACY_BRIDGES, client_report, template_files
from cli_push_inventory import _entry_scope
from distribution_files import package_files


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_temp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.source_temp.name)
        cls.source = cls.repo / 'asdg'
        names = []
        for source in package_files(ROOT):
            name = source.relative_to(ROOT).as_posix()
            if name.startswith(('templates/', 'mods/')):
                dest = cls.source / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                names.append(name)
        names += ['metadata/package-files.json', 'metadata/MANIFEST.json']
        (cls.source / 'metadata').mkdir()
        (cls.source / 'metadata/package-files.json').write_text(json.dumps({'schema_version': 1, 'files': sorted(names)}))
        (cls.source / 'metadata/MANIFEST.json').write_text(json.dumps({'files': {
            name: subject.digest((cls.source / name).read_bytes()) for name in names if name != 'metadata/MANIFEST.json'}}))

    @classmethod
    def tearDownClass(cls):
        cls.source_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def write(self, name, raw):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw if isinstance(raw, bytes) else raw.encode())
        return target

    def plan(self, clients=('codex', 'claude'), prior=()):
        return subject.integration_plan(self.root, self.source, list(clients), list(prior))

    def apply(self, plan):
        self.assertEqual(plan['conflicts'], [])
        for name, data in plan['desired'].items():
            if data is None:
                (self.root / name).unlink(missing_ok=True)
            else:
                self.write(name, data)

    def test_render_matches_existing_canonical_adapters_and_mods(self):
        result = self.plan()
        self.assertFalse(result['conflicts'])
        for path, data in [*template_files(self.repo), *claude_files(self.repo)]:
            self.assertEqual(result['desired'][path.as_posix()], data, path)
        for entry in result['entries']:
            _entry_scope(entry)

    def test_each_selection_is_pure_and_repeat_is_exact_noop(self):
        for clients in [('codex',), ('claude',), ('codex', 'claude')]:
            with self.subTest(clients=clients), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first = subject.integration_plan(root, self.source, list(clients), [])
                self.assertEqual(list(root.iterdir()), [])
                self.assertEqual(first['conflicts'], [])
                for name, data in first['desired'].items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                second = subject.integration_plan(root, self.source, list(clients), first['entries'])
                self.assertEqual(first['desired'], second['desired'])
                self.assertEqual(first['entries'], second['entries'])
                self.assertEqual(subject.integration_problems(root, self.source, list(clients)), [])

    def test_unindexed_source_skill_never_appears_in_plan(self):
        extra = self.source / 'templates/.agents/skills/asdg-unlisted/SKILL.md'
        extra.parent.mkdir(parents=True)
        extra.write_text('not selected')
        try:
            self.assertFalse(any('asdg-unlisted' in name for name in self.plan()['desired']))
        finally:
            extra.unlink()
            extra.parent.rmdir()

    def test_unknown_adapter_collision_blocks_but_prior_owned_edit_replaces(self):
        first = self.plan()
        self.apply(first)
        name = next(name for name in first['desired'] if name.startswith('.agents/skills/'))
        self.write(name, b'locally edited')
        self.assertTrue(any(name in problem for problem in self.plan()['conflicts']))
        second = self.plan(prior=first['entries'])
        self.assertFalse(second['conflicts'])
        self.assertEqual(second['desired'][name], first['desired'][name])

    def test_intact_installed_old_template_is_candidate_evidence(self):
        shutil.copytree(self.source, self.root / 'asdg')
        name = next(name for name in self.plan()['desired'] if name.startswith('.agents/skills/'))
        template = self.root / 'asdg/templates' / name
        template.write_bytes(template.read_bytes() + b'\nOld version\n')
        manifest_path = self.root / 'asdg/metadata/MANIFEST.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['templates/' + name] = subject.digest(template.read_bytes())
        manifest_path.write_text(json.dumps(manifest))
        self.write(name, template.read_bytes())
        self.assertFalse(self.plan()['conflicts'])
        template.write_bytes(template.read_bytes() + b'unknown drift')
        self.assertTrue(self.plan()['conflicts'])

    def test_only_exact_prior_retired_files_are_deleted(self):
        first = self.plan()
        self.apply(first)
        for client, prefix in [('codex', '.agents'), ('claude', '.claude')]:
            name = prefix + '/skills/asdg-retired/SKILL.md'
            self.write(name, b'old owned skill')
            first['entries'].append(subject._entry(client + '-skills', client, name, 'whole_file', b'old owned skill'))
        unknown = self.write('.claude/skills/asdg-retired/notes.md', b'user notes')
        result = self.plan(prior=first['entries'])
        self.assertFalse(result['conflicts'])
        self.assertIsNone(result['desired']['.agents/skills/asdg-retired/SKILL.md'])
        self.assertIsNone(result['desired']['.claude/skills/asdg-retired/SKILL.md'])
        self.assertNotIn('.claude/skills/asdg-retired/notes.md', result['desired'])
        self.assertEqual(unknown.read_bytes(), b'user notes')

    def test_moved_bootstrap_and_ignore_keep_exact_unowned_bytes(self):
        before, after = b'# Project instructions\r\n\r\n', b'\nKeep this trailing space  \n'
        self.write('AGENTS.md', before + BRIDGE.encode() + after)
        self.write('.gitignore', b'user-rule\r\n' + IGNORE.encode() + b'# End user  \n')
        result = self.plan()
        self.assertEqual(result['desired']['AGENTS.md'], BRIDGE.encode() + before + after)
        self.assertEqual(result['desired']['.gitignore'], (self.root / '.gitignore').read_bytes())
        self.assertFalse(result['conflicts'])

    def test_exact_legacy_bootstrap_is_replaced_without_trimming_user_text(self):
        self.write('AGENTS.md', 'User text\n\n' + LEGACY_BRIDGES[0] + '\nTail\n')
        result = self.plan()
        self.assertFalse(result['conflicts'])
        self.assertEqual(result['desired']['AGENTS.md'], (BRIDGE + 'User text\n\n\nTail\n').encode())

    def test_duplicate_inline_and_missing_owned_markers_block(self):
        for raw in [BRIDGE + BRIDGE, 'prefix ' + BRIDGE, BRIDGE.replace(subject.END, ''),
                    '<!-- ASDG:BEGIN unknown -->\nUnknown policy\n<!-- ASDG:END unknown -->\n']:
            with self.subTest(raw=raw):
                self.write('AGENTS.md', raw)
                self.assertTrue(self.plan()['conflicts'])
        first = self.plan(clients=('claude',))
        self.write('AGENTS.md', BRIDGE)
        first = self.plan(clients=('claude',))
        self.write('AGENTS.md', 'user removed managed block\n')
        self.assertTrue(self.plan(clients=('claude',), prior=first['entries'])['conflicts'])

    def test_existing_user_claude_import_is_never_claimed_or_changed(self):
        for name, content in [('CLAUDE.md', '# User\n@./AGENTS.md\n'),
                              ('.claude/CLAUDE.md', '# User\n@../AGENTS.md\n')]:
            with self.subTest(name=name):
                for candidate in ('CLAUDE.md', '.claude/CLAUDE.md'):
                    (self.root / candidate).unlink(missing_ok=True)
                self.write(name, content)
                result = self.plan(clients=('claude',))
                self.assertNotIn(name, result['desired'])
                self.assertFalse(any(e['entity_id'] == 'claude-bridge' for e in result['entries']))
                self.assertEqual((self.root / name).read_text(), content)

    def test_changed_claude_bridge_destination_does_not_lose_prior_ownership(self):
        self.write('.claude/CLAUDE.md', '# Existing project instructions\n')
        first = self.plan(clients=('claude',))
        self.apply(first)
        original = (self.root / '.claude/CLAUDE.md').read_bytes()
        self.write('CLAUDE.md', '# New root instructions\n')
        result = self.plan(clients=('claude',), prior=first['entries'])
        self.assertTrue(any('bridge destination changed' in problem for problem in result['conflicts']))
        self.assertEqual((self.root / '.claude/CLAUDE.md').read_bytes(), original)

    def test_toml_unrelated_keys_comments_and_formatting_are_preserved(self):
        raw = b'# User config\r\nmodel = "test"\r\n[features] # Keep this\r\nhooks = true # User comment\r\nother = false\r\n'
        self.write('.codex/config.toml', raw)
        first = self.plan()
        self.assertFalse(first['conflicts'])
        self.assertEqual(first['desired']['.codex/config.toml'], raw)
        self.apply(first)
        changed = raw.replace(b'hooks = true', b'hooks = false')
        self.write('.codex/config.toml', changed)
        second = self.plan(prior=first['entries'])
        self.assertFalse(second['conflicts'])
        self.assertEqual(second['desired']['.codex/config.toml'], raw)
        self.assertEqual(subject.integration_problems(self.root, self.source, ['codex'], first['entries']),
                         ['.codex/config.toml: ASDG-owned integration needs reconciliation'])

    def test_toml_dotted_key_and_missing_key_preserve_unrelated_values(self):
        for raw in [b'features.hooks = false # keep\nmodel = "test"\n', b'[features]\nother = false\n']:
            with self.subTest(raw=raw):
                prior = [subject._entry('codex-config', 'codex', '.codex/config.toml', 'toml_key', b'true',
                                        {'key_path': ['features', 'hooks']})]
                self.write('.codex/config.toml', raw)
                result = self.plan(prior=prior)
                self.assertFalse(result['conflicts'])
                self.assertIn(b'hooks = true', result['desired']['.codex/config.toml'])
                self.assertIn(b'# keep' if b'# keep' in raw else b'other = false', result['desired']['.codex/config.toml'])

    def test_unknown_false_invalid_toml_and_missing_parser_fail_closed(self):
        for raw in ['[features]\nhooks = false\n', '[features]\nhooks = "true"\n', '[features\n']:
            self.write('.codex/config.toml', raw)
            self.assertTrue(self.plan()['conflicts'])
        with patch.object(subject, 'tomllib', None):
            self.assertTrue(any('UNSUPPORTED_TOML' in message for message in self.plan()['conflicts']))
            self.assertFalse(self.plan(clients=('claude',))['conflicts'])

    def test_unrelated_hook_registrations_and_metadata_survive(self):
        user = {'matcher': 'Write', 'hooks': [{'type': 'command', 'command': 'echo user'}]}
        self.write('.codex/hooks.json', json.dumps({'description': 'User description', 'custom': [1, 2],
                                                   'hooks': {'PreToolUse': [user], 'Stop': [user]}}))
        first = self.plan()
        self.apply(first)
        value = json.loads(first['desired']['.codex/hooks.json'])
        self.assertEqual(value['hooks']['PreToolUse'][0], user)
        self.assertEqual(value['hooks']['Stop'], [user])
        self.assertEqual(value['description'], 'User description')
        self.assertEqual(value['custom'], [1, 2])
        pretty = json.dumps(value, indent=4).encode()
        self.write('.codex/hooks.json', pretty)
        second = self.plan(prior=first['entries'])
        self.assertEqual(second['desired']['.codex/hooks.json'], pretty)
        self.assertEqual(subject.integration_problems(self.root, self.source, ['codex'], first['entries']), [])

    def test_changed_missing_and_duplicate_owned_hooks_are_conflicts(self):
        first = self.plan()
        self.apply(first)
        initial = json.loads(first['desired']['.codex/hooks.json'])
        for mode in ('changed', 'missing', 'duplicate'):
            value = copy.deepcopy(initial)
            items = value['hooks']['PreToolUse']
            if mode == 'changed':
                items[0]['hooks'][0]['command'] = 'unknown command'
            elif mode == 'missing':
                items.clear()
            else:
                items.append(copy.deepcopy(items[0]))
            self.write('.codex/hooks.json', json.dumps(value))
            self.assertTrue(self.plan(prior=first['entries'])['conflicts'], mode)

    def test_unowned_changed_or_moved_asdg_hooks_never_gain_duplicates(self):
        first = self.plan()
        self.apply(first)
        initial = json.loads(first['desired']['.codex/hooks.json'])
        for mode in ('timeout', 'matcher', 'command', 'wrong-event'):
            with self.subTest(mode=mode):
                value = copy.deepcopy(initial)
                item = value['hooks']['PreToolUse'][0]
                if mode == 'timeout':
                    item['hooks'][0]['timeout'] = 20
                elif mode == 'matcher':
                    item['matcher'] = 'Write'
                elif mode == 'command':
                    item['hooks'][0]['command'] += ' --unknown'
                else:
                    value['hooks']['Stop'] = [value['hooks']['PreToolUse'].pop()]
                raw = json.dumps(value).encode()
                self.write('.codex/hooks.json', raw)
                result = self.plan()
                self.assertTrue(any('ASDG-like hook' in problem for problem in result['conflicts']))
                self.assertNotIn('.codex/hooks.json', result['desired'])
                self.assertEqual((self.root / '.codex/hooks.json').read_bytes(), raw)

    def test_duplicate_json_keys_and_linked_targets_block(self):
        self.write('.codex/hooks.json', '{"hooks": {}, "hooks": {}}')
        self.assertTrue(self.plan()['conflicts'])
        (self.root / '.codex/hooks.json').unlink()
        outside = self.write('outside.txt', b'private')
        (self.root / 'AGENTS.md').symlink_to(outside)
        self.assertTrue(self.plan()['conflicts'])
        (self.root / 'AGENTS.md').unlink()
        os.link(outside, self.root / 'AGENTS.md')
        self.assertTrue(self.plan()['conflicts'])
        self.assertEqual(outside.read_bytes(), b'private')

    def test_client_report_uses_validated_bound_ownership_for_shared_settings(self):
        first = self.plan()
        self.apply(first)
        self.write('.asdg/integrations.json', integrations_bytes({name: {'recorded_from': 'test'} for name in ('codex', 'claude')}))
        self.write('.asdg/installation-ownership.json', '{}')
        self.write('.codex/config.toml', '[features]\nhooks = true\nother = false\n')
        with patch('cli_push_inventory.target_identity', return_value={'fixture': 'identity'}), \
                patch('cli_push_inventory.load_ownership', return_value={'entries': first['entries']}) as loader:
            report, problems = client_report(self.root, self.repo, True)
            loader.assert_called_once_with(self.root, target={'fixture': 'identity'}, clients=['claude', 'codex'])
        self.assertEqual(problems, [])
        self.assertEqual({row['status'] for row in report.values()}, {'COMPLETE'})
        self.assertEqual({row['runtime'] for row in report.values()}, {'NOT_VERIFIED'})
        with patch('cli_push_inventory.target_identity', side_effect=ValueError('Invalid ownership binding')):
            report, problems = client_report(self.root, self.repo, True)
        self.assertEqual({row['status'] for row in report.values()}, {'DAMAGED'})
        self.assertIn('Invalid ownership binding', problems)

    def test_client_report_without_receipt_keeps_old_exact_checks(self):
        first = self.plan()
        self.apply(first)
        self.write('.asdg/integrations.json', integrations_bytes({'codex': {'recorded_from': 'test'}}))
        self.write('.codex/config.toml', '[features]\nhooks = true\nother = false\n')
        report, problems = client_report(self.root, self.repo, True)
        self.assertEqual(report['codex']['status'], 'DAMAGED')
        self.assertEqual(report['claude']['status'], 'NOT_SELECTED')
        self.assertTrue(problems)

    def test_unfinished_transaction_blocks_status_before_and_after_ownership_publication(self):
        first = self.plan()
        self.apply(first)
        self.write('.asdg/integrations.json', integrations_bytes({'codex': {'recorded_from': 'test'}}))
        (self.root / '.asdg/backups/push-replace').mkdir(parents=True)
        for has_receipt in (False, True):
            with self.subTest(has_receipt=has_receipt):
                if has_receipt:
                    self.write('.asdg/installation-ownership.json', '{}')
                with patch('cli_push_transaction.assert_idle', side_effect=subject.Conflict('Unfinished transaction; recover first')) as idle, \
                        patch('cli_push_inventory.load_ownership') as loader:
                    report, problems = client_report(self.root, self.repo, True)
                idle.assert_called_once_with(self.root)
                loader.assert_not_called()
                self.assertEqual(report['codex']['status'], 'DAMAGED')
                self.assertEqual(report['codex']['runtime'], 'NOT_VERIFIED')
                self.assertIn('Unfinished transaction; recover first', problems)


if __name__ == '__main__':
    unittest.main()
