"""GitHub planner adapter protocol tests without external side effects."""
import copy
import io
import json
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts/lib'))
from cli_files import Conflict
from cli_plan_github import GitHub, GitHubRejected, FIELD_NAMES, split_marker, marked_body, validate_fields


def connection(nodes, cursor=None):
    return {'nodes': nodes, 'pageInfo': {'hasNextPage': cursor is not None, 'endCursor': cursor}}


def issue(number=1, body='Description'):
    return {'number': number, 'node_id': 'I_' + str(number), 'title': 'Issue ' + str(number),
            'body': body, 'state': 'open', 'updated_at': '2026-11-24T10:00:00Z',
            'html_url': 'https://github.com/acme/app/issues/' + str(number)}


def project(number=7):
    return {'id': 'P_' + str(number), 'number': number, 'title': 'ASDG Plan',
            'url': 'https://github.com/orgs/acme/projects/' + str(number), 'closed': False}


def field(name='Status', field_id='F_STATUS', data_type='SINGLE_SELECT'):
    value = {'id': field_id, 'name': name, 'dataType': data_type,
             '__typename': 'ProjectV2SingleSelectField' if data_type == 'SINGLE_SELECT' else 'ProjectV2Field'}
    if data_type == 'SINGLE_SELECT':
        value['options'] = [{'id': 'O_TODO', 'name': 'Todo'}, {'id': 'O_DONE', 'name': 'Done'}]
    return value


class Fake:
    """Routes a real adapter's REST/GraphQL requests and records exact payloads."""
    def __init__(self):
        self.calls = []
        self.project_pages = {None: connection([project()])}
        self.field_pages = {None: connection([field()])}
        self.item_pages = {None: connection([])}
        self.value_pages = {}
        self.issue_pages = {1: [issue()]}
        self.explicit_project = project()
        self.mutations = {}

    def __call__(self, method, path, payload):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if path == '/users/acme':
            return {'node_id': 'ACME', 'type': 'Organization'}
        if path == '/repos/acme/app':
            return {'node_id': 'R_APP', 'full_name': 'acme/app'}
        if method == 'GET' and path.startswith('/repos/acme/app/issues?'):
            return copy.deepcopy(self.issue_pages[int(path.rsplit('page=', 1)[1])])
        if method == 'GET' and path.startswith('/repos/acme/app/issues/'):
            return issue(int(path.rsplit('/', 1)[1]), marked_body('Description', 'local:abc'))
        if method in {'POST', 'PATCH'} and path.startswith('/repos/acme/app/issues'):
            result = issue(123, payload.get('body', 'Description'))
            result.update({key: payload[key] for key in ('title', 'state') if key in payload})
            return result
        if path != '/graphql':
            raise AssertionError((method, path, payload))
        query, variables = payload['query'], payload['variables']
        # ProjectV2FieldConfiguration is a union in GitHub's schema: properties
        # of item-value fields require an inline fragment, even for select values.
        if re.search(r'\bfield\s*\{\s*(id|name)\b', query):
            return {'errors': [{'message': 'Selections cannot be made directly on ProjectV2FieldConfiguration'}]}
        cursor = variables.get('cursor')
        if query.startswith('mutation'):
            for key, result in self.mutations.items():
                if key + '(' in query:
                    return {'data': {key: copy.deepcopy(result)}}
            raise AssertionError('Unexpected mutation: ' + query)
        if 'projectsV2(' in query:
            return {'data': {'organization': {'projectsV2': self.project_pages[cursor]}}}
        if 'projectV2(number:' in query:
            return {'data': {'organization': {'projectV2': self.explicit_project}}}
        if 'fields(first:' in query:
            return {'data': {'node': {'fields': self.field_pages[cursor]}}}
        if 'items(first:' in query:
            return {'data': {'node': {'items': self.item_pages[cursor]}}}
        if 'fieldValues(first:' in query:
            return {'data': {'node': {'fieldValues': self.value_pages[(variables['id'], cursor)]}}}
        raise AssertionError(query)


class GitHubPlanTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.api = GitHub(transport=self.fake)
        self.config = {'owner': 'acme', 'number': None, 'title': 'ASDG Plan'}

    def snapshot(self):
        return self.api.snapshot('acme/app', self.config)

    def test_snapshot_follows_all_graphql_pages_and_imports_only_repository_issues(self):
        self.fake.project_pages = {None: connection([dict(project(), title='Other')], 'P2'),
                                   'P2': connection([project()])}
        self.fake.field_pages = {None: connection([field()], 'F2'),
                                 'F2': connection([field('ASDG Team', 'F_TEAM', 'TEXT')])}
        def item(number, item_id, repo='acme/app', typename='Issue'):
            return {'id': item_id, 'isArchived': False, 'content': {'__typename': typename, 'number': number,
                                                                  'repository': {'nameWithOwner': repo}}}
        self.fake.item_pages = {None: connection([item(1, 'PI1'), item(2, 'OTHER', 'acme/other')], 'I2'),
                                'I2': connection([item(3, 'PR', typename='PullRequest')])}
        self.fake.value_pages = {('PI1', None): connection([{'field': {'name': 'Status'}, 'name': 'Todo'}], 'V2'),
                                 ('PI1', 'V2'): connection([{'field': {'name': 'ASDG Team'}, 'text': 'Atlas'}])}
        self.fake.issue_pages[1] = [issue(1, marked_body('Description\n', 'local:abc')),
                                    dict(issue(3), pull_request={'url': 'ignored'})]
        result = self.snapshot()
        self.assertEqual([row['id'] for row in result['issues']], ['local:abc'])
        self.assertEqual(result['issues'][0]['fields']['body'], 'Description\n')
        self.assertEqual(result['issues'][0]['fields']['team'], 'Atlas')
        self.assertEqual(result['missing_fields'], ['ASDG Priority', 'ASDG Sprint'])
        self.assertEqual(result['issues'][0]['item_id'], 'PI1')
        self.assertFalse(any(call[2] and call[2].get('variables', {}).get('id') == 'OTHER' for call in self.fake.calls))

    def test_rest_issue_pagination_and_pr_filtering(self):
        self.fake.issue_pages = {1: [issue(i) for i in range(1, 101)], 2: [issue(101)]}
        result = self.snapshot()
        self.assertEqual(len(result['issues']), 101)
        self.assertEqual(result['issues'][-1]['issue_number'], 101)

    def test_missing_project_is_distinguished_from_unavailable_explicit_project(self):
        self.fake.project_pages = {None: connection([])}
        result = self.snapshot()
        self.assertIsNone(result['project'])
        self.assertEqual(result['missing_fields'], list(FIELD_NAMES.values()))
        self.config['number'] = 7
        self.fake.explicit_project = None
        with self.assertRaisesRegex(Conflict, 'not be recreated'):
            self.snapshot()

    def test_duplicate_titles_closed_projects_and_duplicate_fields_fail(self):
        self.fake.project_pages = {None: connection([project(7), project(8)])}
        with self.assertRaisesRegex(Conflict, 'Multiple GitHub Projects'):
            self.snapshot()
        self.fake.project_pages = {None: connection([dict(project(), closed=True)])}
        with self.assertRaisesRegex(Conflict, 'closed'):
            self.snapshot()
        self.fake.project_pages = {None: connection([project()])}
        self.fake.field_pages = {None: connection([field(), field(field_id='DUPLICATE')])}
        with self.assertRaisesRegex(Conflict, 'Duplicate managed'):
            self.snapshot()

    def test_duplicate_issue_markers_and_nonadvancing_cursor_fail(self):
        self.fake.issue_pages[1] = [issue(1, marked_body('One', 'same')), issue(2, marked_body('Two', 'same'))]
        with self.assertRaisesRegex(Conflict, 'Duplicate issue'):
            self.snapshot()
        self.fake.project_pages = {None: connection([], 'same'), 'same': connection([], 'same')}
        with self.assertRaisesRegex(Conflict, 'pagination did not advance'):
            self.snapshot()

    def test_inaccessible_project_items_and_incomplete_collections_fail(self):
        self.fake.item_pages[None] = connection([None])
        with self.assertRaisesRegex(Conflict, 'inaccessible'):
            self.snapshot()
        self.fake.item_pages[None] = connection([{'id': 'HIDDEN', 'content': None}])
        with self.assertRaisesRegex(Conflict, 'inaccessible'):
            self.snapshot()
        self.fake.item_pages[None] = {'nodes': [], 'pageInfo': {}}
        with self.assertRaisesRegex(Conflict, 'incomplete'):
            self.snapshot()

    def test_graphql_errors_never_become_missing_project(self):
        def transport(method, path, payload):
            if path == '/graphql':
                return {'data': {'organization': None}, 'errors': [{'message': 'secret is not printed'}]}
            return self.fake(method, path, payload)
        api = GitHub(transport=transport)
        with self.assertRaises(Conflict) as raised:
            api.snapshot('acme/app', self.config)
        self.assertNotIn('secret', str(raised.exception))

    def test_request_errors_are_rejected_but_data_null_errors_remain_uncertain(self):
        error = {'message': 'Variable input is invalid; secret', 'extensions': {'code': 'variableMismatch'}}
        api = GitHub(transport=lambda method, path, payload: {'errors': [error]})
        with self.assertRaises(GitHubRejected) as raised:
            api._graphql('mutation($input:CreateProjectV2Input!){createProjectV2(input:$input){projectV2{id}}}')
        self.assertNotIn('secret', str(raised.exception))
        for data in (None, {'createProjectV2': None}, {'createProjectV2': {'projectV2': {'id': 'P_7'}}}):
            for kind in ('FORBIDDEN', 'NOT_FOUND', 'UNPROCESSABLE'):
                response = {'data': data, 'errors': [{'type': kind, 'message': 'secret', 'path': ['createProjectV2']}]}
                api = GitHub(transport=lambda method, path, payload: response)
                with self.assertRaises(Conflict) as raised:
                    api._graphql('mutation{createProjectV2{projectV2{id}}}')
                self.assertNotIsInstance(raised.exception, GitHubRejected)
                self.assertNotIn('secret', str(raised.exception))

    def test_field_configuration_union_rejects_direct_selections(self):
        with self.assertRaises(Conflict):
            self.api._graphql('query{node(id:"PI1"){... on ProjectV2Item{fieldValues(first:1){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{id name}}}}}}}')
        self.fake.value_pages[('PI1', None)] = connection([{'field': {'name': 'Status'}, 'name': 'Todo'}])
        self.assertEqual(self.api._item_values('PI1'), {'Status': 'Todo'})

    def test_body_marker_roundtrip_and_malformed_markers(self):
        for body in ('', 'Text', 'Text\n', 'Text\n\n'):
            self.assertEqual(split_marker(marked_body(body, 'local:abc')), (body, 'local:abc'))
        for body in ('<!-- asdg-plan:unsafe id -->', '<!-- asdg-plan:a --> trailing',
                     '<!-- asdg-plan:a -->\n\n<!-- asdg-plan:b -->'):
            with self.assertRaises(Conflict):
                split_marker(body)
        with self.assertRaises(Conflict):
            marked_body(marked_body('x', 'a'), 'b')

    def test_create_project_links_exact_repository_and_returns_metadata(self):
        self.fake.mutations['createProjectV2'] = {'projectV2': project()}
        created = self.api.create_project('acme/app', self.config)
        self.assertEqual(created['number'], 7)
        self.assertEqual(self.fake.calls[-1][2]['variables']['input'],
                         {'ownerId': 'ACME', 'repositoryId': 'R_APP', 'title': 'ASDG Plan'})

    def test_create_managed_fields_has_exact_options_or_text_type(self):
        self.fake.mutations['createProjectV2Field'] = {'projectV2Field': field()}
        self.api.create_field('P_7', 'Status')
        values = self.fake.calls[-1][2]['variables']['input']
        self.assertEqual([item['name'] for item in values['singleSelectOptions']], ['Todo', 'In Progress', 'Done'])
        self.fake.mutations['createProjectV2Field'] = {'projectV2Field': field('ASDG Sprint', 'SPRINT', 'TEXT')}
        self.api.create_field('P_7', 'ASDG Sprint')
        self.assertEqual(self.fake.calls[-1][2]['variables']['input']['dataType'], 'TEXT')
        with self.assertRaises(Conflict):
            self.api.create_field('P_7', 'Unrelated field')

    def test_create_issue_uses_stable_marker_without_notes_and_closes_separately(self):
        item = {'id': 'local:abc', 'notes': 'Private notes',
                'fields': {'title': 'New issue', 'body': 'Public description', 'state': 'CLOSED'}}
        created = self.api.create_issue('acme/app', item)
        self.assertEqual(created['id'], 'local:abc')
        values = self.fake.calls[-1][2]
        self.assertEqual(set(values), {'title', 'body'})
        self.assertNotIn('Private', json.dumps(values))
        self.assertEqual(created['fields']['state'], 'OPEN')

    def test_issue_patch_is_narrow_and_preserves_marker(self):
        result = self.api.update_issue('acme/app', 1, {'body': 'New description'}, marker='local:abc')
        self.assertEqual(result['id'], 'local:abc')
        self.assertEqual(self.fake.calls[-1][2], {'body': marked_body('New description', 'local:abc')})
        self.api.update_issue('acme/app', 1, {'state': 'CLOSED'})
        self.assertEqual(self.fake.calls[-1][2], {'state': 'closed'})
        with self.assertRaisesRegex(Conflict, 'identity changed'):
            self.api.update_issue('acme/app', 1, {'body': 'Bad'}, marker='different')
        with self.assertRaises(Conflict):
            self.api.update_issue('acme/app', 1, {'assignees': ['someone']})

    def test_add_item_and_single_select_clear_text_iteration_updates(self):
        self.fake.mutations.update({
            'addProjectV2ItemById': {'item': {'id': 'PI1'}},
            'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'PI1'}},
            'clearProjectV2ItemFieldValue': {'projectV2Item': {'id': 'PI1'}}})
        self.assertEqual(self.api.add_item('P_7', 'I_1'), 'PI1')
        self.api.update_fields('P_7', 'PI1', {'status': 'Todo'})
        self.assertEqual(self.fake.calls[-1][2]['variables']['input']['value'], {'singleSelectOptionId': 'O_TODO'})
        self.api.update_fields('P_7', 'PI1', {'status': ''})
        self.assertIn('clearProjectV2ItemFieldValue(', self.fake.calls[-1][2]['query'])
        self.fake.field_pages[None] = connection([field('ASDG Team', 'TEAM', 'TEXT')])
        self.api.update_fields('P_7', 'PI1', {'team': 'Atlas'})
        self.assertEqual(self.fake.calls[-1][2]['variables']['input']['value'], {'text': 'Atlas'})
        sprint = field('ASDG Sprint', 'SPRINT', 'ITERATION')
        sprint['configuration'] = {'iterations': [{'id': 'ITER5', 'title': 'Sprint 5', 'startDate': '2026-11-24', 'duration': 14}],
                                   'completedIterations': []}
        self.fake.field_pages[None] = connection([sprint])
        self.api.update_fields('P_7', 'PI1', {'sprint': 'Sprint 5'})
        self.assertEqual(self.fake.calls[-1][2]['variables']['input']['value'], {'iterationId': 'ITER5'})

    def test_field_validation_rejects_ambiguous_or_missing_options_before_mutation(self):
        with self.assertRaisesRegex(Conflict, 'only Todo'):
            self.api.validate_fields({'fields': {}}, {'status': 'Invented status'})
        metadata = {'sprint': {'name': 'ASDG Sprint', 'data_type': 'ITERATION',
                               'iterations': [{'id': 'A', 'title': 'Sprint 5'}, {'id': 'B', 'title': 'Sprint 5'}]}}
        with self.assertRaisesRegex(Conflict, 'no unique'):
            validate_fields({'fields': metadata}, {'sprint': 'Sprint 5'})
        count = len(self.fake.calls)
        with self.assertRaisesRegex(Conflict, 'one Project field'):
            self.api.update_fields('P_7', 'PI1', {'status': 'Todo', 'team': 'Atlas'})
        self.assertEqual(count, len(self.fake.calls))

    def test_auth_failure_and_http_error_are_sanitized_and_not_retried(self):
        with patch.dict(os.environ, {}, clear=True), patch('cli_plan_github.shutil.which', return_value=None):
            with self.assertRaisesRegex(GitHubRejected, 'authentication unavailable'):
                GitHub().snapshot('acme/app', self.config)
        error = HTTPError('https://api.github.com/graphql', 403, 'credential secret', {}, io.BytesIO(b'secret'))
        with patch('cli_plan_github.build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(GitHubRejected) as raised:
                GitHub(token='secret')._request('POST', '/graphql', {})
            self.assertNotIn('secret', str(raised.exception))
            self.assertEqual(build.return_value.open.call_count, 1)
            self.assertTrue(error.closed)

    def test_server_error_keeps_unknown_mutation_outcome(self):
        error = HTTPError('https://api.github.com/graphql', 503, 'secret', {}, io.BytesIO(b'secret'))
        with patch('cli_plan_github.build_opener') as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(Conflict) as raised:
                GitHub(token='secret')._request('POST', '/graphql', {})
            self.assertNotIsInstance(raised.exception, GitHubRejected)
            self.assertNotIn('secret', str(raised.exception))
            self.assertEqual(build.return_value.open.call_count, 1)
            self.assertTrue(error.closed)

    def test_host_and_repository_inputs_cannot_redirect_credentials(self):
        for path in ('https://elsewhere.invalid', '//elsewhere.invalid'):
            with self.assertRaises(Conflict):
                self.api._request('GET', path)
        with self.assertRaises(Conflict):
            self.api.snapshot('acme/app?token=oops', self.config)
        self.assertEqual(self.fake.calls, [])


if __name__ == '__main__':
    unittest.main()
