"""Source-only design contract tests; these never perform client replacement."""
import copy
import json
from pathlib import Path
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'docs/asdg/07-planning'
CATALOG = DESIGN / '02.25-push-replace-catalog.json'
SCHEMA = DESIGN / '02.25-push-replace-ownership.schema.json'


def receipt(client):
    """Synthetic identity and one exact adapter; never copied into a real client."""
    folder = '.agents' if client == 'codex' else '.claude'
    return {
        'schema_version': 1, 'kind': 'asdg-installation-ownership',
        'evidence_status': 'LOCAL_UNAUTHENTICATED_EVIDENCE',
        'catalog_schema_version': 2, 'catalog_sha256': 'a' * 64,
        'plan_basis_sha256': 'b' * 64,
        'source': {'repository': 'github.com/Elustondo-ai/asdg', 'commit': None,
                   'package_sha256': 'c' * 64, 'manifest_sha256': 'd' * 64},
        'target': {'repository': 'github.com/example/client', 'root': '/fixture/client',
                   'git_common_dir': '/fixture/client/.git', 'project_id': 'fixture',
                   'binding_sha256': 'e' * 64},
        'clients': [client],
        'provenance': {'method': 'reviewed_legacy_adoption', 'inventory_basis_sha256': 'f' * 64},
        'entries': [{'entity_id': client + '-skills', 'client': client,
                     'path': folder + '/skills/asdg-help/SKILL.md',
                     'ownership_kind': 'whole_file', 'installed_sha256': '1' * 64,
                     'generator': {'id': client + '_skill_adapters', 'version': '1'}}],
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text())
        self.entities = {entry['id']: entry for entry in self.catalog['entities']}

    def test_resolvers_are_explicit_and_ids_unique(self):
        self.assertEqual(len(self.entities), len(self.catalog['entities']))
        for entry in self.entities.values():
            resolver = entry['scope'].get('resolver')
            if resolver:
                self.assertIn(resolver, self.catalog['resolvers'])

    def test_retired_adapters_have_symmetric_cleanup(self):
        for name in ('codex-skills', 'codex-roles', 'claude-skills', 'claude-mods'):
            self.assertEqual(self.entities[name]['obsolete'], 'remove_previously_owned', name)

    def test_preserved_runtime_state_is_explicit(self):
        paths = {path: entity for entity in self.entities.values()
                 for path in entity['scope'].get('paths', [])}
        for path in ('.asdg/cache/teams/spec-writes', '.claude/worktrees'):
            self.assertIn(path, paths)
            self.assertNotEqual(paths[path]['replacement'], 'replace_owned')
        self.assertTrue(any(e['scope']['anchor'] == 'git_common_dir'
                            for e in self.entities.values()))
        self.assertTrue(any(e['scope'].get('resolver') == 'configured_host_identity'
                            for e in self.entities.values()))


@unittest.skipUnless(Draft202012Validator, 'source-only schema tests require jsonschema')
class OwnershipSchemaTests(unittest.TestCase):
    def setUp(self):
        schema = json.loads(SCHEMA.read_text())
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema)

    def test_claude_and_codex_receipts_validate(self):
        for client in ('claude', 'codex'):
            with self.subTest(client=client):
                self.validator.validate(receipt(client))

    def test_shared_setting_requires_original_and_exact_selector(self):
        value = receipt('codex')
        entry = value['entries'][0]
        entry.update(entity_id='codex-config', path='.codex/config.toml',
                     ownership_kind='toml_key', selector={'key_path': ['features', 'hooks']},
                     original={'present': False})
        self.validator.validate(value)
        del entry['original']
        self.assertFalse(self.validator.is_valid(value))

    def test_unsafe_write_paths_are_rejected_for_both_clients(self):
        for client in ('claude', 'codex'):
            for path in ('../outside', '/absolute', 'C:/outside', 'asdg/*', './asdg/x',
                         'asdg//x', 'asdg/../x', 'asdg/x/', '.git/config', 'a\\b', 'a\nb'):
                with self.subTest(client=client, path=path):
                    value = receipt(client)
                    value['entries'][0]['path'] = path
                    self.assertFalse(self.validator.is_valid(value))

    def test_clients_and_ownership_kinds_cannot_be_relabelled(self):
        for client in ('claude', 'codex'):
            value = receipt(client)
            value['entries'][0]['client'] = 'codex' if client == 'claude' else 'claude'
            self.assertFalse(self.validator.is_valid(value))
        value = receipt('codex')
        value['entries'][0].update(entity_id='codex-config', path='.codex/config.toml')
        self.assertFalse(self.validator.is_valid(value))

    def test_clock_and_final_token_cannot_enter_ownership_payload(self):
        for key in ('timestamp', 'recorded_at', 'plan_id', 'human_approval'):
            value = receipt('codex')
            value[key] = 'unapproved-extra-field'
            self.assertFalse(self.validator.is_valid(value), key)

    def test_unknown_versions_duplicate_entries_and_invalid_hashes_fail(self):
        value = receipt('claude')
        value['schema_version'] = 99
        self.assertFalse(self.validator.is_valid(value))
        value = receipt('claude')
        value['entries'].append(copy.deepcopy(value['entries'][0]))
        self.assertFalse(self.validator.is_valid(value))
        value = receipt('claude')
        value['entries'][0]['installed_sha256'] = 'not-a-hash'
        self.assertFalse(self.validator.is_valid(value))


if __name__ == '__main__':
    unittest.main()
