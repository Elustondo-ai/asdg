"""Deterministic, side-effect-free reconciliation of local and remote plans."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts/lib'))
from cli_files import Conflict
from cli_plan_merge import empty_cache, reconcile, validate_cache


def fields(**changes):
    result = {'title': 'A task', 'body': 'Shared description', 'state': 'OPEN',
              'status': 'Todo', 'priority': '', 'team': 'Atlas', 'sprint': 'Sprint 5'}
    result.update(changes)
    return result


def item(identifier='PLAN-001', number=1, **changes):
    result = {'id': identifier, 'issue_number': number, 'fields': fields(),
              'base': fields() if number is not None else None,
              'notes': 'My unshared reasoning notes', 'sources': ['docs/asdg/07-planning/03-plan.md']}
    result.update(changes)
    return result


def cache(*items):
    result = empty_cache('example/project', number=7)
    result['items'] = list(items)
    return result


def remote(identifier='PLAN-001', number=1, **changes):
    result = {'id': identifier, 'issue_number': number, 'fields': fields(),
              'item_id': 'PVTI_' + str(number), 'node_id': 'I_' + str(number),
              'updated_at': '2026-11-24T00:00:00Z',
              'url': 'https://github.com/example/project/issues/' + str(number)}
    result.update(changes)
    return result


def snapshot(*issues):
    return {'repository': 'example/project', 'project': {
        'id': 'PVT_7', 'number': 7, 'title': 'ASDG Plan — example/project',
        'url': 'https://github.com/orgs/example/projects/7', 'owner': 'example'},
        'issues': list(issues)}


class MergeTests(unittest.TestCase):
    def test_defaults_and_independent_validation_copy(self):
        fresh = empty_cache('example/project')
        self.assertEqual(fresh['project'], {'owner': 'example', 'number': None,
                                           'title': 'ASDG Plan — example/project'})
        local = cache(item())
        result = validate_cache(local)
        result['items'][0]['fields']['title'] = 'Changed copy'
        self.assertEqual(local['items'][0]['fields']['title'], 'A task')

    def test_noop_does_not_mutate_inputs(self):
        local, server = cache(item()), snapshot(remote())
        before = deepcopy((local, server))
        result = reconcile(local, server)
        self.assertEqual(result, {'cache': local, 'operations': [], 'conflicts': [], 'imports': []})
        self.assertEqual((local, server), before)

    def test_local_changes_export_only_changed_fields(self):
        local = cache(item(fields=fields(title='Renamed', priority='High')))
        result = reconcile(local, snapshot(remote()))
        self.assertFalse(result['conflicts'])
        self.assertEqual(result['operations'], [
            {'kind': 'update_issue', 'id': 'PLAN-001', 'issue_number': 1, 'fields': {'title': 'Renamed'}},
            {'kind': 'update_fields', 'id': 'PLAN-001', 'issue_number': 1, 'fields': {'priority': 'High'}},
        ])
        self.assertEqual(result['cache']['items'][0]['base'], local['items'][0]['fields'])

    def test_remote_changes_pull_and_keep_local_annotations(self):
        local = cache(item())
        result = reconcile(local, snapshot(remote(fields=fields(title='Server edit', team='Orion'))))
        self.assertFalse(result['operations'])
        self.assertFalse(result['conflicts'])
        merged = result['cache']['items'][0]
        self.assertEqual(merged['fields']['title'], 'Server edit')
        self.assertEqual(merged['base'], merged['fields'])
        self.assertEqual(merged['notes'], local['items'][0]['notes'])
        self.assertEqual(merged['sources'], local['items'][0]['sources'])

    def test_disjoint_changes_merge(self):
        local = cache(item(fields=fields(title='Local title')))
        result = reconcile(local, snapshot(remote(fields=fields(priority='High'))))
        self.assertEqual(result['cache']['items'][0]['fields'], fields(title='Local title', priority='High'))
        self.assertEqual(result['operations'][0]['fields'], {'title': 'Local title'})
        self.assertEqual(len(result['operations']), 1)

    def test_same_change_converges_without_write(self):
        result = reconcile(cache(item(fields=fields(title='Same'))), snapshot(remote(fields=fields(title='Same'))))
        self.assertFalse(result['conflicts'])
        self.assertFalse(result['operations'])
        self.assertEqual(result['cache']['items'][0]['base']['title'], 'Same')

    def test_conflicting_field_preserves_whole_item(self):
        local = cache(item(fields=fields(title='Local title', body='Local body')))
        result = reconcile(local, snapshot(remote(fields=fields(title='Remote title'))))
        self.assertEqual(result['conflicts'], [{'id': 'PLAN-001', 'kind': 'field_conflict', 'field': 'title',
                                              'base': 'A task', 'local': 'Local title', 'remote': 'Remote title'}])
        self.assertFalse(result['operations'])
        self.assertEqual(result['cache']['items'], local['items'])

    def test_missing_bound_issue_is_not_recreated(self):
        result = reconcile(cache(item()), snapshot())
        self.assertEqual(result['conflicts'][0]['kind'], 'missing_bound_issue')
        self.assertFalse(result['operations'])

    def test_new_issue_creation_excludes_notes_and_sources(self):
        result = reconcile(cache(item(number=None)), snapshot())
        self.assertEqual([op['kind'] for op in result['operations']], ['create_issue', 'add_item', 'update_fields'])
        self.assertEqual(result['operations'][0]['fields'], {'title': 'A task', 'body': 'Shared description', 'state': 'OPEN'})
        self.assertEqual(result['operations'][2]['fields'], {'status': 'Todo', 'team': 'Atlas', 'sprint': 'Sprint 5'})
        self.assertIsNone(result['cache']['items'][0]['base'])
        self.assertFalse(result['conflicts'])

    def test_new_issue_empty_project_fields_need_no_update(self):
        new = item(number=None, fields=fields(status='', team='', sprint=''))
        result = reconcile(cache(new), snapshot())
        self.assertEqual([op['kind'] for op in result['operations']], ['create_issue', 'add_item'])

    def test_closed_new_issue_requires_create_then_bound_state_update(self):
        local = cache(item(number=None, fields=fields(state='CLOSED')))
        first = reconcile(local, snapshot())
        self.assertEqual(first['operations'][0]['fields']['state'], 'OPEN')
        observed = remote(item_id=None, fields=fields(status='', team='', sprint=''))
        # The caller records a provisional baseline only after its journalled
        # create mutation succeeds and the newly created issue is read back.
        local['items'][0]['issue_number'] = observed['issue_number']
        local['items'][0]['base'] = deepcopy(observed['fields'])
        next_plan = reconcile(local, snapshot(observed))
        self.assertFalse(next_plan['conflicts'])
        self.assertEqual(next_plan['operations'][0]['fields'], {'state': 'CLOSED'})

    def test_known_creation_baseline_survives_individual_project_updates(self):
        original = item(number=None)
        created = remote(item_id=None, fields=fields(status='', priority='', team='', sprint=''))
        original['issue_number'] = created['issue_number']
        original['base'] = deepcopy(created['fields'])
        for key in ('status', 'team', 'sprint'):
            created['item_id'] = 'PVTI_1'
            created['fields'][key] = original['fields'][key]
            result = reconcile(cache(original), snapshot(created))
            self.assertFalse(result['conflicts'])
        self.assertFalse(result['operations'])

    def test_new_issue_can_bind_after_readback_and_become_noop(self):
        local = cache(item(number=None))
        result = reconcile(local, snapshot(remote()))
        self.assertFalse(result['conflicts'])
        self.assertFalse(result['operations'])
        self.assertEqual(result['cache']['items'][0]['issue_number'], 1)
        self.assertEqual(reconcile(result['cache'], snapshot(remote()))['operations'], [])

    def test_interrupted_issue_create_adopts_only_identical_issue_fields(self):
        server = snapshot(remote(item_id=None, fields=fields(status='', priority='', team='', sprint='')))
        result = reconcile(cache(item(number=None)), server)
        self.assertFalse(result['conflicts'])
        self.assertEqual([op['kind'] for op in result['operations']], ['add_item', 'update_fields'])
        server['issues'][0]['fields']['title'] = 'Someone changed it'
        blocked = reconcile(cache(item(number=None)), server)
        self.assertEqual(blocked['conflicts'][0]['kind'], 'unbased_field_conflict')
        self.assertFalse(blocked['operations'])

    def test_unbased_remote_collision_does_not_overwrite_project_field(self):
        local = cache(item(number=None))
        result = reconcile(local, snapshot(remote(fields=fields(team='Orion'))))
        self.assertEqual(result['conflicts'][0]['kind'], 'unbased_field_conflict')
        self.assertEqual(result['conflicts'][0]['field'], 'team')
        self.assertFalse(result['operations'])
        self.assertEqual(result['cache']['items'], local['items'])

    def test_import_all_remote_issues_and_ensure_project_membership(self):
        server = snapshot(remote('github:3', 3), remote('github:2', 2, item_id=None))
        result = reconcile(cache(), server)
        self.assertEqual(result['imports'], ['github:2', 'github:3'])
        self.assertEqual(result['operations'], [{'kind': 'add_item', 'id': 'github:2', 'issue_number': 2}])
        self.assertEqual(result['cache']['items'][0]['notes'], '')
        self.assertEqual(result['cache']['items'][0]['sources'], [])
        server['issues'][1]['item_id'] = 'PVTI_2'
        self.assertFalse(reconcile(result['cache'], server)['operations'])

    def test_remote_only_issue_does_not_remove_local_item(self):
        result = reconcile(cache(item()), snapshot(remote(), remote('github:4', 4)))
        self.assertEqual(len(result['cache']['items']), 2)
        self.assertEqual(result['imports'], ['github:4'])

    def test_status_is_independent_of_issue_state(self):
        result = reconcile(cache(item(fields=fields(status='Done'))), snapshot(remote()))
        self.assertEqual(result['operations'][0]['fields'], {'status': 'Done'})
        self.assertEqual(result['cache']['items'][0]['fields']['state'], 'OPEN')

    def test_cleared_field_is_an_explicit_empty_update(self):
        result = reconcile(cache(item(fields=fields(team=''))), snapshot(remote()))
        self.assertEqual(result['operations'][0]['fields'], {'team': ''})

    def test_identity_change_does_not_rebind(self):
        result = reconcile(cache(item()), snapshot(remote('another-id')))
        self.assertEqual(result['conflicts'][0]['kind'], 'issue_identity_changed')
        self.assertEqual(len(result['cache']['items']), 1)
        self.assertFalse(result['operations'])

    def test_marker_moved_to_another_issue_is_conflict(self):
        result = reconcile(cache(item()), snapshot(remote('github:1', 1), remote('PLAN-001', 2)))
        self.assertTrue(result['conflicts'])
        self.assertFalse(result['operations'])
        self.assertEqual(len(result['cache']['items']), 1)

    def test_project_binding_is_observed_not_inferred_from_branch(self):
        local = empty_cache('example/project')
        result = reconcile(local, snapshot())
        self.assertEqual(result['cache']['project']['number'], 7)
        self.assertFalse(result['conflicts'])
        missing = snapshot()
        missing['project'] = None
        self.assertEqual(reconcile(cache(), missing)['conflicts'][0]['kind'], 'missing_bound_project')
        self.assertFalse(reconcile(local, missing)['conflicts'])
        changed = snapshot()
        changed['project']['number'] = 9
        self.assertEqual(reconcile(cache(), changed)['conflicts'][0]['kind'], 'project_identity_changed')

    def test_order_is_independent_of_input_item_order(self):
        a = item('A', 1, fields=fields(priority='High'))
        z = item('Z', 2, fields=fields(title='Local title'))
        first = reconcile(cache(z, a), snapshot(remote('Z', 2), remote('A', 1), remote('github:8', 8)))
        second = reconcile(cache(a, z), snapshot(remote('github:8', 8), remote('A', 1), remote('Z', 2)))
        self.assertEqual(first, second)

    def test_repository_comparison_accepts_case_only_difference(self):
        server = snapshot(remote())
        server['repository'] = 'Example/Project'
        self.assertFalse(reconcile(cache(item()), server)['conflicts'])


class ValidationTests(unittest.TestCase):
    def test_schema_rejects_unexpected_keys_and_missing_fields(self):
        cases = []
        for path, value in [((), {'extra': 'no'}), (('project',), {'extra': 'no'}),
                            (('items', 0), {'extra': 'no'}), (('items', 0, 'fields'), {'extra': 'no'})]:
            case = cache(item())
            target = case
            for key in path:
                target = target[key]
            target.update(value)
            cases.append(case)
        case = cache(item())
        del case['items'][0]['fields']['body']
        cases.append(case)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(Conflict):
                validate_cache(case)

    def test_schema_rejects_malformed_values(self):
        cases = [cache(item(id='bad --> id')), cache(item(issue_number=True)),
                 cache(item('github:4', 3)), cache(item(fields=fields(state='in-progress'))),
                 cache(item(fields=fields(title='  '))), cache(item(fields=fields(body='bad\x00text'))),
                 cache(item(notes=3)), cache(item(sources=['ok', 4])), cache(item(number=None, base=fields()))]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(Conflict):
                validate_cache(case)
        for repo in ['https://github.com/a/b', '../a', 'a/b/c', None]:
            with self.subTest(repo=repo), self.assertRaises(Conflict):
                empty_cache(repo)

    def test_duplicate_local_and_remote_identities_fail(self):
        for local in [cache(item(), item()), cache(item(), item('other', 1))]:
            with self.assertRaises(Conflict):
                validate_cache(local)
        for server in [snapshot(remote(), remote()), snapshot(remote(), remote('other', 1)),
                       snapshot(remote(), remote('PLAN-001', 2))]:
            with self.assertRaises(Conflict):
                reconcile(cache(), server)

    def test_remote_repository_and_partial_snapshots_fail(self):
        server = snapshot()
        server['repository'] = 'another/project'
        with self.assertRaises(Conflict):
            reconcile(cache(), server)
        for server in [{}, snapshot({'id': 'bad'}), snapshot(remote(fields={}))]:
            with self.assertRaises(Conflict):
                reconcile(cache(), server)

    def test_valid_input_not_changed_when_remote_validation_fails(self):
        local = cache(item())
        before = deepcopy(local)
        with self.assertRaises(Conflict):
            reconcile(local, snapshot(remote(), remote()))
        self.assertEqual(local, before)


if __name__ == '__main__':
    unittest.main()
