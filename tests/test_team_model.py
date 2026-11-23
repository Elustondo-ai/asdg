"""Pure team name, ID and specification rules; no store, claim, CLI or native runtime is exercised."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from cli_files import Conflict
from cli_model import catalogue
from cli_team_model import TEAM_ID, clean_name, find_collision, name_key, new_team_id, validate_spec

ROOT = Path(__file__).resolve().parents[1]
ROLES = {agent['role_id'] for agent in catalogue(ROOT)[0]}
CONTEXT = dict(project_id='client-project', role_ids=ROLES, coordinator='ASDG-COORDINATOR')
SHA = 'a' * 64


def spec(kind='subagents', name='Architecture review'):
    native = kind != 'sessions'
    return {
        'schema_version': 1, 'team_id': 'team-0123456789abcdef', 'revision': 1, 'name': name,
        'project_id': 'client-project', 'type': kind, 'purpose': 'Review the architecture documents.',
        'members': [
            {'slot': 'governance', 'role_id': 'ASDG-COORDINATOR', 'responsibility': 'Coordinate and integrate.'},
            {'slot': 'architecture-security', 'role_id': 'ASDG-05', 'responsibility': 'Security findings.'},
            {'slot': 'architecture-data', 'role_id': 'ASDG-05', 'responsibility': 'Data findings.'}],
        'lead': 'governance' if native else None,
        'rules': {'collaboration': 'Findings return to the lead.', 'outputs': 'One findings note per slot.',
                  'completion': 'Every slot has reported.', 'handoff': 'Record open questions.',
                  'integration_owner': 'governance', 'work': 'read-only'},
        'provenance': {'generator': 'cli.py team', 'asdg_build': '20261114T032930Z-f2b8591',
                       'created_at': '2026-11-14T20:00:00Z',
                       'definitions': [{'path': '.claude/agents/asdg-05.md', 'role_id': 'ASDG-05',
                                        'sha256': SHA, 'template_sha256': SHA}] if native else []}}


def changed(path, value, kind='subagents'):
    """A valid specification with one nested field replaced; `...` deletes the field."""
    result = spec(kind)
    holder = result
    for key in path[:-1]:
        holder = holder[key]
    if value is ...:
        del holder[path[-1]]
    else:
        holder[path[-1]] = value
    return result


class TeamModelTests(unittest.TestCase):
    def test_names_are_data_and_lifecycle_words_are_valid(self):
        self.assertEqual(clean_name('  Architecture   review '), 'Architecture review')
        for name in ('start', 'list', 'status', 'archive', '../../etc/passwd', '$(rm -rf ~); `id` && x', 'Revisión ñ'):
            self.assertEqual(clean_name(name), name)
            self.assertEqual(validate_spec(spec(name=name), **CONTEXT)['name'], name)
        for bad in ('', '   ', 'a\nb', 'a\tb', 'a\x00b', 'a​b', 'a b', 'x' * 81, 42, None, ['start']):
            with self.assertRaises(Conflict, msg=repr(bad)):
                clean_name(bad)

    def test_identity_is_normalized_and_case_insensitive(self):
        same = ('Architecture Review', '  architecture   REVIEW ', 'ＡＲＣＨＩＴＥＣＴＵＲＥ review')
        self.assertEqual(len({name_key(name) for name in same}), 1)
        self.assertEqual(name_key('Straße'), name_key('STRASSE'))
        self.assertNotEqual(name_key('Architecture review'), name_key('Security review'))
        saved = [spec(name='Architecture review')]
        self.assertIs(find_collision('ARCHITECTURE  Review', saved), saved[0])
        self.assertIsNone(find_collision('Security review', saved))

    def test_ids_are_opaque_unique_and_independent_of_names(self):
        first = new_team_id()
        self.assertTrue(TEAM_ID.fullmatch(first))
        many = {new_team_id() for _ in range(300)}
        self.assertEqual(len(many), 300)
        self.assertNotIn(new_team_id(many), many)
        with self.assertRaises(TypeError):
            new_team_id(name='Architecture review')  # There is no way to derive an ID from a name.
        with self.assertRaises(Conflict):
            validate_spec(changed(['team_id'], 'architecture-review'), **CONTEXT)

    def test_valid_specifications_round_trip_without_mutation(self):
        for kind in ('sessions', 'subagents', 'teammates'):
            with self.subTest(kind=kind):
                original = spec(kind)
                before = copy.deepcopy(original)
                checked = validate_spec(original, **CONTEXT)
                self.assertEqual(checked, before)
                self.assertEqual(original, before)
                self.assertIsNot(checked, original)
                self.assertIsNot(checked['members'], original['members'])
                checked['members'][0]['slot'] = 'changed'
                self.assertEqual(original, before)
                again = validate_spec(json.loads(json.dumps(before)), **CONTEXT)
                self.assertEqual(again, before)
                self.assertEqual(checked['type'], kind)
        for stamp in ('2028-02-29T23:59:59Z', '2026-01-01T00:00:00Z'):  # A real leap day and a midnight.
            leap = changed(['provenance', 'created_at'], stamp)
            self.assertEqual(validate_spec(leap, **CONTEXT)['provenance']['created_at'], stamp)
        second = dict(spec('subagents', 'Security review'), team_id='team-fedcba9876543210')
        self.assertEqual(validate_spec(second, **CONTEXT)['type'], 'subagents')  # Two teams, one type.
        sessions = validate_spec(spec('sessions'), **CONTEXT)  # No native dispatch lead, yet an integration owner.
        self.assertEqual((sessions['lead'], sessions['rules']['integration_owner']), (None, 'governance'))
        roles = [member['role_id'] for member in spec()['members']]
        self.assertEqual(roles.count('ASDG-05'), 2)  # Two specialist slots share one role.

    def test_malformed_specifications_are_refused_and_left_unchanged(self):
        definition = ['provenance', 'definitions', 0]
        cases = {
            'not an object': [spec()], 'future version': changed(['schema_version'], 2),
            'text version': changed(['schema_version'], '1'), 'boolean version': changed(['schema_version'], True),
            'float version': changed(['schema_version'], 1.0),
            'missing field': changed(['purpose'], ...), 'extra field': dict(spec(), active=True),
            'bad id': changed(['team_id'], 'team-XYZ'), 'zero revision': changed(['revision'], 0),
            'boolean revision': changed(['revision'], True), 'unsaved name': changed(['name'], ' Architecture review'),
            'other project': changed(['project_id'], 'another'), 'unknown type': changed(['type'], 'swarm'),
            'list type': changed(['type'], ['sessions']),
            'earlier manual type': changed(['type'], 'manual', 'sessions'),
            'earlier delegated type': changed(['type'], 'delegated'),
            'earlier collaborative type': changed(['type'], 'collaborative'),
            'capitalized type': changed(['type'], 'Sessions', 'sessions'), 'empty purpose': changed(['purpose'], ''),
            'multi-line purpose': changed(['purpose'], 'one\ntwo'), 'no members': changed(['members'], []),
            'duplicate slot': changed(['members', 1, 'slot'], 'governance'),
            'uppercase slot': changed(['members', 1, 'slot'], 'Architecture'),
            'path slot': changed(['members', 1, 'slot'], '../architecture'),
            'admin role': changed(['members', 1, 'role_id'], 'ASDG-ADMIN'),
            'list role': changed(['members', 1, 'role_id'], ['ASDG-05']),
            'extra member field': changed(['members', 1, 'tools'], 'Write'),
            'no lead': changed(['lead'], None), 'specialist lead': changed(['lead'], 'architecture-data'),
            'sessions with lead': changed(['lead'], 'governance', 'sessions'),
            'unknown integration owner': changed(['rules', 'integration_owner'], 'nobody'),
            'coding work': changed(['rules', 'work'], 'code'), 'missing rule': changed(['rules', 'handoff'], ...),
            'bad time': changed(['provenance', 'created_at'], '2026-11-14 20:00'),
            'impossible time': changed(['provenance', 'created_at'], '2026-99-99T99:99:99Z'),
            'non-leap day': changed(['provenance', 'created_at'], '2026-02-29T12:00:00Z'),
            'hour 24': changed(['provenance', 'created_at'], '2026-11-14T24:00:00Z'),
            'second 60': changed(['provenance', 'created_at'], '2026-11-14T23:59:60Z'),
            'numeric time': changed(['provenance', 'created_at'], 20261114200000),
            'definitions not a list': changed(['provenance', 'definitions'], {}),
            'path escape': changed(definition + ['path'], '.claude/agents/../settings.json'),
            'unowned path': changed(definition + ['path'], '.claude/agents/other.md'),
            'short hash': changed(definition + ['sha256'], 'abc'),
            'role without member': changed(definition + ['role_id'], 'ASDG-09'),
            'sessions with definitions': changed(['provenance', 'definitions'], spec()['provenance']['definitions'], 'sessions'),
        }
        for label, candidate in cases.items():
            with self.subTest(case=label):
                before = copy.deepcopy(candidate)
                with self.assertRaises(Conflict):
                    validate_spec(candidate, **CONTEXT)
                self.assertEqual(candidate, before)
        with self.assertRaisesRegex(Conflict, 'Unsupported team specification version 2'):
            validate_spec(changed(['schema_version'], 2), **CONTEXT)
        with self.assertRaisesRegex(Conflict, 'Unsupported team specification version 1.0'):
            validate_spec(changed(['schema_version'], 1.0), **CONTEXT)
        for earlier in ('manual', 'delegated', 'collaborative'):
            with self.assertRaisesRegex(Conflict, 'one of: sessions, subagents, teammates'):
                validate_spec(changed(['type'], earlier), **CONTEXT)
        with self.assertRaisesRegex(Conflict, 'real UTC date and time'):
            validate_spec(changed(['provenance', 'created_at'], '2026-99-99T99:99:99Z'), **CONTEXT)
        with self.assertRaises(Conflict):
            validate_spec(spec(), project_id='', role_ids=ROLES, coordinator='ASDG-COORDINATOR')


if __name__ == '__main__':
    unittest.main()
