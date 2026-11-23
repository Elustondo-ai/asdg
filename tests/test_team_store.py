"""Team specification listing, preview and token-checked apply against disposable Git projects only."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from cli_files import Conflict
import cli_files
import cli_team_store
from cli_team_store import CLAIM, LIMIT, LOCK, RECEIPTS, SPECS, apply, preview, project, run_state, scan, spec_bytes, unused_team_id
from test_team_model import ROLES, spec

RULES = dict(role_ids=ROLES, coordinator='ASDG-COORDINATOR')
IDS = ('team-0123456789abcdef', 'team-1111111111111111', 'team-2222222222222222')
os.environ.setdefault('ASDG_OPENSPEC', '0')  # Hermetic: setup's OpenSpec step would run a separately installed command.


def git(root, *arguments):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    *arguments], check=True, capture_output=True, text=True)


def team(kind='subagents', name='Architecture review', team_id=IDS[0], **changes):
    return dict(spec(kind, name), team_id=team_id, **changes)


def snapshot(area):
    """Every path below `area`, Git internals included: kind, bytes or link target, and modification time."""
    result = {}
    for folder, folders, files in os.walk(area):
        for name in folders + files:
            path = Path(folder) / name
            kind = 'link' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
            content = os.readlink(path) if kind == 'link' else path.read_bytes() if kind == 'file' else None
            result[str(path)] = (kind, content, os.lstat(path).st_mtime_ns)
    return result


class TeamStoreTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-team-store-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name).resolve()
        self.root = self.area / 'client'
        (self.root / '.asdg').mkdir(parents=True)
        git(self.root, 'init', '-q')
        (self.root / '.asdg/project.json').write_text(json.dumps({'project_id': 'client-project'}))
        (self.root / 'app.py').write_text('print("client application")\n')
        self.specs = self.root / SPECS

    def save(self, saved, data=None):
        self.specs.mkdir(parents=True, exist_ok=True)
        (self.specs / (saved['team_id'] + '.json')).write_bytes(spec_bytes(saved) if data is None else data)

    def read_only(self, call):
        """Run a listing or preview and prove the whole disposable area is byte- and time-identical after it."""
        before = snapshot(self.area)
        try:
            return call()
        finally:
            self.assertEqual(snapshot(self.area), before)

    def look(self, candidate=None, **options):
        return self.read_only(lambda: preview(self.root, candidate or team(), **RULES, **options))

    def codes(self, result):
        self.assertEqual((result['outcome'], result['token'], result['applied']), ('CONFLICT', None, False))
        return {conflict['code'] for conflict in result['conflicts']}

    def test_empty_store_then_all_three_types_are_listed(self):
        empty = self.read_only(lambda: scan(self.root, **RULES))
        self.assertEqual((empty['exists'], empty['teams'], empty['clean']), (False, [], True))
        self.assertFalse((self.root / '.asdg/teams').exists())
        for kind, name, team_id in zip(('sessions', 'subagents', 'teammates'), ('Alpha', 'Beta', 'Gamma'), IDS):
            self.save(team(kind, name, team_id))
        listing = self.read_only(lambda: scan(self.root, **RULES))
        self.assertEqual([(row['team_id'], row['name'], row['type']) for row in listing['teams']],
                         list(zip(IDS, ('Alpha', 'Beta', 'Gamma'), ('sessions', 'subagents', 'teammates'))))
        self.assertTrue(listing['clean'])
        self.assertEqual({row['provenance'] for row in listing['teams']}, {'UNVERIFIED'})  # Format is not origin.
        self.assertNotIn(self.read_only(lambda: unused_team_id(self.root)), IDS)

    def test_preview_is_exact_deterministic_and_names_are_data(self):
        for kind in ('sessions', 'subagents', 'teammates'):
            for name in ('Architecture review', 'start', '../../etc/passwd', '$(touch owned)'):
                with self.subTest(kind=kind, name=name):
                    candidate = team(kind, name)
                    first, second = self.look(candidate), self.look(candidate)
                    self.assertEqual(first, second)
                    self.assertEqual((first['outcome'], first['action']), ('READY', 'create'))
                    self.assertEqual(first['path'], '.asdg/teams/specs/team-0123456789abcdef.json')
                    self.assertEqual(first['bytes'], spec_bytes(candidate))
                    self.assertEqual(json.loads(first['bytes'])['name'], name)
                    self.assertRegex(first['token'], r'^team-spec-preview-1\.[0-9a-f]{64}$')
                    self.assertEqual(first['evidence']['project']['git_common_dir'], str(self.root / '.git'))
        self.assertFalse((self.root / '.asdg/teams').exists())
        self.assertFalse((self.root / '.git/asdg').exists())
        self.assertFalse((self.root / 'owned').exists())

    def test_every_bound_input_changes_the_token(self):
        base = self.look()['token']
        tokens = {
            'purpose': self.look(team(purpose='Another purpose.'))['token'],
            'type': self.look(team('teammates'))['token'],
            'supplied context': self.look(context={'template_sha256': 'a' * 64})['token'],
            'role catalogue': self.read_only(lambda: preview(
                self.root, team(), role_ids=ROLES | {'ASDG-99'}, coordinator='ASDG-COORDINATOR'))['token'],
        }
        self.save(team('sessions', 'Other team', IDS[1]))
        tokens['another saved team'] = self.look()['token']
        (self.specs / 'notes.txt').write_text('kept\n')
        tokens['stray file'] = self.look()['token']
        claim = self.root / '.git' / CLAIM
        claim.parent.mkdir(parents=True)
        claim.write_text('{"opaque": true}\n')
        claimed = self.look()
        tokens['run claim'] = claimed['token']
        self.assertEqual(claimed['evidence']['run']['state'], 'PRESENT_UNINTERPRETED')
        (self.root / '.asdg/project.json').write_text(json.dumps({'project_id': 'client-project', 'extra': 1}))
        tokens['project binding'] = self.look()['token']
        self.assertEqual(len({base, *tokens.values()}), len(tokens) + 1, tokens)
        self.assertEqual(self.look()['supplied_unverified']['context'], {})  # Supplied text is carried, never proof.
        with self.assertRaises(Conflict):
            self.look(context={'capability': ['observed']})
        (self.root / '.asdg/project.json').write_text(json.dumps({'project_id': 'renamed'}))
        with self.assertRaisesRegex(Conflict, 'different project'):
            self.look()
        self.assertEqual((self.specs / 'notes.txt').read_text(), 'kept\n')

    def test_normalized_duplicate_names_are_conflicts(self):
        self.save(team(name='Architecture Review'))
        clash = self.look(team(name='ARCHITECTURE review', team_id=IDS[1]))
        self.assertEqual(self.codes(clash), {'NAME_IN_USE'})
        self.assertEqual(self.look(team(name='Security review', team_id=IDS[1]))['outcome'], 'READY')
        self.save(team('sessions', 'ＡＲＣＨＩＴＥＣＴＵＲＥ review', IDS[2]))
        listing = self.read_only(lambda: scan(self.root, **RULES))
        self.assertEqual((listing['duplicate_names'], listing['clean']), ([[IDS[0], IDS[2]]], False))
        self.assertIn('DUPLICATE_NAMES', self.codes(self.look(team(name='Security review', team_id=IDS[1]))))

    def test_unreadable_stored_files_are_reported_preserved_and_block(self):
        compact = json.dumps(team('sessions', 'Edited', IDS[2])).encode()
        files = {'team-aaaaaaaaaaaaaaaa.json': b'{not json', 'team-bbbbbbbbbbbbbbbb.json': b'[]',
                 'team-cccccccccccccccc.json': spec_bytes(team(team_id='team-cccccccccccccccc', project_id='elsewhere')),
                 'team-dddddddddddddddd.json': spec_bytes(team(team_id='team-dddddddddddddddd', schema_version=2)),
                 'team-eeeeeeeeeeeeeeee.json': spec_bytes(team(team_id='team-ffffffffffffffff')),
                 'team-9999999999999999.json': spec_bytes(team(team_id='team-9999999999999999', lead='nobody')),
                 IDS[2] + '.json': compact, 'team-0123456789abcdef (1).json': spec_bytes(team()),
                 'notes.json': b'{}', '.DS_Store': b'\x00'}
        self.specs.mkdir(parents=True)
        for name, data in files.items():
            (self.specs / name).write_bytes(data)
        (self.specs / 'folder').mkdir()
        listing = self.read_only(lambda: scan(self.root, **RULES))
        states = {row['file']: row['state'] for row in listing['problems']}
        self.assertEqual(states, {
            'team-aaaaaaaaaaaaaaaa.json': 'MALFORMED', 'team-bbbbbbbbbbbbbbbb.json': 'MALFORMED',
            'team-cccccccccccccccc.json': 'FOREIGN_PROJECT', 'team-dddddddddddddddd.json': 'UNSUPPORTED_VERSION',
            'team-eeeeeeeeeeeeeeee.json': 'INVALID', 'team-9999999999999999.json': 'INVALID',
            IDS[2] + '.json': 'NOT_SAVED_FORM', 'team-0123456789abcdef (1).json': 'UNKNOWN_FILE',
            'notes.json': 'UNKNOWN_FILE', 'folder': 'NOT_A_FILE'})
        self.assertEqual(([row['file'] for row in listing['strays']], listing['teams']), (['.DS_Store'], []))
        self.assertEqual(self.codes(self.look()), {'STORE_NEEDS_RECONCILIATION'})
        self.assertIn('NAME_IN_USE', self.codes(self.look(team(name='EDITED'))))  # A reformatted file still holds its name.
        for name, data in files.items():
            self.assertEqual((self.specs / name).read_bytes(), data)

    def test_unsafe_paths_and_symlinks_are_refused(self):
        outside = self.area / 'outside'
        outside.mkdir()
        (outside / 'secret.json').write_bytes(spec_bytes(team()))
        self.specs.mkdir(parents=True)
        (self.specs / (IDS[0] + '.json')).symlink_to(outside / 'secret.json')
        self.assertEqual(self.read_only(lambda: scan(self.root, **RULES))['problems'][0]['state'], 'SYMLINK')
        self.assertEqual(self.codes(self.look()), {'STORE_NEEDS_RECONCILIATION'})
        (self.specs / (IDS[0] + '.json')).unlink()
        self.specs.rmdir()
        self.specs.symlink_to(outside, target_is_directory=True)
        for candidate in (team(), team(team_id='../../outside/x'), team(team_id='team-0123456789ABCDEF')):
            with self.assertRaises(Conflict):
                self.look(candidate)
        self.specs.unlink()
        with self.assertRaises(Conflict):
            self.look(team(team_id='../../outside/x'))
        (self.root / 'sub').mkdir()
        for bad in (self.area, self.root / 'sub', Path('client')):
            with self.assertRaises(Conflict, msg=str(bad)):
                self.read_only(lambda: scan(bad, **RULES))
        claim = self.root / '.git' / CLAIM
        claim.parent.mkdir(parents=True)
        claim.symlink_to(outside / 'secret.json')
        self.assertEqual(run_state(self.root / '.git')['state'], 'UNSAFE')
        self.assertEqual(self.codes(self.look()), {'RUN_STATE_UNREADABLE'})
        (self.root / '.asdg/project.json').unlink()
        with self.assertRaisesRegex(Conflict, 'binding'):
            self.look()
        self.assertEqual(list(outside.iterdir()), [outside / 'secret.json'])

    def test_replacement_needs_the_next_revision_and_no_claim(self):
        self.save(team())
        self.assertEqual((self.look()['outcome'], self.look()['token']), ('UNCHANGED', None))
        stored = scan(self.root, **RULES)['teams'][0]['sha256']
        revised = self.look(team(purpose='A revised purpose.', revision=2))
        self.assertEqual((revised['action'], self.codes(revised)), ('replace', {'PROVENANCE_UNVERIFIED'}))
        self.assertEqual(revised['evidence']['target']['before_sha256'], stored)
        claimed = self.look(team(purpose='A revised purpose.', revision=2), context={'baseline_sha256': stored})
        self.assertEqual(self.codes(claimed), {'PROVENANCE_UNVERIFIED'})  # A supplied hash is not a baseline.
        self.assertEqual(self.codes(self.look(team(purpose='A revised purpose.'))),
                         {'STALE_REVISION', 'PROVENANCE_UNVERIFIED'})
        self.assertEqual(self.codes(self.look(team(team_id=IDS[1], name='New', revision=3))), {'REVISION'})
        claim = self.root / '.git' / CLAIM
        claim.parent.mkdir(parents=True)
        claim.write_text('{}\n')
        self.assertEqual(self.codes(self.look(team(purpose='A revised purpose.', revision=2))),
                         {'RUN_STATE_UNPROVEN', 'PROVENANCE_UNVERIFIED'})

    def test_a_local_agreement_in_the_saved_format_is_never_replaced(self):
        local = team()
        local['rules']['handoff'] = 'Keep this local agreement.'
        self.save(local)  # Same valid shape and serialization as a writer's file; nothing shows who wrote it.
        kept = (self.specs / (IDS[0] + '.json')).read_bytes()
        result = self.look(team(revision=2, purpose='Updated purpose.'))
        self.assertEqual((result['action'], self.codes(result)), ('replace', {'PROVENANCE_UNVERIFIED'}))
        self.assertEqual(self.look(local)['outcome'], 'UNCHANGED')
        self.assertEqual(self.look(team(name='Another team', team_id=IDS[1]))['outcome'], 'READY')
        self.assertEqual((self.specs / (IDS[0] + '.json')).read_bytes(), kept)

    def test_candidate_larger_than_the_read_limit_is_refused(self):
        def sized(target):
            candidate = team()
            for index in range(2000):
                member = {'slot': f'extra-{index}', 'role_id': 'ASDG-05', 'responsibility': 'x'}
                candidate['members'].append(member)
                need = target - len(spec_bytes(candidate))
                if 0 <= need <= 599:
                    member['responsibility'] = 'x' * (1 + need)
                    return candidate
                member['responsibility'] = 'x' * (600 if need > 1500 else 300)
        exact, over = sized(LIMIT), sized(LIMIT + 1)
        self.assertEqual((len(spec_bytes(exact)), len(spec_bytes(over))), (LIMIT, LIMIT + 1))
        ready = self.look(exact)
        self.assertEqual((ready['outcome'], len(ready['bytes'])), ('READY', LIMIT))
        before = copy.deepcopy(over)
        with self.assertRaisesRegex(Conflict, 'the limit is 262144'):
            self.look(over)
        self.assertEqual(over, before)
        self.save(exact)  # What a preview accepts, a later listing can read back.
        self.assertEqual([row['team_id'] for row in self.read_only(lambda: scan(self.root, **RULES))['teams']], [IDS[0]])
        self.save(over)
        self.assertEqual(scan(self.root, **RULES)['problems'][0]['state'], 'TOO_LARGE')

    def test_linked_worktree_resolves_the_shared_common_directory(self):
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'Seed')
        linked = self.area / 'linked'
        git(self.root, 'worktree', 'add', '-q', '-b', 'linked', str(linked))
        found = self.read_only(lambda: project(linked))
        self.assertEqual((found['root'], found['git_common_dir']), (str(linked), str(self.root / '.git')))
        self.assertNotEqual(self.read_only(lambda: preview(linked, team(), **RULES))['token'], self.look()['token'])

    # Apply: every mutation below happens inside the disposable area.

    def put(self, candidate, **options):
        token = self.look(candidate, **options)['token']
        return apply(self.root, candidate, token, **RULES, **options)

    def stored(self, team_id=IDS[0]):
        return (self.specs / (team_id + '.json')).read_bytes(), (self.root / RECEIPTS / (team_id + '.json')).read_bytes()

    def test_create_writes_the_previewed_spec_and_receipt_and_reads_back(self):
        for kind, name, team_id in zip(('sessions', 'subagents', 'teammates'), ('Alpha', 'Beta', 'Gamma'), IDS):
            candidate = team(kind, name, team_id)
            seen = self.look(candidate)
            self.assertEqual([effect['action'] for effect in seen['effects']], ['create', 'create'])
            self.assertEqual(seen['helpers']['lock'], str(self.root / '.git' / LOCK))
            done = apply(self.root, candidate, seen['token'], **RULES)
            self.assertEqual((done['outcome'], len(done['changed_files'])), ('APPLIED', 2))
            self.assertEqual(self.stored(team_id), (seen['bytes'], seen['receipt_bytes']))
            receipt = json.loads(seen['receipt_bytes'])
            self.assertEqual((receipt['team_id'], receipt['revision'], receipt['sha256'], receipt['root'],
                              receipt['git_common_dir']), (team_id, 1, seen['sha256'], str(self.root), str(self.root / '.git')))
            self.assertEqual(self.look(candidate)['outcome'], 'UNCHANGED')
            with self.assertRaises(Conflict):
                apply(self.root, candidate, seen['token'], **RULES)  # A used token no longer matches the store.
        listing = scan(self.root, **RULES)
        self.assertEqual(([row['type'] for row in listing['teams']], listing['clean']),
                         (['sessions', 'subagents', 'teammates'], True))
        self.assertEqual(sorted(item.name for item in self.specs.iterdir()), [name + '.json' for name in IDS])
        self.assertEqual((self.root / 'app.py').read_text(), 'print("client application")\n')

    def test_revision_needs_a_matching_receipt_and_the_exact_stored_bytes(self):
        self.put(team())
        second = team(purpose='A revised purpose.', revision=2)
        seen = self.look(second)
        self.assertEqual((seen['outcome'], [effect['action'] for effect in seen['effects']]), ('READY', ['replace', 'replace']))
        apply(self.root, second, seen['token'], **RULES)
        self.assertEqual(self.stored(), (seen['bytes'], seen['receipt_bytes']))
        third = team(purpose='A third purpose.', revision=3)
        spec_file, receipt_file = self.specs / (IDS[0] + '.json'), self.root / RECEIPTS / (IDS[0] + '.json')
        good_spec, good_receipt = self.stored()
        local = team(purpose='A revised purpose.', revision=2)
        local['rules']['handoff'] = 'Keep this local agreement.'
        other_root = json.dumps(dict(json.loads(good_receipt), root='/elsewhere'), indent=2, sort_keys=True) + '\n'
        for label, change in {'local edit': lambda: spec_file.write_bytes(spec_bytes(local)),
                              'missing receipt': receipt_file.unlink,
                              'malformed receipt': lambda: receipt_file.write_bytes(b'{'),
                              'receipt for another root': lambda: receipt_file.write_text(other_root),
                              'stale receipt': lambda: receipt_file.write_bytes(
                                  cli_team_store.receipt_bytes(project(self.root), IDS[0], 1, 'a' * 64))}.items():
            with self.subTest(case=label):
                change()
                blocked = self.look(third)
                self.assertEqual(self.codes(blocked), {'PROVENANCE_UNVERIFIED'})
                spec_file.write_bytes(good_spec)
                receipt_file.write_bytes(good_receipt)
        self.assertEqual(self.put(third)['action'], 'replace')
        spec_file.unlink()  # A receipt whose file is gone is not ours to overwrite either.
        self.assertEqual(self.codes(self.look(team())), {'RECEIPT_PRESENT'})

    def test_changed_inputs_reject_the_token_and_leave_only_the_lock(self):
        candidate = team()
        token = self.look(candidate)['token']
        for bad in (None, 'team-spec-preview-1.xyz', token.upper()):
            with self.assertRaises(Conflict):
                self.read_only(lambda: apply(self.root, candidate, bad, **RULES))  # Refused before any lock exists.
        self.save(team('sessions', 'Other team', IDS[1]))
        before = snapshot(self.area)
        attempts = (lambda: apply(self.root, candidate, token, **RULES),
                    lambda: apply(self.root, team(purpose='Swapped.'), token, **RULES),
                    lambda: apply(self.root, candidate, token, **RULES, context={'template': 'changed'}),
                    lambda: apply(self.root, candidate, token, role_ids=ROLES | {'ASDG-99'}, coordinator='ASDG-COORDINATOR'))
        for attempt in attempts:
            with self.assertRaisesRegex(Conflict, 'preview changed'):
                attempt()
        after = snapshot(self.area)
        lock = self.root / '.git' / LOCK
        self.assertEqual(set(after) - set(before), {str(lock), str(lock.parent), str(lock.parent.parent)})
        self.assertEqual({path: entry[:2] for path, entry in after.items() if path in before},
                         {path: entry[:2] for path, entry in before.items()})
        self.assertEqual(lock.read_bytes(), b'')
        self.assertEqual(self.put(candidate)['outcome'], 'APPLIED')  # The reused lock does not block a fresh preview.

    def test_concurrent_same_name_creates_save_at_most_one(self):
        names = ('Architecture review', 'ARCHITECTURE REVIEW', 'architecture Review', 'ＡＲＣＨＩＴＥＣＴＵＲＥ review',
                 'Architecture REVIEW', 'aRCHITECTURE review')
        candidates = [team(name=name, team_id='team-%016x' % index) for index, name in enumerate(names)]
        tokens = [self.look(candidate)['token'] for candidate in candidates]
        self.assertTrue(all(tokens))
        barrier, results = threading.Barrier(len(candidates)), []

        def attempt(candidate, token):
            barrier.wait()
            try:
                results.append(apply(self.root, candidate, token, **RULES)['outcome'])
            except Conflict as error:
                results.append(str(error))

        threads = [threading.Thread(target=attempt, args=pair) for pair in zip(candidates, tokens)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual((results.count('APPLIED'), len(results)), (1, len(candidates)), results)
        listing = scan(self.root, **RULES)
        self.assertEqual((len(listing['teams']), listing['clean'], len(list((self.root / RECEIPTS).iterdir()))), (1, True, 1))
        handle = os.open(self.root / '.git' / LOCK, os.O_RDWR)
        self.addCleanup(os.close, handle)
        cli_team_store.fcntl.flock(handle, cli_team_store.fcntl.LOCK_EX)  # A held lock makes a writer wait, then refuse.
        fresh = team(name='Held', team_id=IDS[1])
        with self.assertRaisesRegex(Conflict, 'in progress'):
            apply(self.root, fresh, self.look(fresh)['token'], **RULES, wait=0.1)
        self.assertFalse((self.specs / (IDS[1] + '.json')).exists())

    def test_symlinked_receipt_and_lock_paths_are_refused(self):
        outside = self.area / 'outside'
        outside.mkdir()
        candidate = team()
        token = self.look(candidate)['token']
        # Lock cases run first: a refused apply in the later cases leaves the real, reusable lock file behind.
        cases = {'lock folder': self.root / '.git/asdg', 'lock file': self.root / '.git' / LOCK,
                 'cache folder': self.root / '.asdg/cache', 'receipt file': self.root / RECEIPTS / (IDS[0] + '.json')}
        for label, link in cases.items():
            with self.subTest(case=label):
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside if 'folder' in label else outside / 'target', target_is_directory='folder' in label)
                for call in (lambda: preview(self.root, candidate, **RULES), lambda: apply(self.root, candidate, token, **RULES)):
                    with self.assertRaises(Conflict):
                        call()
                link.unlink()
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse(self.specs.exists())

    def test_injected_failures_roll_back_only_this_writers_changes(self):
        self.save(team('sessions', 'Unrelated team', IDS[1]))  # Someone else's file; it has no receipt.
        unrelated = (self.specs / (IDS[1] + '.json')).read_bytes()
        candidate = team()
        token = self.look(candidate)['token']
        real_scan, calls = cli_team_store.scan, []

        def failing_scan(*arguments, **options):
            calls.append(1)
            if len(calls) == 2:  # The first call is the recheck; the second is the read-back after both writes.
                raise RuntimeError('injected read-back failure')
            return real_scan(*arguments, **options)

        with mock.patch.object(cli_team_store, 'scan', failing_scan), self.assertRaisesRegex(RuntimeError, 'injected'):
            apply(self.root, candidate, token, **RULES)
        self.assertEqual(sorted(item.name for item in self.specs.iterdir()), [IDS[1] + '.json'])
        self.assertFalse((self.root / '.asdg/cache').exists())
        self.assertEqual((self.specs / (IDS[1] + '.json')).read_bytes(), unrelated)
        apply(self.root, candidate, token, **RULES)  # Rollback restored the previewed state exactly.
        first = self.stored()
        second = team(purpose='A revised purpose.', revision=2)
        token = self.look(second)['token']
        real_replace = cli_files.atomic_replace

        def failing_replace(path, data, mode):
            if RECEIPTS.name in Path(path).parts:
                raise OSError('injected receipt failure')  # The specification was already replaced.
            return real_replace(path, data, mode)

        with mock.patch.object(cli_files, 'atomic_replace', failing_replace), self.assertRaisesRegex(OSError, 'injected'):
            apply(self.root, second, token, **RULES)
        self.assertEqual(self.stored(), first)
        leftovers = [item.name for folder in (self.specs, self.root / RECEIPTS) for item in folder.iterdir()
                     if item.name.startswith('.asdg-tmp-')]
        self.assertEqual(leftovers, [])
        self.assertEqual((self.specs / (IDS[1] + '.json')).read_bytes(), unrelated)
        self.assertEqual(apply(self.root, second, token, **RULES)['action'], 'replace')


if __name__ == '__main__':
    unittest.main()
