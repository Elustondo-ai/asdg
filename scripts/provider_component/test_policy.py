"""Exercise the Git handoff and narrow provider receipt using disposable clones."""
import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'lib'), str(HERE.parent)]
import cli
from provider_component import policy, receipts, review


class ProviderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name).resolve()
        self.root = self.folder / 'source'
        policy.git(HERE, 'clone', '--quiet', '--no-local', str(HERE.parents[1]), str(self.root))
        policy.git(self.root, 'remote', 'set-url', 'origin', sorted(policy.ORIGINS)[0])
        binding = patch.object(cli, '__file__', str(self.root / 'scripts/lib/cli.py'))
        binding.start()
        self.addCleanup(binding.stop)
        self.copy = self.folder / 'scratch'
        self.base = 'components/example/'
        self.old, self.new = (self.base + name for name in ('before.txt', 'after.txt'))
        self.job = dict(role_id='ASDG-09', component='example', root=str(self.root),
                        revision=policy.git(self.root, 'rev-parse', 'HEAD').decode().strip(),
                        objective='Exercise isolated Git review', acceptance=['Fixture passes'],
                        targets=[self.old, self.new])
        self.put(self.root, self.old, b'original content\n')
        self.start = review.prepare(self.root, self.job, self.copy)

    @staticmethod
    def put(root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def export(self):
        previous = Path.cwd()
        try:
            os.chdir(self.copy)
            return review.export_patch(self.root, self.start)
        finally:
            os.chdir(previous)

    def test_rename_and_exact_human_application(self):
        (self.copy / self.old).rename(self.copy / self.new)
        candidate = self.export()
        self.assertIn(b'rename from ', candidate)
        report = review.preview(self.root, self.start, candidate)
        self.assertCountEqual(report['paths'], [self.old, self.new])
        with self.assertRaises(ValueError):
            review.apply_reviewed(self.root, self.start, candidate, 'APPLY ' + report['patch_sha256'])
        review.apply_reviewed(self.root, self.start, candidate, 'APPLY ' + report['approval'])
        self.assertFalse((self.root / self.old).exists())
        self.assertEqual((self.root / self.new).read_bytes(), b'original content\n')
        with self.assertRaises(ValueError):
            review.preview(self.root, self.start, candidate)

    def test_add_delete_modes_and_dirty_state(self):
        (self.copy / self.old).unlink()
        self.put(self.copy, self.new, b'different\x00binary')
        (self.copy / self.new).chmod(0o755)
        candidate = self.export()
        report = review.preview(self.root, self.start, candidate)
        self.assertCountEqual(report['paths'], [self.old, self.new])
        for change in ('bytes', 'mode', 'index', 'revision'):
            with self.subTest(change=change):
                original = self.root / self.old
                if change == 'bytes':
                    original.write_bytes(b'new input')
                elif change == 'mode':
                    original.chmod(0o755)
                elif change == 'index':
                    policy.git(self.root, 'add', '--', self.old)
                else:
                    self.start['assignment']['revision'] = '0' * 40
                with self.assertRaises(ValueError):
                    review.preview(self.root, self.start, candidate)
                original.write_bytes(b'original content\n')
                original.chmod(self.start['starting_state']['files'][self.old]['mode'])
                policy.git(self.root, 'reset', '--quiet', '--', self.old)

    def test_dirty_read_only_input_and_export_isolation(self):
        dependency = self.base + 'input.txt'
        self.put(self.root, dependency, b'pending input')
        self.job['inputs'] = [dependency]
        self.copy = self.folder / 'with-input'
        self.start = review.prepare(self.root, self.job, self.copy)
        self.assertEqual((self.copy / dependency).read_bytes(), b'pending input')
        index = (self.copy / '.git/index').read_bytes()
        self.put(self.copy, self.new, b'candidate')
        candidate = self.export()
        review.preview(self.root, self.start, candidate)
        self.assertEqual((self.copy / '.git/index').read_bytes(), index)
        self.put(self.copy, dependency, b'changed')
        with self.assertRaisesRegex(ValueError, 'endpoint'):
            review.preview(self.root, self.start, self.export())
        self.put(self.root, dependency, b'stale')
        with self.assertRaisesRegex(ValueError, 'Starting'):
            review.preview(self.root, self.start, candidate)

    def test_ignored_candidate_fails_explicitly(self):
        self.put(self.copy, self.new, b'candidate')
        self.put(self.copy, '.git/info/exclude', (self.new + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'Git-ignored'):
            self.export()

    def test_cli_interactive_application_in_fixture(self):
        self.put(self.copy, self.new, b'candidate')
        candidate = self.export()
        start_path = self.folder / 'start.json'
        start_path.write_text(json.dumps(self.start))
        patch_path = self.folder / 'candidate.patch'
        patch_path.write_bytes(candidate)
        # CLI needs to be loaded from the simulated authority itself.
        dest = self.root / 'scripts/provider_component'
        shutil.copytree(HERE, dest)
        shutil.copyfile(HERE.parent / 'lib/cli.py', self.root / 'scripts/lib/cli.py')
        args = [sys.executable, '-B', str(dest / 'review.py')]
        result = subprocess.run([*args, 'preview', str(start_path), str(patch_path)],
                                cwd=self.root, check=True, capture_output=True, text=True)
        token = json.loads(result.stdout)['approval']
        result = subprocess.run([*args, 'apply', str(start_path), str(patch_path)], cwd=self.root,
                                input='APPLY ' + token, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('interactive terminal', result.stderr)
        self.assertFalse((self.root / self.new).exists())
        master, slave = pty.openpty()
        try:
            os.write(master, ('APPLY ' + token + '\n').encode())
            subprocess.run([*args, 'apply', str(start_path), str(patch_path)], cwd=self.root,
                           stdin=slave, capture_output=True, check=True, timeout=10)
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual((self.root / self.new).read_bytes(), b'candidate')


    def test_patch_and_assignment_substitution(self):
        self.put(self.copy, self.new, b'one\n')
        first = self.export()
        token = review.preview(self.root, self.start, first)['approval']
        self.put(self.copy, self.new, b'two\n')
        with self.assertRaises(ValueError):
            review.apply_reviewed(self.root, self.start, self.export(), 'APPLY ' + token)
        self.job['objective'] += ' changed'
        with self.assertRaises(ValueError):
            review.apply_reviewed(self.root, self.start, first, 'APPLY ' + token)
        self.assertFalse((self.root / self.new).exists())

    def test_mixed_patch_and_both_rename_endpoints(self):
        self.put(self.copy, self.new, b'valid\n')
        self.put(self.copy, 'unassigned', b'invalid\n')
        with self.assertRaises(ValueError):
            review.preview(self.root, self.start, self.export())
        (self.copy / 'unassigned').unlink()
        (self.copy / self.old).rename(self.copy / 'unassigned')
        candidate = self.export()
        self.assertIn('unassigned', policy.endpoints(self.root, candidate))
        with self.assertRaises(ValueError):
            review.preview(self.root, self.start, candidate)
        self.job['targets'].remove(self.old)
        self.job['targets'].append('unassigned')
        with self.assertRaises(ValueError):
            review.preview(self.root, self.start, candidate)

    def test_controls_links_and_traversal(self):
        (self.root / self.base / 'link').symlink_to(self.folder)
        for tail in ('../escape', 'link/file', '.git/config', '.asdg/state',
                     '.codex/config.toml', 'AGENTS.md', 'SKILL.md'):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                target = self.base + tail
                review.scope(self.root, dict(self.job, targets=[target]), [target])
        (self.copy / self.new).symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError, 'mode'):
            review.preview(self.root, self.start, self.export())
        candidate = self.export().replace(b'\n', b'\r\n')
        with self.assertRaises(ValueError):
            review.preview(self.root, self.start, candidate)
        (self.root / self.base / '.git').mkdir()
        with self.assertRaises(ValueError):
            review.scope(self.root, self.job, [self.old])

    def test_role_client_checkout_and_portable_boundary(self):
        for job in (dict(self.job, role_id='ASDG-ADMIN'), dict(self.job, acceptance=[]),
                    dict(self.job, root=str(self.copy))):
            with self.assertRaises(ValueError):
                review.scope(self.root, job, [self.old])
        context = dict(role_id='ASDG-09', workflow='provider-component', targets=[self.old])
        self.assertFalse(cli.evaluate_write(self.root, [self.old], context)[0])
        with self.assertRaises(ValueError):
            review.prepare(self.root, self.job, self.root / 'unsafe')
        index = self.root / 'metadata/package-files.json'
        data = json.loads(index.read_bytes())
        data['files'].append(self.old)
        index.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Portable'):
            review.scope(self.root, self.job, [self.old])
        (self.root / '.asdg').mkdir()
        with self.assertRaises(ValueError):
            review.scope(self.root, self.job, [self.old])
        (self.root / '.asdg').rmdir()
        policy.git(self.root, 'remote', 'set-url', 'origin', 'other')
        with self.assertRaises(ValueError):
            review.scope(self.root, self.job, [self.old])

    def test_receipt_only_appends_computed_events(self):
        ledger = self.root / receipts.LEDGER
        previous = json.loads(ledger.read_bytes())
        name = 'scripts/provider_component/example.md'
        self.put(self.root, name, b'test documentation\n')
        receipts.append_receipts(self.root, 'ASDG-ADMIN', [name])
        current = json.loads(ledger.read_bytes())
        event = current['events'].pop()
        self.assertEqual(previous, current)
        self.assertEqual((event['event'], event['human_approval'], event['sha256']),
                         ('AI-MODIFIED', None, policy.sha(b'test documentation\n')))
        self.assertEqual(receipts.append_receipts(self.root, 'ASDG-ADMIN', [name])['appended'], [])
        saved = ledger.read_bytes()
        for role, target in [('ASDG-09', name), ('ASDG-ADMIN', self.old),
                             ('ASDG-ADMIN', str(receipts.LEDGER)), ('ASDG-ADMIN', '00-governance/types/other.json')]:
            with self.assertRaises(ValueError):
                receipts.append_receipts(self.root, role, [target])
            self.assertEqual(ledger.read_bytes(), saved)
        context = dict(role_id='ASDG-ADMIN', workflow='admin', targets=[str(receipts.LEDGER)])
        # Admin maintains the ledger as a methodology record; receipts still never describe the ledger itself.
        self.assertTrue(cli.evaluate_write(self.root, context['targets'], context)[0])
        (self.root / '.asdg').mkdir()
        with self.assertRaises(ValueError):
            receipts.append_receipts(self.root, 'ASDG-ADMIN', [name])


if __name__ == '__main__':
    unittest.main()
