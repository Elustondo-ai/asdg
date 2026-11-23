"""Host identity and run-claim acquisition against disposable Git projects and a fixture host path only."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
LIB = str(Path(__file__).resolve().parents[1] / 'scripts/lib')
sys.path.insert(0, LIB)
import cli_team_claim
from cli_files import Conflict
from cli_team_claim import (acquire, check_run, default_host_path, describe_suspects, host_preview, host_setup,
                            new_host_id, new_run_id, read_claim, read_host, recover, recover_preview, release,
                            release_preview, start_preview, validate_claim)
import cli_team_store
from cli_team_store import CLAIM, LOCK, SPECS, project, spec_bytes
from test_team_model import ROLES
from test_team_store import IDS, git, snapshot, team

STAMP, SESSION = '2026-11-14T20:00:00Z', '0f3c9a52-7b1e-4c7d-9a61-2f6f0c1d8e44'
HOST, RUN = 'host-' + '1' * 32, 'run-' + '2' * 16
LATER, RUN_B, RUN_C, OTHER = '2026-11-14T21:00:00Z', 'run-' + '3' * 16, 'run-' + '4' * 16, 'a81d4fae-7dec-41d0-a765-00a0c91e6bf6'
RULES = dict(role_ids=ROLES, coordinator='ASDG-COORDINATOR')
CHILD = '''
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import cli_team_claim as claim
a = json.loads(sys.argv[2])
options = dict(goal='Review the architecture.', owner_session=a['session'], run_id=a['run'], started_at=a['stamp'],
               host_path=Path(a['host']), role_ids=set(a['roles']), coordinator='ASDG-COORDINATOR')
token = claim.start_preview(Path(a['root']), a['team'], **options)['token']
Path(a['ready']).touch()
while not Path(a['go']).exists():
    time.sleep(0.005)
try:
    print(claim.acquire(Path(a['root']), a['team'], token, **options)['run_id'])
except claim.Conflict as error:
    print('CONFLICT', error)
'''
import os
os.environ.setdefault('ASDG_OPENSPEC', '0')  # Hermetic: setup's OpenSpec step would run a separately installed command.


class TeamClaimTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-team-claim-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name).resolve()
        self.root = self.area / 'client'
        (self.root / SPECS).mkdir(parents=True)
        git(self.root, 'init', '-q')
        (self.root / '.asdg/project.json').write_text(json.dumps({'project_id': 'client-project'}))
        for kind, name, team_id in zip(('sessions', 'subagents'), ('Alpha', 'Beta'), IDS):
            (self.root / SPECS / (team_id + '.json')).write_bytes(spec_bytes(team(kind, name, team_id)))
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'Seed')
        self.host = self.area / 'host-state/asdg/host-id.json'  # A fixture; never the real user location.
        self.common = self.root / '.git'
        self.claim = self.common / CLAIM

    def read_only(self, call):
        before = snapshot(self.area)
        try:
            return call()
        finally:
            self.assertEqual(snapshot(self.area), before)

    def make_host(self, host_id=HOST):
        token = host_preview(self.host, root=self.root, host_id=host_id, created_at=STAMP)['token']
        return host_setup(self.host, token, root=self.root, host_id=host_id, created_at=STAMP)

    def options(self, **changes):
        return dict(dict(goal='Review the architecture.', owner_session=SESSION, run_id=RUN, started_at=STAMP,
                         host_path=self.host, role_ids=ROLES, coordinator='ASDG-COORDINATOR'), **changes)

    def look(self, team_id=IDS[0], root=None, **changes):
        return self.read_only(lambda: start_preview(root or self.root, team_id, **self.options(**changes)))

    def codes(self, result):
        self.assertEqual((result['outcome'], result['token'], result['bytes']), ('CONFLICT', None, None))
        return {conflict['code'] for conflict in result['conflicts']}

    def test_host_preview_is_read_only_and_setup_creates_then_preserves(self):
        look = lambda **changes: self.read_only(lambda: host_preview(
            self.host, root=self.root, **dict(dict(host_id=HOST, created_at=STAMP), **changes)))
        first = look()
        self.assertEqual((first, first['outcome'], first['host_id']), (look(), 'READY', HOST))
        tokens = {first['token'], look(host_id=new_host_id())['token'], look(created_at='2026-11-15T00:00:00Z')['token'],
                  self.read_only(lambda: host_preview(self.area / 'other/host-id.json', root=self.root, host_id=HOST,
                                                      created_at=STAMP))['token']}
        self.assertEqual(len(tokens), 4)
        self.assertFalse(self.host.parent.exists())
        for stale in (None, 'x', look(host_id=new_host_id())['token']):
            with self.assertRaises(Conflict):
                self.read_only(lambda: host_setup(self.host, stale, root=self.root, host_id=HOST, created_at=STAMP))
        self.assertEqual(self.make_host()['outcome'], 'CREATED')
        saved = self.host.read_bytes()
        self.assertEqual((saved, self.host.stat().st_mode & 0o777), (first['bytes'], 0o600))
        self.assertEqual(self.read_only(lambda: read_host(self.host, root=self.root))['host_id'], HOST)
        other = new_host_id()
        kept = look(host_id=other)  # A second proposal never replaces the existing identity.
        self.assertEqual((kept['outcome'], kept['host_id'], kept['token']), ('UNCHANGED', HOST, None))
        with self.assertRaises(Conflict):
            host_setup(self.host, first['token'], root=self.root, host_id=HOST, created_at=STAMP)
        self.assertEqual(self.host.read_bytes(), saved)

    def test_malformed_unknown_symlinked_or_misplaced_identity_is_refused(self):
        self.host.parent.mkdir(parents=True)
        good = spec_bytes({'schema_version': 1, 'kind': 'asdg-host-identity', 'host_id': HOST, 'created_at': STAMP})
        bad = {'malformed': b'{', 'unknown version': good.replace(b'"schema_version": 1', b'"schema_version": 2'),
               'unknown field': spec_bytes(dict(json.loads(good), note='x')), 'reformatted': json.dumps(json.loads(good)).encode(),
               'bad id': good.replace(HOST.encode(), b'my-laptop')}
        for label, data in bad.items():
            with self.subTest(case=label):
                self.host.write_bytes(data)
                seen = self.read_only(lambda: host_preview(self.host, root=self.root, host_id=HOST, created_at=STAMP))
                self.assertEqual((seen['outcome'], seen['found']['state'], seen['token'], seen['host_id']),
                                 ('CONFLICT', 'INVALID', None, None))
                self.assertEqual(self.codes(self.look()), {'HOST_IDENTITY_INVALID'})
                self.assertEqual(self.host.read_bytes(), data)  # Never repaired or regenerated.
        self.host.unlink()
        (self.area / 'elsewhere.json').write_bytes(good)
        self.host.symlink_to(self.area / 'elsewhere.json')
        self.assertEqual(read_host(self.host, root=self.root)['state'], 'UNSAFE')
        self.assertEqual(self.codes(self.look()), {'HOST_IDENTITY_UNSAFE'})
        self.host.unlink()
        self.assertEqual(self.codes(self.look()), {'HOST_IDENTITY_NONE'})
        (self.area / 'link').symlink_to(self.host.parent, target_is_directory=True)
        misplaced = (Path('host-id.json'), self.root / 'host-id.json', self.common / 'asdg/host-id.json',
                     self.area / 'host.json', self.area / 'link/host-id.json', self.area / 'x/../host-id.json',
                     Path('/Users/someone/Library/CloudStorage/Drive/asdg/host-id.json'),
                     Path('/Users/someone/Dropbox/asdg/host-id.json'))
        for path in misplaced:
            with self.assertRaises(Conflict, msg=str(path)):
                self.read_only(lambda: host_preview(path, root=self.root, host_id=HOST, created_at=STAMP))
        self.assertNotIn(str(self.area), str(default_host_path()))
        self.assertEqual(default_host_path().name, 'host-id.json')

    def test_first_claim_succeeds_and_any_second_run_is_refused(self):
        self.make_host()
        seen = self.look()
        self.assertEqual((seen, seen['outcome'], seen['runtime']), (self.look(), 'READY', 'NOT_OBSERVED'))
        self.assertFalse((self.common / 'asdg').exists())
        done = acquire(self.root, IDS[0], seen['token'], **self.options())
        self.assertEqual((done['outcome'], done['generation'], done['runtime']), ('ACQUIRED', 1, 'NOT_OBSERVED'))
        self.assertEqual((self.claim.read_bytes(), self.claim.stat().st_mode & 0o777), (seen['bytes'], 0o600))
        claim = read_claim(self.common)['claim']
        row = {'spec_sha256': claim['spec_sha256'], 'spec_revision': claim['spec_revision']}
        self.assertEqual(row, {'spec_sha256': seen['evidence']['team']['sha256'], 'spec_revision': 1})
        self.assertEqual({key: claim[key] for key in ('run_id', 'team_id', 'host_id', 'owner_session', 'owner_evidence',
                                                      'state', 'goal', 'worktree', 'git_common_dir', 'project_id')},
                         {'run_id': RUN, 'team_id': IDS[0], 'host_id': HOST, 'owner_session': SESSION,
                          'owner_evidence': 'UNCORRELATED', 'state': 'ACTIVE', 'goal': 'Review the architecture.',
                          'worktree': str(self.root), 'git_common_dir': str(self.common), 'project_id': 'client-project'})
        for team_id in IDS[:2]:  # The same team again, or another team: one managed run per project.
            again = self.look(team_id, run_id=new_run_id())
            self.assertEqual(self.codes(again), {'CLAIM_EXISTS'})
            self.assertEqual(again['conflicts'][0]['run_id'], RUN)
        with self.assertRaisesRegex(Conflict, 'already claimed: run ' + RUN):
            acquire(self.root, IDS[1], seen['token'], **self.options(run_id=new_run_id()))
        self.assertEqual(self.claim.read_bytes(), seen['bytes'])

    def test_two_linked_worktrees_compete_in_separate_processes(self):
        self.make_host()
        linked = self.area / 'linked'
        git(self.root, 'worktree', 'add', '-q', '-b', 'linked', str(linked))
        self.assertEqual(project(linked)['git_common_dir'], project(self.root)['git_common_dir'])
        go, children = self.area / 'go', []
        for index, root in enumerate((self.root, linked, self.root, linked)):
            options = {'root': str(root), 'team': IDS[index % 2], 'session': SESSION[:-1] + str(index), 'stamp': STAMP,
                       'run': 'run-%016x' % index, 'host': str(self.host), 'roles': sorted(ROLES),
                       'ready': str(self.area / ('ready-%d' % index)), 'go': str(go)}
            children.append((options, subprocess.Popen([sys.executable, '-B', '-c', CHILD, LIB, json.dumps(options)],
                                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
        deadline = time.monotonic() + 60
        while not all(Path(options['ready']).exists() for options, _ in children) and time.monotonic() < deadline:
            time.sleep(0.01)
        go.touch()
        outputs = [child.communicate(timeout=60) for _, child in children]
        lines = [out.strip() for out, _ in outputs]
        winners = [line for line in lines if line.startswith('run-')]
        self.assertEqual((len(winners), sum(line.startswith('CONFLICT') for line in lines)), (1, 3), outputs)
        found = read_claim(self.common)
        self.assertEqual((found['state'], found['claim']['run_id'], found['suspects']), ('CLAIMED', winners[0], []))
        self.assertFalse((linked / '.git').is_dir())  # The linked worktree has no Git directory of its own.

    def test_missing_or_literal_owner_session_and_malformed_inputs_are_refused(self):
        self.make_host()
        sessions = (None, '', '   ', '${CLAUDE_SESSION_ID}', '$CLAUDE_SESSION_ID', 'CLAUDE_SESSION_ID', 'session-id',
                    'unknown-session', 'abc', 'has space in it', 'aaaaaaaaaaaa', 42)
        bad = [dict(owner_session=value) for value in sessions] + [
            dict(run_id='run-1'), dict(run_id=None), dict(started_at='2026-99-99T99:99:99Z'), dict(goal=''),
            dict(goal='two\nlines'), dict(goal=' padded '), dict(goal=None)]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(Conflict):
                self.look(**changes)
        for team_id in ('team-ffffffffffffffff', '../x', None):
            with self.assertRaisesRegex(Conflict, 'saved, valid team'):
                self.look(team_id)
        (self.root / SPECS / (IDS[1] + '.json')).write_bytes(b'{')
        with self.assertRaisesRegex(Conflict, 'saved, valid team'):
            self.look(IDS[1])
        for field, value in (('generation', 0), ('generation', True), ('schema_version', 1.0), ('state', 'RUNNING'),
                             ('owner_evidence', 'VERIFIED'), ('spec_sha256', 'abc'), ('extra', 1)):
            with self.subTest(field=field), self.assertRaises(Conflict):
                validate_claim(dict(self.look()['claim'], **{field: value}))
        self.assertFalse((self.common / 'asdg').exists())

    def test_stale_tokens_unreadable_claims_and_symlinks_block_a_start(self):
        self.make_host()
        token = self.look()['token']
        for bad in (None, 'team-start-preview-1.zz', token.upper()):
            with self.assertRaises(Conflict):
                self.read_only(lambda: acquire(self.root, IDS[0], bad, **self.options()))
        changed = (self.options(goal='Another goal.'), self.options(run_id=new_run_id()),
                   self.options(owner_session=SESSION[:-1] + 'f'), self.options(role_ids=ROLES | {'ASDG-99'}))
        for options in changed:
            with self.assertRaisesRegex(Conflict, 'preview changed'):
                acquire(self.root, IDS[0], token, **options)
        spec_file = self.root / SPECS / (IDS[0] + '.json')
        original = spec_file.read_bytes()
        spec_file.write_bytes(spec_bytes(team('sessions', 'Alpha', IDS[0], purpose='Edited after the preview.')))
        with self.assertRaisesRegex(Conflict, 'preview changed'):
            acquire(self.root, IDS[0], token, **self.options())
        spec_file.write_bytes(original)
        self.assertFalse(self.claim.exists())
        self.assertEqual(sorted(item.name for item in self.claim.parent.iterdir()), [LOCK.name])  # Only the reused lock.
        outside = self.area / 'outside'
        outside.mkdir()
        blockers = {'conflict copy': ('active-run (1).json', b'{}', 'CLAIM_FOLDER_SUSPECT'),
                    'leftover': ('.asdg-tmp-abc', b'', 'CLAIM_FOLDER_SUSPECT'),
                    'malformed claim': (CLAIM.name, b'{', 'CLAIM_UNREADABLE'),
                    'reformatted claim': (CLAIM.name, json.dumps(self.look()['claim']).encode(), 'CLAIM_UNREADABLE'),
                    'foreign shape': (CLAIM.name, b'{"run": "someone else"}\n', 'CLAIM_UNREADABLE')}
        for label, (name, data, code) in blockers.items():
            with self.subTest(case=label):
                (self.claim.parent / name).write_bytes(data)
                self.assertEqual(self.codes(self.look()), {code})
                with self.assertRaises(Conflict):
                    acquire(self.root, IDS[0], token, **self.options())
                self.assertEqual((self.claim.parent / name).read_bytes(), data)
                (self.claim.parent / name).unlink()
        self.claim.symlink_to(outside / 'claim.json')
        self.assertEqual(self.codes(self.look()), {'CLAIM_UNSAFE'})
        self.claim.unlink()
        (self.claim.parent / LOCK.name).unlink()
        self.claim.parent.rmdir()
        self.claim.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(Conflict):
            self.look()
        with self.assertRaises(Conflict):
            acquire(self.root, IDS[0], token, **self.options())
        self.assertEqual(list(outside.iterdir()), [])

    def test_an_ordinary_failure_leaves_no_claim_and_the_token_still_works(self):
        self.make_host()
        token, host = self.look()['token'], self.host.read_bytes()
        real, calls = cli_team_claim.read_claim, []

        def failing(common):
            calls.append(1)
            if len(calls) == 2:  # The first call is the recheck under the lock; the second is the read-back.
                raise RuntimeError('injected read-back failure')
            return real(common)

        with mock.patch.object(cli_team_claim, 'read_claim', failing), self.assertRaisesRegex(RuntimeError, 'injected'):
            acquire(self.root, IDS[0], token, **self.options())
        self.assertEqual((read_claim(self.common)['state'], sorted(item.name for item in self.claim.parent.iterdir())),
                         ('NONE', [LOCK.name]))
        self.assertEqual(self.host.read_bytes(), host)
        self.assertEqual(acquire(self.root, IDS[0], token, **self.options())['outcome'], 'ACQUIRED')

    def begin(self, **changes):
        options = self.options(**changes)
        return acquire(self.root, IDS[0], start_preview(self.root, IDS[0], **options)['token'], **options)

    def end(self, **changes):
        return dict(dict(run_id=RUN, generation=1, session=SESSION, ended_at=LATER, host_path=self.host), **changes)

    def ending(self, preview, root=None, **changes):
        return self.read_only(lambda: preview(root or self.root, **self.end(**changes)))

    def test_release_leaves_a_tombstone_and_old_start_tokens_never_replay(self):
        self.make_host()
        first, other = self.options(), self.options(run_id=RUN_B)
        token_a, token_b = (start_preview(self.root, IDS[0], **item)['token'] for item in (first, other))
        self.assertEqual(acquire(self.root, IDS[0], token_a, **first)['generation'], 1)
        self.assertEqual([check_run(self.root, *pair)['outcome'] for pair in ((RUN, 1), (RUN, 2), (RUN_B, 1))],
                         ['CURRENT', 'STALE', 'STALE'])
        self.assertEqual(self.codes(self.ending(release_preview, generation=2)), {'STALE_RUN'})
        self.assertEqual(self.codes(self.ending(release_preview, run_id=RUN_B)), {'STALE_RUN'})
        self.assertEqual(self.codes(self.ending(release_preview, ended_at='2026-11-14T19:00:00Z')), {'ENDS_BEFORE_START'})
        ready = self.ending(release_preview)
        self.assertEqual((ready, ready['outcome'], ready['standing']), (self.ending(release_preview), 'READY', 'OWNER_FIELDS_MATCH'))
        active = self.claim.read_bytes()
        for stale in (None, 'x', ready['token'][:-1] + ('0' if ready['token'][-1] != '0' else '1')):
            with self.assertRaises(Conflict):
                release(self.root, stale, **self.end())
        with self.assertRaises(Conflict):
            release(self.root, ready['token'], **self.end(ended_at='2026-11-14T22:00:00Z'))
        self.assertEqual(self.claim.read_bytes(), active)
        done = release(self.root, ready['token'], **self.end())
        self.assertEqual((done['outcome'], done['generation'], done['liveness']), ('RELEASED', 1, 'NOT_ENFORCED'))
        tombstone = self.claim.read_bytes()
        self.assertEqual((tombstone, read_claim(self.common)['state']), (ready['bytes'], 'RELEASED'))
        self.assertEqual(json.loads(tombstone)['end_evidence'], 'OWNER_FIELDS_MATCH_UNCORRELATED')
        self.assertEqual(check_run(self.root, RUN, 1)['outcome'], 'STALE')
        self.assertEqual(self.codes(self.ending(release_preview)), {'NOT_ACTIVE'})
        for token, options in ((token_a, first), (token_b, other)):  # Tokens issued before the run existed.
            with self.assertRaises(Conflict):
                acquire(self.root, IDS[0], token, **options)
        self.assertEqual(self.codes(self.look()), {'RUN_ID_REUSED'})
        self.assertEqual(self.claim.read_bytes(), tombstone)
        token_c = start_preview(self.root, IDS[0], **self.options(run_id=RUN_C))['token']  # Bound to tombstone 1.
        again = self.look(run_id=RUN_B)
        self.assertEqual((again['outcome'], again['claim']['generation']), ('READY', 2))
        self.assertEqual(self.begin(run_id=RUN_B)['generation'], 2)
        self.assertEqual(self.codes(self.ending(release_preview)), {'STALE_RUN'})  # The first run's owner.
        end_b = self.end(run_id=RUN_B, generation=2)
        release(self.root, release_preview(self.root, **end_b)['token'], **end_b)
        with self.assertRaises(Conflict):  # A start approved against the first tombstone.
            acquire(self.root, IDS[0], token_c, **self.options(run_id=RUN_C))
        self.assertEqual(self.look(run_id=RUN_C)['claim']['generation'], 3)

    def test_release_needs_matching_owner_fields_and_recovery_needs_the_exact_phrase(self):
        self.make_host()
        self.begin()
        owner_token = release_preview(self.root, **self.end())['token']
        tree = self.area / 'second tree'
        git(self.root, 'worktree', 'add', '-q', str(tree), '-b', 'second')
        elsewhere, stranger = self.ending(release_preview, root=tree), self.ending(release_preview, session=OTHER)
        self.assertEqual((self.codes(elsewhere), elsewhere['standing']), ({'NOT_OWNER'}, 'OTHER_WORKTREE'))
        self.assertEqual((self.codes(stranger), stranger['standing']), ({'NOT_OWNER'}, 'OTHER_SESSION'))
        self.assertEqual(self.codes(self.ending(recover_preview)), {'OWNER_USES_RELEASE'})
        asked = self.ending(recover_preview, session=OTHER)
        phrase = asked['confirmation_expected']
        self.assertEqual(self.codes(asked), {'CONFIRMATION_REQUIRED'})
        self.assertEqual(phrase, f'RECOVER OTHER_SESSION RUN {RUN} GENERATION 1 HOST {HOST}')
        for wrong in ('yes', phrase.lower(), phrase + ' ', phrase.replace('OTHER_SESSION', 'OTHER_WORKTREE')):
            self.assertEqual(self.codes(self.ending(recover_preview, session=OTHER, confirmation=wrong)),
                             {'CONFIRMATION_REQUIRED'})
        self.assertEqual(self.codes(self.ending(recover_preview, session=OTHER, confirmation=phrase, generation=2)),
                         {'STALE_RUN'})
        ready = self.ending(recover_preview, session=OTHER, confirmation=phrase)
        self.assertEqual((ready['outcome'], ready['supplied_unverified']['basis']), ('READY', 'HUMAN_DECLARED_UNVERIFIED'))
        active = self.claim.read_bytes()
        for changes in (dict(session=OTHER), dict(session=OTHER, confirmation='yes'), dict(confirmation=phrase)):
            with self.assertRaises(Conflict):  # The token alone, without the same phrase and session, ends nothing.
                recover(self.root, ready['token'], **self.end(**changes))
        with self.assertRaises(Conflict):  # A release token is not a recovery token.
            recover(self.root, owner_token, **self.end(session=OTHER, confirmation=phrase))
        self.assertEqual(self.claim.read_bytes(), active)
        done = recover(self.root, ready['token'], **self.end(session=OTHER, confirmation=phrase))
        self.assertEqual((done['outcome'], done['standing'], done['runtime'], done['liveness']),
                         ('RECOVERED', 'OTHER_SESSION', 'NOT_OBSERVED', 'NOT_ENFORCED'))
        saved = json.loads(self.claim.read_bytes())
        self.assertEqual((saved['state'], saved['end_kind'], saved['end_evidence'], saved['ended_by_session'], saved['owner_session']),
                         ('RELEASED', 'RECOVERY', 'HUMAN_DECLARED_UNVERIFIED', OTHER, SESSION))
        with self.assertRaises(Conflict):  # The recovered owner's own approved release arrives late.
            release(self.root, owner_token, **self.end())
        self.assertEqual((check_run(self.root, RUN, 1)['outcome'], self.codes(self.ending(release_preview))),
                         ('STALE', {'NOT_ACTIVE'}))
        self.assertEqual(self.look(run_id=RUN_B, root=tree)['claim']['generation'], 2)

    def test_foreign_hosts_missing_identity_and_conflict_copies_are_conservative(self):
        self.make_host()
        self.begin()
        away, missing = self.area / 'other-host/asdg/host-id.json', self.area / 'no-host/asdg/host-id.json'
        other_host = 'host-' + '9' * 32
        host_setup(away, host_preview(away, root=self.root, host_id=other_host, created_at=STAMP)['token'],
                   root=self.root, host_id=other_host, created_at=STAMP)
        foreign = self.ending(release_preview, host_path=away)
        self.assertEqual((self.codes(foreign), foreign['standing']), ({'NOT_OWNER'}, 'FOREIGN_HOST'))
        asked = self.ending(recover_preview, host_path=away)
        phrase = asked['confirmation_expected']
        self.assertEqual(phrase, f'RECOVER FOREIGN_HOST RUN {RUN} GENERATION 1 HOST {HOST}')
        local = phrase.replace('FOREIGN_HOST', 'OTHER_SESSION')
        self.assertEqual(self.codes(self.ending(recover_preview, host_path=away, confirmation=local)), {'CONFIRMATION_REQUIRED'})
        for preview in (release_preview, recover_preview):  # No identity: nothing can be compared, so nothing ends.
            unknown = self.ending(preview, host_path=missing, confirmation=phrase) if preview is recover_preview \
                else self.ending(preview, host_path=missing)
            self.assertIn('HOST_IDENTITY_NONE', self.codes(unknown))
            self.assertEqual(unknown['standing'], 'HOST_UNKNOWN')
        ready = self.ending(recover_preview, host_path=away, confirmation=phrase)
        self.assertEqual(ready['outcome'], 'READY')
        active = self.claim.read_bytes()
        copies = {'active-run (1).json': spec_bytes(dict(json.loads(active), run_id=RUN_B)),
                  '.asdg-tmp-active-run.json-1': b'partial', 'notes.txt': b'kept'}
        for name, data in copies.items():
            (self.claim.parent / name).write_bytes(data)
            rows = self.read_only(lambda: describe_suspects(self.common))
            self.assertEqual([row['file'] for row in rows], [name])
            self.assertEqual((rows[0]['kind'], (rows[0]['claim'] or {}).get('run_id')),
                             {'a': ('CONFLICT_COPY', RUN_B), '.': ('TEMPORARY_LEFTOVER', None), 'n': ('UNKNOWN', None)}[name[0]])
            self.assertEqual(check_run(self.root, RUN, 1)['outcome'], 'UNPROVEN')
            self.assertEqual(self.codes(self.ending(release_preview)), {'CLAIM_FOLDER_SUSPECT'})
            self.assertEqual(self.codes(self.ending(recover_preview, host_path=away, confirmation=phrase)),
                             {'CLAIM_FOLDER_SUSPECT'})
            self.assertIn('CLAIM_FOLDER_SUSPECT', self.codes(self.look(run_id=RUN_C)))
            with self.assertRaises(Conflict):
                recover(self.root, ready['token'], **self.end(host_path=away, confirmation=phrase))
            self.assertEqual(((self.claim.parent / name).read_bytes(), self.claim.read_bytes()), (data, active))
            (self.claim.parent / name).unlink()
        self.assertEqual(recover(self.root, ready['token'], **self.end(host_path=away, confirmation=phrase))['standing'],
                         'FOREIGN_HOST')
        self.assertEqual(json.loads(self.claim.read_bytes())['ended_by_host'], other_host)
        (self.claim.parent / 'active-run (1).json').write_bytes(active)  # A late copy of the ended run syncs in.
        self.assertIn('CLAIM_FOLDER_SUSPECT', self.codes(self.look(run_id=RUN_B)))
        (self.claim.parent / 'active-run (1).json').unlink()
        self.claim.write_text('{"state": "RELEASED"}\n')
        self.assertEqual(self.codes(self.ending(release_preview)), {'CLAIM_UNREADABLE'})
        self.assertEqual(self.codes(self.look(run_id=RUN_B)), {'CLAIM_UNREADABLE'})
        self.claim.unlink()
        self.assertEqual(self.codes(self.ending(release_preview)), {'NO_CLAIM'})

    def test_an_inactive_tombstone_stops_blocking_configuration(self):
        self.make_host()
        gamma = 'team-' + 'c' * 16
        first = team('sessions', 'Gamma', gamma)
        cli_team_store.apply(self.root, first, cli_team_store.preview(self.root, first, **RULES)['token'], **RULES)
        revised = dict(first, purpose='A revised purpose.', revision=2)
        look = lambda: self.read_only(lambda: cli_team_store.preview(self.root, revised, **RULES))
        self.assertEqual(look()['outcome'], 'READY')
        early = look()['token']
        self.begin()
        self.assertEqual({item['code'] for item in look()['conflicts']}, {'RUN_STATE_UNPROVEN'})
        release(self.root, release_preview(self.root, **self.end())['token'], **self.end())
        idle = look()
        self.assertEqual((idle['outcome'], idle['evidence']['run']['state']), ('READY', 'INACTIVE'))
        self.assertNotEqual(idle['token'], early)  # The claim's history is part of what was approved.
        (self.claim.parent / 'active-run (1).json').write_bytes(b'{}')
        self.assertEqual({item['code'] for item in look()['conflicts']}, {'RUN_STATE_UNPROVEN'})
        (self.claim.parent / 'active-run (1).json').unlink()
        self.assertEqual(cli_team_store.apply(self.root, revised, idle['token'], **RULES)['outcome'], 'APPLIED')


if __name__ == '__main__':
    unittest.main()
