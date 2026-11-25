"""Push-replace transaction and recovery tests against disposable directories only."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
import cli_push_transaction as tx
from cli_files import Conflict


class PushTransactionTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-push-transaction-')
        self.addCleanup(area.cleanup)
        self.root = Path(area.name).resolve()
        self.write('payload/a', b'old-a', 0o640)
        self.write('payload/b', b'old-b')
        self.write('.asdg/installation-ownership.json', b'old-receipt')

    def write(self, path, value, mode=0o644):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value)
        p.chmod(mode)

    def change(self, path, after, mode=0o644):
        p = self.root / path
        before = p.read_bytes() if p.exists() else None
        return {'path': path, 'before_sha256': hashlib.sha256(before).hexdigest() if before is not None else None,
                'after': after, 'before_mode': stat.S_IMODE(p.stat().st_mode) if p.exists() else None,
                'after_mode': mode if after is not None else None}

    def plan(self, *changes, publish=()):
        return {'plan_id': 'a' * 64, 'changes': list(changes), 'publish_paths': list(publish),
                'verification': {'clients': ['claude', 'codex'], 'project_id': 'fixture'}}

    def transaction(self):
        return next((self.root / tx.BACKUPS).iterdir()).name

    def crash(self):
        plan = self.plan(self.change('payload/a', b'new-a'), self.change('payload/b', b'new-b'))
        original = tx._write

        def interrupted(root, relative, *args, **kwargs):
            if relative == 'payload/b':
                raise SystemExit('simulated process interruption')
            return original(root, relative, *args, **kwargs)

        with mock.patch.object(tx, '_write', side_effect=interrupted):
            with self.assertRaises(SystemExit):
                tx.execute(self.root, plan, lambda: None)
        return self.transaction()

    def test_noop_creates_no_lock_backup_or_receipt(self):
        p = self.root / 'payload/a'
        result = tx.execute(self.root, self.plan(self.change('payload/a', p.read_bytes(), 0o640)))
        self.assertEqual(result['state'], 'UNCHANGED')
        self.assertFalse((self.root / tx.BACKUPS).exists())
        self.assertFalse((self.root / tx.LOCK).exists())
        self.assertEqual((self.root / '.asdg/installation-ownership.json').read_bytes(), b'old-receipt')

    def test_publication_follows_payload_verification_and_preserves_backup(self):
        receipt = '.asdg/installation-ownership.json'
        order = []

        def preflight():
            order.append('preflight')
            self.assertEqual((self.root / 'payload/a').read_bytes(), b'old-a')

        def verify():
            order.append('verify')
            self.assertEqual((self.root / 'payload/a').read_bytes(), b'new-a')
            self.assertEqual((self.root / receipt).read_bytes(), b'old-receipt')

        plan = self.plan(self.change('payload/a', b'new-a', 0o600),
                         self.change(receipt, b'new-receipt'), publish=[receipt])
        result = tx.execute(self.root, plan, verify, preflight)
        self.assertEqual(order, ['preflight', 'verify'])
        self.assertEqual(result['state'], 'COMMITTED')
        self.assertEqual((self.root / receipt).read_bytes(), b'new-receipt')
        view = tx.inspect(self.root, result['transaction_id'])
        self.assertEqual(view['verification'], plan['verification'])
        self.assertEqual(view['changes'][0]['before_sha256'], hashlib.sha256(b'old-a').hexdigest())
        self.assertEqual(view['journal']['payload_verification'], 'PASSED')
        self.assertEqual(view['journal']['realized_files'], result['realized_files'])
        self.assertEqual(view['journal']['elapsed_seconds'], result['elapsed_seconds'])
        self.assertGreaterEqual(result['elapsed_seconds'], 0)
        self.assertEqual(stat.S_IMODE((self.root / 'payload/a').stat().st_mode), 0o600)

    def test_stale_bytes_or_modes_fail_before_creating_transaction(self):
        plan = self.plan(self.change('payload/a', b'new'))
        (self.root / 'payload/a').chmod(0o600)
        with self.assertRaisesRegex(Conflict, 'Stale'):
            tx.execute(self.root, plan, lambda: None)
        self.assertFalse((self.root / tx.BACKUPS).exists())
        self.assertFalse((self.root / tx.LOCK).exists())

    def test_preflight_mutation_is_rechecked_under_lock(self):
        plan = self.plan(self.change('payload/a', b'new'))
        with self.assertRaisesRegex(Conflict, 'Stale'):
            tx.execute(self.root, plan, lambda: None,
                       lambda: (self.root / 'payload/a').write_bytes(b'user-change'))
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'user-change')
        self.assertFalse((self.root / tx.BACKUPS).exists())

    def test_verifier_failure_restores_modified_deleted_and_new_files(self):
        plan = self.plan(self.change('payload/a', b'new-a'), self.change('payload/b', None),
                         self.change('payload/new', b'new'))
        with self.assertRaises(tx.TransactionFailure) as failure:
            tx.execute(self.root, plan, lambda: (_ for _ in ()).throw(ValueError('verification failed')))
        self.assertEqual(failure.exception.state, 'ROLLED_BACK')
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'old-a')
        self.assertEqual(stat.S_IMODE((self.root / 'payload/a').stat().st_mode), 0o640)
        self.assertEqual((self.root / 'payload/b').read_bytes(), b'old-b')
        self.assertFalse((self.root / 'payload/new').exists())

    def test_interruption_can_resume_without_source_tree(self):
        transaction = self.crash()
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'new-a')
        self.assertEqual((self.root / 'payload/b').read_bytes(), b'old-b')
        with self.assertRaisesRegex(Conflict, 'verification callback'):
            tx.recover(self.root, transaction, 'resume')
        result = tx.recover(self.root, transaction, 'resume', lambda: None)
        self.assertEqual(result['state'], 'COMMITTED')
        self.assertEqual((self.root / 'payload/b').read_bytes(), b'new-b')

    def test_interruption_can_roll_back_and_cannot_replay_after_rollback(self):
        transaction = self.crash()
        self.assertEqual(tx.recover(self.root, transaction)['state'], 'ROLLED_BACK')
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'old-a')
        self.assertEqual((self.root / 'payload/b').read_bytes(), b'old-b')
        with self.assertRaisesRegex(Conflict, 'cannot resume'):
            tx.recover(self.root, transaction, 'resume', lambda: None)

    def test_later_edit_blocks_all_recovery_writes(self):
        transaction = self.crash()
        (self.root / 'payload/b').write_bytes(b'later-user-edit')
        with self.assertRaisesRegex(tx.TransactionFailure, 'Later edit'):
            tx.recover(self.root, transaction)
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'new-a')
        self.assertEqual((self.root / 'payload/b').read_bytes(), b'later-user-edit')

    def test_pending_transaction_blocks_new_apply(self):
        self.crash()
        with self.assertRaisesRegex(Conflict, 'Unfinished transaction'):
            tx.execute(self.root, self.plan(self.change('payload/a', b'another')), lambda: None)

    def test_backup_failure_can_be_abandoned_without_deleting_partial_backup(self):
        original = tx._write

        def fail_backup(root, relative, *args, **kwargs):
            if relative.endswith('/0.after'):
                raise OSError('simulated full backup volume')
            return original(root, relative, *args, **kwargs)

        with mock.patch.object(tx, '_write', side_effect=fail_backup):
            with self.assertRaises(tx.TransactionFailure) as failure:
                tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        self.assertEqual(failure.exception.state, 'PREPARATION_INCOMPLETE')
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'old-a')
        with self.assertRaisesRegex(Conflict, 'Unfinished transaction'):
            tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        transaction = failure.exception.transaction_id
        folder = self.root / tx.BACKUPS / transaction
        self.assertIn('0.after', tx.inspect(self.root, transaction)['missing_backup_blobs'])
        with self.assertRaisesRegex(Conflict, 'Preparation is incomplete'):
            tx.recover(self.root, transaction, 'resume', lambda: None)
        result = tx.recover(self.root, transaction)
        self.assertEqual(result['disposition'], 'ABANDONED_PREPARATION')
        self.assertEqual(result['changed_files'], [])
        self.assertEqual((folder / '0.before').read_bytes(), b'old-a')
        tx.assert_idle(self.root)
        self.assertEqual(tx.execute(self.root, self.plan(self.change('payload/a', b'new')),
                                    lambda: None)['state'], 'COMMITTED')

    def test_preparation_interrupt_refuses_abandonment_after_later_edit(self):
        original = tx._write

        def interrupt(root, relative, *args, **kwargs):
            if relative.endswith('/0.after'):
                raise KeyboardInterrupt('simulated preparation interruption')
            return original(root, relative, *args, **kwargs)

        with mock.patch.object(tx, '_write', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        transaction = self.transaction()
        self.assertEqual(tx.inspect(self.root, transaction)['state'], 'PREPARING')
        (self.root / 'payload/a').write_bytes(b'later-edit')
        with self.assertRaisesRegex(Conflict, 'target no longer matches'):
            tx.recover(self.root, transaction)
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'later-edit')

    def test_valid_manifest_without_first_journal_can_be_abandoned(self):
        with mock.patch.object(tx, '_journal', side_effect=SystemExit('preparing journal crash')):
            with self.assertRaises(SystemExit):
                tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        transaction = self.transaction()
        self.assertEqual(tx.inspect(self.root, transaction)['state'], 'PREPARATION_INCOMPLETE')
        self.assertEqual(tx.recover(self.root, transaction)['disposition'], 'ABANDONED_PREPARATION')

    def test_readonly_idle_guard_and_noop_refuse_pending_transaction(self):
        self.crash()
        with self.assertRaisesRegex(Conflict, 'Unfinished transaction'):
            tx.assert_idle(self.root)
        with self.assertRaisesRegex(Conflict, 'Unfinished transaction'):
            tx.execute(self.root, self.plan(self.change('payload/a', b'new-a')))

    def test_resource_checks_fail_before_lock_backups_or_payload_writes(self):
        plan = self.plan(self.change('payload/a', b'new-a'))
        with mock.patch.object(tx.shutil, 'disk_usage', return_value=mock.Mock(free=0)):
            with self.assertRaisesRegex(Conflict, 'Insufficient free space'):
                tx.execute(self.root, plan, lambda: None)
        with mock.patch.object(tx.os, 'access', return_value=False):
            with self.assertRaisesRegex(Conflict, 'not writable/searchable'):
                tx.execute(self.root, plan, lambda: None)
        self.assertFalse((self.root / tx.BACKUPS).exists())
        self.assertFalse((self.root / tx.LOCK).exists())
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'old-a')

    def test_repeated_terminal_recovery_does_not_rewrite_journal(self):
        result = tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        transaction = result['transaction_id']
        journal = self.root / tx.BACKUPS / transaction / 'journal.json'
        before = (journal.read_bytes(), journal.stat().st_mtime_ns)
        verified = mock.Mock()
        result = tx.recover(self.root, transaction, 'resume', verified)
        verified.assert_called_once_with()
        self.assertEqual(result['changed_files'], [])
        self.assertTrue(result['recovery_unchanged'])
        self.assertEqual((journal.read_bytes(), journal.stat().st_mtime_ns), before)
        tx.recover(self.root, transaction, 'rollback')
        before = (journal.read_bytes(), journal.stat().st_mtime_ns)
        result = tx.recover(self.root, transaction, 'rollback')
        self.assertEqual(result['changed_files'], [])
        self.assertEqual((journal.read_bytes(), journal.stat().st_mtime_ns), before)

    def test_committed_resume_refuses_replay_over_later_edit(self):
        result = tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None)
        (self.root / 'payload/a').write_bytes(b'later-edit')
        with self.assertRaisesRegex(Conflict, 'output has changed'):
            tx.recover(self.root, result['transaction_id'], 'resume', lambda: None)
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'later-edit')

    def test_failed_error_journal_keeps_recovery_id_and_last_durable_state(self):
        transaction = self.crash()
        original = tx._journal

        def full_volume(root, txid, state, **detail):
            if state in ('ROLLING_BACK', 'BLOCKED'):
                raise OSError('simulated journal volume failure')
            return original(root, txid, state, **detail)

        with mock.patch.object(tx, '_journal', side_effect=full_volume):
            with self.assertRaises(tx.TransactionFailure) as failure:
                tx.recover(self.root, transaction)
        self.assertEqual(failure.exception.transaction_id, transaction)
        self.assertEqual(failure.exception.state, 'APPLYING')
        self.assertEqual(tx.inspect(self.root, transaction)['state'], 'APPLYING')
        self.assertEqual(tx.recover(self.root, transaction)['state'], 'ROLLED_BACK')

    def test_modified_backup_and_manifest_are_rejected(self):
        transaction = self.crash()
        folder = self.root / tx.BACKUPS / transaction
        raw = (folder / 'manifest.json').read_bytes()
        (folder / 'manifest.json').write_bytes(raw + b' ')
        with self.assertRaisesRegex(Conflict, 'manifest/checksum'):
            tx.inspect(self.root, transaction)
        (folder / 'manifest.json').write_bytes(raw)
        (folder / '0.before').write_bytes(b'corrupt-backup')
        with self.assertRaisesRegex(Conflict, 'backup blob'):
            tx.recover(self.root, transaction)
        self.assertEqual((self.root / 'payload/a').read_bytes(), b'new-a')

    def test_symlinks_hardlinks_and_nested_repositories_are_refused(self):
        for kind in ('symlink', 'hardlink', 'nested'):
            with self.subTest(kind=kind):
                target = self.root / ('unsafe-' + kind)
                if kind == 'symlink':
                    target.symlink_to(self.root / 'payload/a')
                elif kind == 'hardlink':
                    os.link(self.root / 'payload/b', target)
                else:
                    target.mkdir()
                    (target / '.git').write_text('gitdir: elsewhere')
                    target = target / 'file'
                rel = str(target.relative_to(self.root))
                with self.assertRaises(Conflict):
                    tx.execute(self.root, self.plan(self.change(rel, b'bad')), lambda: None)

    def test_traversal_git_and_control_paths_are_refused(self):
        for path in ('../escape', '.git/config', '/absolute', tx.LOCK, tx.BACKUPS + '/tx-x/data'):
            change = {'path': path, 'before_sha256': None, 'before_mode': None,
                      'after': b'bad', 'after_mode': 0o644}
            with self.subTest(path=path), self.assertRaises(Conflict):
                tx.execute(self.root, self.plan(change), lambda: None)

    def test_competing_lock_refuses_second_transaction(self):
        with tx._lock(self.root):
            with self.assertRaisesRegex(Conflict, 'holds the project lock'):
                tx.execute(self.root, self.plan(self.change('payload/a', b'new')), lambda: None, wait=0)

    def test_crash_after_publication_recovers_commit(self):
        receipt = '.asdg/installation-ownership.json'
        plan = self.plan(self.change('payload/a', b'new-a'), self.change(receipt, b'new-receipt'),
                         publish=[receipt])
        original = tx._journal

        def interrupt(root, txid, state, **detail):
            if state == 'COMMITTED':
                raise KeyboardInterrupt('simulated interruption after publication')
            return original(root, txid, state, **detail)

        with mock.patch.object(tx, '_journal', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                tx.execute(self.root, plan, lambda: None)
        self.assertEqual((self.root / receipt).read_bytes(), b'new-receipt')
        result = tx.recover(self.root, self.transaction(), 'resume', lambda: None)
        self.assertEqual(result['state'], 'COMMITTED')


if __name__ == '__main__':
    unittest.main()
