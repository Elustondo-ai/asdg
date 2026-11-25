"""Isolated Git and fake-GitHub forward tests for explicit planning synchronization."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import cli_plan_sync as sync
from cli_files import Conflict
from cli_plan_merge import empty_cache
from cli_plan_github import FIELD_NAMES, STATUS_OPTIONS, GitHubRejected, validate_fields


class Interrupted(RuntimeError):
    pass


def fields(title='Task', **changes):
    return dict({'title': title, 'body': 'Shared description', 'state': 'OPEN',
                 'status': 'Todo', 'priority': 'High', 'team': 'Atlas', 'sprint': 'SPRINT-001'}, **changes)


def item(identifier='PLAN-001', number=None, base=None, **changes):
    return {'id': identifier, 'issue_number': number, 'fields': fields(**changes),
            'base': copy.deepcopy(base), 'notes': 'Private local analysis',
            'sources': ['docs/asdg/07-planning/03-plan.md']}


class FakeGitHub:
    """Deterministic public adapter contract with injected before/after-write failures."""
    def __init__(self, project=True):
        self.project = ({'id': 'P1', 'owner': 'example', 'number': 1,
                         'title': 'ASDG Plan — example/client',
                         'url': 'https://github.com/orgs/example/projects/1'} if project else None)
        self.fields = {}
        if project:
            for name in FIELD_NAMES.values():
                self._field(name)
        self.issues = []
        self.mutations = []
        self.reads = 0
        self.fail_before = None
        self.fail_after = None
        self.reject_once = None
        self.after_mutation = None

    def _field(self, name):
        key = next(key for key, value in FIELD_NAMES.items() if value == name)
        metadata = {'id': 'F-' + key, 'name': name, 'data_type': 'SINGLE_SELECT' if key == 'status' else 'TEXT'}
        if key == 'status':
            metadata['options'] = [{'id': str(i), 'name': value} for i, value in enumerate(STATUS_OPTIONS)]
        self.fields[key] = metadata

    def add_existing(self, identifier, number, values=None, member=True):
        row = {'id': identifier, 'issue_number': number, 'node_id': 'I' + str(number),
               'item_id': 'PI' + str(number) if member else None,
               'url': 'https://github.com/example/client/issues/' + str(number),
               'updated_at': 'fixture-version-0', 'fields': copy.deepcopy(values or fields())}
        if not member:
            row['fields'].update({key: '' for key in FIELD_NAMES})
        self.issues.append(row)
        return row

    def snapshot(self, repository, config):
        assert repository == 'example/client'
        self.reads += 1
        return copy.deepcopy({'repository': repository, 'repository_id': 'R1',
                              'project': self.project, 'fields': self.fields,
                              'missing_fields': [name for key, name in FIELD_NAMES.items() if key not in self.fields],
                              'issues': sorted(self.issues, key=lambda row: row['issue_number'])})

    def validate_fields(self, snapshot, values):
        validate_fields(snapshot, values)

    def mutate(self, kind, action):
        self.mutations.append(kind)
        if self.reject_once == kind:
            self.reject_once = None
            raise GitHubRejected('GitHub rejected fixture write: permission required')
        if self.fail_before == kind:
            self.fail_before = None
            raise Interrupted('Write outcome not visible: ' + kind)
        result = action()
        if self.after_mutation:
            self.after_mutation(kind)
        if self.fail_after == kind:
            self.fail_after = None
            raise Interrupted('Response lost after: ' + kind)
        return result

    def create_project(self, repository, config):
        def action():
            self.project = {'id': 'P1', 'owner': config['owner'], 'number': 1,
                            'title': config['title'], 'url': 'https://github.com/orgs/example/projects/1'}
            return copy.deepcopy(self.project)
        return self.mutate('create_project', action)

    def create_field(self, project_id, name):
        return self.mutate('create_field', lambda: self._field(name))

    def create_issue(self, repository, value):
        def action():
            number = max([row['issue_number'] for row in self.issues] + [0]) + 1
            desired = copy.deepcopy(value['fields'])
            desired['state'] = 'OPEN'  # GitHub REST create is OPEN even for a requested CLOSED final state.
            return self.add_existing(value['id'], number, desired, member=False)
        return self.mutate('create_issue', action)

    def update_issue(self, repository, number, changes):
        def action():
            row = next(row for row in self.issues if row['issue_number'] == number)
            row['fields'].update(changes)
            return copy.deepcopy(row)
        return self.mutate('update_issue', action)

    def add_item(self, project_id, issue_node_id):
        def action():
            row = next(row for row in self.issues if row['node_id'] == issue_node_id)
            row['item_id'] = 'PI' + str(row['issue_number'])
            return row['item_id']
        return self.mutate('add_item', action)

    def update_fields(self, project_id, item_id, changes):
        assert len(changes) == 1
        def action():
            row = next(row for row in self.issues if row['item_id'] == item_id)
            row['fields'].update(changes)
        return self.mutate('update_fields', action)


class PlanSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'ASDG fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/example/client.git')
        self.write('README.md', 'Fixture project\n')
        self.write('.gitignore', '/.asdg/cache/\n')
        self.git('add', 'README.md', '.gitignore')
        self.git('commit', '-m', 'Fixture baseline')
        self.api = FakeGitHub()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def cache(self, items):
        value = empty_cache('example/client')
        value['items'] = items
        self.write(sync.CACHE, json.dumps(value, indent=2) + '\n')
        return value

    def read_cache(self):
        return json.loads((self.root / sync.CACHE).read_text())

    def files(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*')
                if '.git' not in path.relative_to(self.root).parts and path.is_file()}

    def preview(self, **kwargs):
        return sync.synchronize(self.root, api=self.api, **kwargs)

    def apply(self, **kwargs):
        preview = self.preview(**kwargs)
        self.assertEqual(preview['conflicts'], [])
        return sync.synchronize(self.root, api=self.api, apply=True, expected_plan=preview['plan'], **kwargs)

    def test_dry_run_changes_no_files_or_remote_records(self):
        self.cache([item()])
        self.write('docs/asdg/07-planning/03-plan.md', '# Plan\n\nKeep this narrative.\n')
        before = self.files()
        result = self.preview()
        self.assertIn('create_issue', [row['kind'] for row in result['operations']])
        self.assertEqual(self.files(), before)
        self.assertEqual(self.api.mutations, [])
        self.assertGreater(self.api.reads, 0)

    def test_first_sync_creates_project_fields_and_issue_then_converges(self):
        self.api = FakeGitHub(project=False)
        self.cache([item()])
        result = self.apply()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.api.mutations.count('create_project'), 1)
        self.assertEqual(self.api.mutations.count('create_field'), 4)
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        final = self.read_cache()['items'][0]
        self.assertEqual(final['fields'], fields())
        self.assertEqual(final['base'], final['fields'])
        self.assertEqual(final['notes'], 'Private local analysis')
        before, count = self.files(), len(self.api.mutations)
        self.assertEqual(self.apply()['status'], 'unchanged')
        self.assertEqual(self.files(), before)
        self.assertEqual(len(self.api.mutations), count)

    def test_new_closed_issue_is_created_open_then_closed_once(self):
        self.cache([item(state='CLOSED')])
        self.apply()
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual(self.api.mutations.count('update_issue'), 1)
        self.assertEqual(self.read_cache()['items'][0]['fields']['state'], 'CLOSED')
        self.assertEqual(self.api.issues[0]['fields']['state'], 'CLOSED')

    def test_import_create_and_independent_field_updates_preserve_notes(self):
        base = fields(title='Original', priority='Low')
        self.cache([item(), item('github:7', 7, base, title='Original', priority='High')])
        self.api.add_existing('github:7', 7, dict(base, title='Remote title'))
        self.api.add_existing('github:8', 8, fields(title='Remote only', state='CLOSED'), member=False)
        document = self.write('docs/asdg/07-planning/03-plan.md', '# Evidence\n\nDo not replace this.\n')
        self.apply()
        values = {row['id']: row for row in self.read_cache()['items']}
        self.assertEqual(set(values), {'PLAN-001', 'github:7', 'github:8'})
        self.assertEqual(values['github:7']['fields']['title'], 'Remote title')
        self.assertEqual(values['github:7']['fields']['priority'], 'High')
        self.assertEqual(values['github:7']['notes'], 'Private local analysis')
        self.assertEqual(document.read_text(), '# Evidence\n\nDo not replace this.\n')
        self.assertEqual(self.preview()['operations'], [])

    def test_bootstrap_dev_reads_cache_without_switching_branch_or_rewriting_docs(self):
        self.cache([item()])
        self.git('add', sync.CACHE)
        self.git('commit', '-m', 'Structured development plan')
        self.git('branch', 'dev')
        self.git('rm', sync.CACHE)
        self.git('commit', '-m', 'Fixture branch without a cache')
        head, branch, before = self.git('rev-parse', 'HEAD'), self.git('branch', '--show-current'), self.files()
        result = self.preview(bootstrap_ref='dev')
        self.assertEqual(result['bootstrap']['ref'], 'dev')
        self.assertEqual(self.files(), before)
        self.apply(bootstrap_ref='dev')
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.git('branch', '--show-current'), branch)
        self.assertEqual(self.read_cache()['items'][0]['id'], 'PLAN-001')
        with self.assertRaisesRegex(Conflict, 'absent local cache'):
            self.preview(bootstrap_ref='dev')

    def test_stale_local_and_remote_plans_make_no_mutations(self):
        self.cache([item()])
        result = self.preview()
        self.cache([item(title='Changed local')])
        before = self.files()
        with self.assertRaisesRegex(Conflict, 'Stale'):
            sync.synchronize(self.root, api=self.api, apply=True, expected_plan=result['plan'])
        self.assertEqual(self.files(), before)
        result = self.preview()
        self.api.add_existing('github:7', 7)
        with self.assertRaisesRegex(Conflict, 'Stale'):
            sync.synchronize(self.root, api=self.api, apply=True, expected_plan=result['plan'])
        self.assertEqual(self.api.mutations, [])

    def test_conflict_reports_both_changes_and_has_no_side_effects(self):
        base = fields()
        self.cache([item('github:7', 7, base, title='Local title')])
        self.api.add_existing('github:7', 7, fields(title='Remote title'))
        before = self.files()
        result = self.preview()
        self.assertEqual(result['status'], 'conflict')
        conflict = result['conflicts'][0]
        self.assertEqual((conflict['base'], conflict['local'], conflict['remote']), ('Task', 'Local title', 'Remote title'))
        with self.assertRaisesRegex(Conflict, 'conflicts'):
            sync.synchronize(self.root, api=self.api, apply=True, expected_plan=result['plan'])
        self.assertEqual(self.files(), before)
        self.assertEqual(self.api.mutations, [])

    def test_lost_create_response_resume_verifies_without_duplicate(self):
        self.cache([item()])
        self.api.fail_after = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        result = sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual(len(self.api.issues), 1)
        self.assertEqual(self.preview()['operations'], [])

    def test_unknown_create_outcome_is_never_blindly_retried(self):
        self.cache([item()])
        self.api.fail_before = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        for _ in range(2):
            with self.assertRaisesRegex(Conflict, 'Uncertain'):
                sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual(self.api.issues, [])
        self.assertIsNone(self.read_cache()['items'][0]['base'])

    def test_cache_edit_during_apply_is_preserved_and_stops_further_writes(self):
        self.cache([item()])
        def edit_after_creation(kind):
            if kind == 'create_issue':
                self.cache([item(title='Developer edit while request was running')])
        self.api.after_mutation = edit_after_creation
        with self.assertRaisesRegex(Conflict, 'Local cache'):
            self.apply()
        self.assertEqual(self.api.mutations, ['create_issue'])
        self.assertEqual(self.read_cache()['items'][0]['fields']['title'], 'Developer edit while request was running')
        with self.assertRaisesRegex(Conflict, 'Local cache changed'):
            sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(self.api.mutations, ['create_issue'])

    def test_origin_mismatch_fails_before_api_or_local_mutation(self):
        before = self.files()
        with self.assertRaisesRegex(Conflict, 'origin'):
            self.preview(repository='other/repo')
        self.assertEqual(self.api.reads, 0)
        self.assertEqual(self.files(), before)

    def test_symlinked_and_hardlinked_cache_are_rejected(self):
        value = empty_cache('example/client')
        outside = self.write('external-plan.json', json.dumps(value))
        target = self.root / sync.CACHE
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        with self.assertRaisesRegex(Conflict, 'symlink'):
            self.preview()
        target.unlink()
        os.link(outside, target)
        with self.assertRaisesRegex(Conflict, 'single-link'):
            self.preview()
        self.assertEqual(self.api.reads, 0)
        self.assertEqual(outside.read_text(), json.dumps(value))

    def test_cache_publication_crash_can_complete_without_repeating_remote_writes(self):
        self.cache([item()])
        original_write = sync.write
        def fail_final_journal(root, name, value):
            if name == sync.JOURNAL and value.get('state') == 'complete':
                raise Interrupted('Lost local journal completion')
            return original_write(root, name, value)
        with patch.object(sync, 'write', side_effect=fail_final_journal):
            with self.assertRaises(Interrupted):
                self.apply()
        self.assertIsNotNone(self.read_cache()['items'][0]['base'])
        mutations, reads = list(self.api.mutations), self.api.reads
        result = sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(self.api.mutations, mutations)
        self.assertGreater(self.api.reads, reads, 'Recovery must verify current remote state before claiming completion')
        self.assertEqual(json.loads((self.root / sync.JOURNAL).read_text())['state'], 'complete')

    def test_resume_refuses_changed_worktree_revision(self):
        self.cache([item()])
        self.api.fail_after = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        self.git('commit', '--allow-empty', '-m', 'Concurrent commit')
        count = len(self.api.mutations)
        with self.assertRaisesRegex(Conflict, 'revision changed'):
            sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(len(self.api.mutations), count)

    def test_missing_cache_preview_exposes_existing_issue_identity_without_creates(self):
        self.api.add_existing('github:7', 7, fields(title='Show welcome screen'))
        before = self.files()
        result = self.preview()
        candidate = result['cache_preview']['items'][0]
        self.assertEqual((candidate['id'], candidate['issue_number']), ('github:7', 7))
        self.assertEqual(candidate['base'], candidate['fields'])
        self.assertFalse(any(row['kind'] == 'create_issue' for row in result['operations']))
        self.assertEqual(self.files(), before)
        self.assertEqual(self.api.mutations, [])

    def test_definite_rejection_can_resume_after_permission_is_fixed(self):
        self.cache([item()])
        self.api.reject_once = 'create_issue'
        with self.assertRaises(GitHubRejected):
            self.apply()
        journal = json.loads((self.root / sync.JOURNAL).read_text())
        self.assertIsNone(journal['pending'])
        self.assertEqual(self.api.issues, [])
        sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual(len(self.api.issues), 1)
        self.assertEqual(self.api.mutations.count('create_issue'), 2)  # One rejection, one successful create.

    def test_abandon_preserves_edited_cache_and_partial_remote_results(self):
        self.cache([item()])
        self.api.fail_after = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        original = json.loads((self.root / sync.JOURNAL).read_text())
        self.cache([item(title='Developer reconciliation')])
        local = (self.root / sync.CACHE).read_bytes()
        remote = copy.deepcopy(self.api.issues)
        with self.assertRaisesRegex(Conflict, 'exact original'):
            sync.synchronize(self.root, api=self.api, abandon=True, expected_plan='wrong')
        result = sync.synchronize(self.root, api=self.api, abandon=True, expected_plan=original['plan'])
        self.assertEqual(result['status'], 'abandoned')
        self.assertTrue((self.root / result['archive']).is_file())
        self.assertEqual((self.root / sync.CACHE).read_bytes(), local)
        self.assertEqual(self.api.issues, remote)
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual(self.preview()['status'], 'conflict')

    def test_abandon_after_visible_create_allows_safe_new_plan_without_duplicate(self):
        self.cache([item()])
        self.api.fail_after = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        original = json.loads((self.root / sync.JOURNAL).read_text())
        sync.synchronize(self.root, api=self.api, abandon=True, expected_plan=original['plan'])
        self.apply()
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual(self.read_cache()['items'][0]['base'], fields())

    def test_unknown_create_cannot_be_abandoned_to_enable_blind_retry(self):
        self.cache([item()])
        self.api.fail_before = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        original = json.loads((self.root / sync.JOURNAL).read_text())
        with self.assertRaisesRegex(Conflict, 'unobserved write'):
            sync.synchronize(self.root, api=self.api, abandon=True, expected_plan=original['plan'])
        self.assertEqual(json.loads((self.root / sync.JOURNAL).read_text())['state'], 'running')
        self.assertEqual(self.api.mutations.count('create_issue'), 1)

    def test_explicit_uncertainty_acknowledgement_archives_without_replaying(self):
        self.cache([item()])
        self.api.fail_before = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        original = json.loads((self.root / sync.JOURNAL).read_text())
        cache = (self.root / sync.CACHE).read_bytes()
        result = sync.synchronize(self.root, api=self.api, abandon=True,
                                  expected_plan=original['plan'], acknowledge_uncertain=True)
        archived = json.loads((self.root / result['archive']).read_text())
        self.assertTrue(archived['uncertain_outcome_acknowledged'])
        self.assertIsNotNone(archived['pending'])
        self.assertEqual(result['status'], 'abandoned')
        self.assertEqual(self.api.mutations.count('create_issue'), 1)
        self.assertEqual((self.root / sync.CACHE).read_bytes(), cache)
        with self.assertRaisesRegex(Conflict, 'only valid'):
            sync.synchronize(self.root, api=self.api, acknowledge_uncertain=True)

    def test_resume_does_not_enroll_new_issue_outside_reviewed_plan(self):
        self.cache([item()])
        self.api.fail_after = 'create_issue'
        with self.assertRaises(Interrupted):
            self.apply()
        outsider = self.api.add_existing('github:99', 99, fields(title='Created later'), member=False)
        with self.assertRaisesRegex(Conflict, 'outside the reviewed plan'):
            sync.synchronize(self.root, api=self.api, resume=True)
        self.assertIsNone(outsider['item_id'])
        self.assertEqual(self.api.mutations.count('create_issue'), 1)

    def test_publication_recovery_refuses_changed_remote_without_overwriting_cache(self):
        self.cache([item()])
        original_write = sync.write
        def fail_final_journal(root, name, value):
            if name == sync.JOURNAL and value.get('state') == 'complete':
                raise Interrupted('Journal completion lost')
            return original_write(root, name, value)
        with patch.object(sync, 'write', side_effect=fail_final_journal):
            with self.assertRaises(Interrupted):
                self.apply()
        published = (self.root / sync.CACHE).read_bytes()
        self.api.issues[0]['fields']['title'] = 'Concurrent remote edit'
        mutations = list(self.api.mutations)
        with self.assertRaisesRegex(Conflict, 'after cache publication'):
            sync.synchronize(self.root, api=self.api, resume=True)
        self.assertEqual((self.root / sync.CACHE).read_bytes(), published)
        self.assertEqual(self.api.mutations, mutations)

    def test_cache_only_publication_rechecks_git_binding(self):
        self.api.add_existing('github:7', 7)
        preview = self.preview()
        original_snapshot = self.api.snapshot
        original_write = sync.write
        started = False
        changed = False
        def observe_journal(root, name, value):
            nonlocal started
            result = original_write(root, name, value)
            if name == sync.JOURNAL and value.get('state') == 'running':
                started = True
            return result
        def concurrent_commit(repository, config):
            nonlocal changed
            result = original_snapshot(repository, config)
            if started and not changed:
                changed = True
                self.git('commit', '--allow-empty', '-m', 'Concurrent revision during pull-only sync')
            return result
        with patch.object(sync, 'write', side_effect=observe_journal), \
                patch.object(self.api, 'snapshot', side_effect=concurrent_commit):
            with self.assertRaisesRegex(Conflict, 'before cache publication'):
                sync.synchronize(self.root, api=self.api, apply=True, expected_plan=preview['plan'])
        self.assertFalse((self.root / sync.CACHE).exists())
        self.assertEqual(self.api.mutations, [])

    def test_cache_utility_exception_is_exact_and_requires_known_role(self):
        from cli_ownership import ownership_decision
        context = {'role_id': 'ASDG-05', 'workflow': 'project-plan-sync', 'targets': [sync.CACHE]}
        allowed, _, application = ownership_decision(self.root, [sync.CACHE], context, repo=ROOT)
        self.assertTrue(allowed)
        self.assertEqual(application, [])
        for path in ['docs/asdg/07-planning/neighbor.json', '.asdg/sprint.json']:
            changed = dict(context, targets=[path])
            self.assertFalse(ownership_decision(self.root, [path], changed, repo=ROOT)[0], path)
        self.assertFalse(ownership_decision(self.root, [sync.CACHE], dict(context, role_id='Unknown'), repo=ROOT)[0])


if __name__ == '__main__':
    unittest.main()
