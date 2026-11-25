"""GitHub.com Issues and Projects transport for explicit planner synchronization."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cli_files import Conflict

API = 'https://api.github.com'
FIELD_NAMES = {'status': 'Status', 'priority': 'ASDG Priority',
               'team': 'ASDG Team', 'sprint': 'ASDG Sprint'}
STATUS_OPTIONS = ('Todo', 'In Progress', 'Done')
MARKER = re.compile(r'<!-- asdg-plan:([A-Za-z0-9][A-Za-z0-9._:-]{0,127}) -->')
FIELD_FRAGMENT = '''__typename
  ... on ProjectV2Field { id name dataType }
  ... on ProjectV2SingleSelectField { id name dataType options { id name } }
  ... on ProjectV2IterationField { id name dataType configuration {
    iterations { id title startDate duration }
    completedIterations { id title startDate duration }
  } }'''
VALUE_FRAGMENT = '''__typename
  ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2Field { id name } } }
  ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2SingleSelectField { id name } } }
  ... on ProjectV2ItemFieldIterationValue { title field { ... on ProjectV2IterationField { id name } } }'''


class GitHubRejected(Conflict):
    """The request was not transmitted or GitHub definitively rejected it."""


def _repository(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise Conflict('Expected a GitHub.com owner/repository name.')
    return value


def _owner(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]+', value):
        raise Conflict('Expected a GitHub account login.')
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Conflict('Expected a positive GitHub issue/project number.')
    return value


def split_marker(body):
    """Return logical body and optional stable ID without normalizing user prose."""
    body = body or ''
    if not isinstance(body, str):
        raise Conflict('GitHub returned an invalid issue body.')
    matches = list(MARKER.finditer(body))
    if not matches:
        if '<!-- asdg-plan:' in body:
            raise Conflict('Malformed ASDG issue marker; reconcile it explicitly.')
        return body, None
    if len(matches) != 1 or body.count('<!-- asdg-plan:') != 1:
        raise Conflict('Multiple ASDG markers in one issue; reconcile it explicitly.')
    match = matches[0]
    if match.end() != len(body) or (match.start() and body[match.start()-2:match.start()] != '\n\n'):
        raise Conflict('ASDG issue marker must be the final separate paragraph.')
    return body[:max(0, match.start()-2)], match.group(1)


def marked_body(body, marker):
    logical, existing = split_marker(body)
    if existing is not None:
        raise Conflict('The planner body must not contain an ASDG identity marker.')
    if marker is None:
        return logical
    if not isinstance(marker, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', marker):
        raise Conflict('Invalid stable ASDG issue identity.')
    return logical + '\n\n<!-- asdg-plan:' + marker + ' -->'


def _field(raw):
    result = {'id': raw['id'], 'name': raw['name'], 'data_type': raw['dataType']}
    if raw['dataType'] == 'SINGLE_SELECT':
        result['options'] = raw.get('options', [])
    if raw['dataType'] == 'ITERATION':
        config = raw.get('configuration', {})
        result['iterations'] = config.get('iterations', []) + config.get('completedIterations', [])
    return result


def validate_fields(snapshot, values):
    """Reject unrepresentable values before the orchestrator makes any writes."""
    for key, value in values.items():
        if key not in FIELD_NAMES or not isinstance(value, str):
            raise Conflict('Invalid managed project field or value.')
        metadata = snapshot.get('fields', {}).get(key)
        if metadata is None:
            if key == 'status' and value and value not in STATUS_OPTIONS:
                raise Conflict('New Status field supports only Todo, In Progress and Done.')
            continue
        kind = metadata['data_type']
        if kind == 'TEXT' or value == '':
            continue
        choices = metadata.get('options', []) if kind == 'SINGLE_SELECT' else metadata.get('iterations', [])
        name = 'name' if kind == 'SINGLE_SELECT' else 'title'
        if kind not in {'SINGLE_SELECT', 'ITERATION'} or sum(x[name] == value for x in choices) != 1:
            raise Conflict('Project field ' + metadata['name'] + ' has no unique option/iteration for the requested value.')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    """Transport receives (method, API-relative path, JSON body) and returns JSON.

    Injected transport is for tests. Production always authenticates to api.github.com;
    requests are bounded, redirects rejected, and mutations are never auto-retried.
    """
    validate_fields = staticmethod(validate_fields)

    def __init__(self, token=None, transport=None):
        self._token = token
        self._transport = transport
        self._fields = {}

    def _credential(self):
        if self._token is None:
            self._token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self._token and shutil.which('gh'):
            try:
                result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                        capture_output=True, text=True, timeout=15, check=False)
                if result.returncode == 0:
                    self._token = result.stdout.strip()
            except (OSError, subprocess.SubprocessError):
                pass
        if not self._token:
            raise GitHubRejected('GitHub authentication unavailable. Use an existing GH_TOKEN/GITHUB_TOKEN or authenticated gh CLI with repository and Projects access.')
        if not isinstance(self._token, str) or any(c in self._token for c in '\r\n'):
            raise GitHubRejected('Invalid GitHub credential format.')
        return self._token

    def _request(self, method, path, payload=None):
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//'):
            raise Conflict('Only fixed GitHub API-relative endpoints are supported.')
        if self._transport is not None:
            return self._transport(method, path, payload)
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = Request(API + path, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self._credential(), 'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'ASDG-project-plan-sync'})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise Conflict('GitHub response exceeds the synchronization size limit.')
            return json.loads(raw)
        except HTTPError as exc:
            error = GitHubRejected if exc.code in {400, 401, 403, 404, 409, 410, 422} else Conflict
            message = 'GitHub API HTTP ' + str(exc.code) + '; check authentication, repository/Projects permissions and rate limits. No mutation was automatically retried.'
            try:
                exc.close()
            finally:
                raise error(message) from None
        except (URLError, TimeoutError, OSError, UnicodeError, ValueError):
            raise Conflict('GitHub API transport/response failure; remote mutation outcome may be unknown. Reconcile before retrying.') from None

    def _graphql(self, query, variables=None):
        response = self._request('POST', '/graphql', {'query': query, 'variables': variables or {}})
        # GraphQL request errors have no data entry and occur before execution.
        # data:null is different: resolver errors may have followed a mutation.
        errors = response.get('errors') if isinstance(response, dict) else None
        if (isinstance(errors, list) and errors and 'data' not in response
                and all(isinstance(item, dict) and isinstance(item.get('message'), str) for item in errors)):
            raise GitHubRejected('GitHub GraphQL rejected the request before execution; check query inputs and permissions. No mutation was automatically retried.')
        if not isinstance(response, dict) or response.get('errors') or not isinstance(response.get('data'), dict):
            raise Conflict('GitHub GraphQL request failed or returned incomplete data; verify Projects permissions and reconcile any pending mutation.')
        return response['data']

    @staticmethod
    def _connection(connection, seen):
        if not isinstance(connection, dict) or not isinstance(connection.get('nodes'), list):
            raise Conflict('GitHub returned an incomplete paginated collection.')
        info = connection.get('pageInfo', {})
        if not isinstance(info.get('hasNextPage'), bool) or any(node is None for node in connection['nodes']):
            raise Conflict('GitHub returned inaccessible or incomplete collection entries.')
        cursor = info.get('endCursor') if info['hasNextPage'] else None
        if info['hasNextPage'] and (not isinstance(cursor, str) or not cursor or cursor in seen):
            raise Conflict('GitHub pagination did not advance.')
        if cursor:
            seen.add(cursor)
        return connection['nodes'], cursor

    def _account(self, login):
        raw = self._request('GET', '/users/' + _owner(login))
        if not isinstance(raw, dict) or raw.get('type') not in {'User', 'Organization'} or not raw.get('node_id'):
            raise Conflict('GitHub project owner is unavailable or unsupported.')
        return raw['node_id'], 'organization' if raw['type'] == 'Organization' else 'user'

    def _project(self, config):
        owner = _owner(config['owner'])
        _, kind = self._account(owner)
        number = config.get('number')
        if number is not None:
            query = 'query($login:String!,$number:Int!){' + kind + '(login:$login){projectV2(number:$number){id number title url closed}}}'
            account = self._graphql(query, {'login': owner, 'number': _number(number)}).get(kind)
            if not account or not account.get('projectV2'):
                raise Conflict('Configured GitHub Project is missing or inaccessible; it will not be recreated automatically.')
            project = account['projectV2']
        else:
            projects, cursor, seen = [], None, set()
            query = 'query($login:String!,$cursor:String){' + kind + '(login:$login){projectsV2(first:100,after:$cursor){nodes{id number title url closed} pageInfo{hasNextPage endCursor}}}}'
            while True:
                account = self._graphql(query, {'login': owner, 'cursor': cursor}).get(kind)
                if not account:
                    raise Conflict('GitHub project owner is inaccessible.')
                nodes, cursor = self._connection(account.get('projectsV2'), seen)
                projects.extend(p for p in nodes if p.get('title') == config['title'])
                if cursor is None:
                    break
            if len(projects) > 1:
                raise Conflict('Multiple GitHub Projects share the configured title; choose an explicit project number.')
            if not projects:
                return None
            project = projects[0]
        if project.get('closed'):
            raise Conflict('Configured GitHub Project is closed; reopen or select another explicitly.')
        return {key: project[key] for key in ('id', 'number', 'title', 'url')} | {'owner': owner}

    def project_fields(self, project_id):
        fields, cursor, seen = [], None, set()
        query = 'query($id:ID!,$cursor:String){node(id:$id){... on ProjectV2{fields(first:100,after:$cursor){nodes{' + FIELD_FRAGMENT + '} pageInfo{hasNextPage endCursor}}}}}'
        while True:
            node = self._graphql(query, {'id': project_id, 'cursor': cursor}).get('node')
            if not node:
                raise Conflict('GitHub Project is unavailable.')
            nodes, cursor = self._connection(node.get('fields'), seen)
            fields.extend(nodes)
            if cursor is None:
                break
        result = {}
        for key, name in FIELD_NAMES.items():
            candidates = [raw for raw in fields if raw.get('name') == name]
            if len(candidates) > 1:
                raise Conflict('Duplicate managed GitHub Project field: ' + name)
            if not candidates:
                continue
            metadata = _field(candidates[0])
            allowed = {'SINGLE_SELECT'} if key == 'status' else {'TEXT', 'SINGLE_SELECT', 'ITERATION'} if key == 'sprint' else {'TEXT', 'SINGLE_SELECT'}
            if metadata['data_type'] not in allowed:
                raise Conflict('Incompatible managed GitHub Project field type: ' + name)
            result[key] = metadata
        self._fields[project_id] = result
        return result

    def _item_values(self, item_id):
        values, cursor, seen = {}, None, set()
        query = 'query($id:ID!,$cursor:String){node(id:$id){... on ProjectV2Item{fieldValues(first:100,after:$cursor){nodes{' + VALUE_FRAGMENT + '} pageInfo{hasNextPage endCursor}}}}}'
        while True:
            node = self._graphql(query, {'id': item_id, 'cursor': cursor}).get('node')
            if not node:
                raise Conflict('GitHub Project item became unavailable during snapshot.')
            nodes, cursor = self._connection(node.get('fieldValues'), seen)
            for entry in nodes:
                name = (entry.get('field') or {}).get('name')
                if name in FIELD_NAMES.values():
                    if name in values:
                        raise Conflict('Duplicate managed field values in one Project item.')
                    values[name] = entry.get('text', entry.get('name', entry.get('title', '')))
            if cursor is None:
                return values

    def _project_items(self, project_id, repository):
        items, cursor, seen = {}, None, set()
        query = '''query($id:ID!,$cursor:String){node(id:$id){... on ProjectV2{
          items(first:100,after:$cursor){nodes{id isArchived content{__typename
            ... on Issue{number repository{nameWithOwner}}}}
            pageInfo{hasNextPage endCursor}}}}}'''
        while True:
            node = self._graphql(query, {'id': project_id, 'cursor': cursor}).get('node')
            if not node:
                raise Conflict('GitHub Project became unavailable during snapshot.')
            nodes, cursor = self._connection(node.get('items'), seen)
            for item in nodes:
                content = item.get('content')
                if not isinstance(content, dict) or not content.get('__typename'):
                    raise Conflict('A GitHub Project item is inaccessible; complete repository scope cannot be established.')
                if content.get('__typename') != 'Issue' or content.get('repository', {}).get('nameWithOwner', '').lower() != repository.lower():
                    continue
                number = _number(content['number'])
                if number in items:
                    raise Conflict('One issue appears multiple times in the GitHub Project.')
                items[number] = {'id': item['id'], 'values': self._item_values(item['id'])}
            if cursor is None:
                return items

    @staticmethod
    def _issue(raw, item=None):
        body, marker = split_marker(raw.get('body'))
        number = _number(raw['number'])
        state = raw.get('state', '').upper()
        if state not in {'OPEN', 'CLOSED'} or not isinstance(raw.get('title'), str):
            raise Conflict('GitHub returned invalid issue state/title.')
        values = item['values'] if item else {}
        return {'id': marker or 'github:' + str(number), 'issue_number': number,
                'node_id': raw['node_id'], 'item_id': item['id'] if item else None,
                'url': raw['html_url'], 'updated_at': raw['updated_at'],
                'fields': {'title': raw['title'], 'body': body, 'state': state,
                           **{key: values.get(name, '') for key, name in FIELD_NAMES.items()}}}

    def snapshot(self, repository, project_config):
        repository = _repository(repository)
        repo = self._request('GET', '/repos/' + repository)
        if not isinstance(repo, dict) or str(repo.get('full_name', '')).lower() != repository.lower() or not repo.get('node_id'):
            raise Conflict('GitHub repository identity is unavailable or changed.')
        project = self._project(project_config)
        fields = self.project_fields(project['id']) if project else {}
        items = self._project_items(project['id'], repository) if project else {}
        issues, identities, numbers = [], set(), set()
        page = 1
        while True:
            path = '/repos/' + repository + '/issues?' + urlencode({'state': 'all', 'sort': 'created', 'direction': 'asc', 'per_page': 100, 'page': page})
            rows = self._request('GET', path)
            if not isinstance(rows, list):
                raise Conflict('GitHub returned an incomplete issue collection.')
            for raw in rows:
                if 'pull_request' in raw:
                    continue
                item = self._issue(raw, items.get(raw.get('number')))
                if item['id'] in identities or item['issue_number'] in numbers:
                    raise Conflict('Duplicate issue identity/number in GitHub snapshot; reconcile before syncing.')
                identities.add(item['id'])
                numbers.add(item['issue_number'])
                issues.append(item)
            if len(rows) < 100:
                break
            page += 1
        if set(items) - numbers:
            raise Conflict('A Project issue is absent from the repository snapshot; retry a fresh preview.')
        return {'repository': repository, 'repository_id': repo['node_id'], 'project': project,
                'issues': sorted(issues, key=lambda item: item['issue_number']), 'fields': fields,
                'missing_fields': [name for key, name in FIELD_NAMES.items() if key not in fields]}

    def create_project(self, repository, config):
        repository = _repository(repository)
        repo = self._request('GET', '/repos/' + repository)
        owner_id, _ = self._account(config['owner'])
        values = {'ownerId': owner_id, 'repositoryId': repo['node_id'], 'title': config['title']}
        query = 'mutation($input:CreateProjectV2Input!){createProjectV2(input:$input){projectV2{id number title url}}}'
        raw = self._graphql(query, {'input': values})['createProjectV2']['projectV2']
        return {key: raw[key] for key in ('id', 'number', 'title', 'url')} | {'owner': config['owner']}

    def create_field(self, project_id, name):
        if name not in FIELD_NAMES.values():
            raise Conflict('Only named ASDG planning fields may be created.')
        values = {'projectId': project_id, 'name': name, 'dataType': 'SINGLE_SELECT' if name == 'Status' else 'TEXT'}
        if name == 'Status':
            values['singleSelectOptions'] = [{'name': text, 'color': color, 'description': ''}
                                            for text, color in zip(STATUS_OPTIONS, ('GRAY', 'BLUE', 'GREEN'))]
        query = 'mutation($input:CreateProjectV2FieldInput!){createProjectV2Field(input:$input){projectV2Field{' + FIELD_FRAGMENT + '}}}'
        raw = self._graphql(query, {'input': values})['createProjectV2Field']['projectV2Field']
        self._fields.pop(project_id, None)
        return _field(raw)

    def create_issue(self, repository, item):
        repository = _repository(repository)
        fields = item['fields']
        # REST issue creation always creates OPEN; the orchestrator sets CLOSED separately.
        values = {'title': fields['title'], 'body': marked_body(fields['body'], item['id'])}
        return self._issue(self._request('POST', '/repos/' + repository + '/issues', values))

    def update_issue(self, repository, number, fields, marker=None):
        repository, number = _repository(repository), _number(number)
        if not fields or set(fields) - {'title', 'body', 'state'}:
            raise Conflict('Issue update must contain only changed title, body or state fields.')
        values = dict(fields)
        path = '/repos/' + repository + '/issues/' + str(number)
        if 'body' in values:
            current = self._request('GET', path)
            _, existing = split_marker(current.get('body'))
            if marker is not None and existing != marker:
                raise Conflict('Issue identity changed before body update.')
            values['body'] = marked_body(values['body'], existing)
        if 'state' in values:
            if values['state'] not in {'OPEN', 'CLOSED'}:
                raise Conflict('Invalid issue state.')
            values['state'] = values['state'].lower()
        return self._issue(self._request('PATCH', path, values))

    def add_item(self, project_id, issue_node_id):
        query = 'mutation($input:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$input){item{id}}}'
        raw = self._graphql(query, {'input': {'projectId': project_id, 'contentId': issue_node_id}})
        return raw['addProjectV2ItemById']['item']['id']

    def update_fields(self, project_id, item_id, fields):
        """One field per call makes the orchestrator's mutation journal unambiguous."""
        if len(fields) != 1:
            raise Conflict('Update one Project field per journaled operation.')
        metadata = self.project_fields(project_id)
        validate_fields({'fields': metadata}, fields)
        key, value = next(iter(fields.items()))
        if key not in metadata:
            raise Conflict('Managed Project field is missing; create it before assigning values.')
        field = metadata[key]
        args = {'projectId': project_id, 'itemId': item_id, 'fieldId': field['id']}
        if not value:
            query = 'mutation($input:ClearProjectV2ItemFieldValueInput!){clearProjectV2ItemFieldValue(input:$input){projectV2Item{id}}}'
        else:
            if field['data_type'] == 'TEXT':
                args['value'] = {'text': value}
            elif field['data_type'] == 'SINGLE_SELECT':
                args['value'] = {'singleSelectOptionId': next(x['id'] for x in field['options'] if x['name'] == value)}
            else:
                args['value'] = {'iterationId': next(x['id'] for x in field['iterations'] if x['title'] == value)}
            query = 'mutation($input:UpdateProjectV2ItemFieldValueInput!){updateProjectV2ItemFieldValue(input:$input){projectV2Item{id}}}'
        return self._graphql(query, {'input': args})
