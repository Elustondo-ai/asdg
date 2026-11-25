"""Durable, cooperative file transactions for reviewed push-replace plans."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import uuid
from datetime import datetime, timezone

from cli_files import Conflict

try:
    import fcntl
except ImportError:
    fcntl = None

BACKUPS = '.asdg/backups/push-replace'
LOCK = '.asdg/cache/push-replace.lock'
TX_ID = re.compile(r'tx-[0-9a-f]{32}')
SHA = re.compile(r'[0-9a-f]{64}')
STATES = {'PREPARING', 'PREPARATION_INCOMPLETE', 'PREPARED', 'APPLYING', 'VERIFYING', 'PUBLISHING', 'COMMITTED',
          'ROLLING_BACK', 'ROLLED_BACK', 'BLOCKED'}


class TransactionFailure(Conflict):
    """Failure with a retained recovery record; never implies zero writes."""
    def __init__(self, message, transaction_id, state):
        super().__init__(f'{message} [transaction {transaction_id}; state {state}]')
        self.transaction_id, self.state = transaction_id, state


def _encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value) or any(c in value for c in '*?[]')):
        raise Conflict('Invalid transaction path.')
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or p.as_posix() != value or any(v in ('.', '..', '.git') for v in p.parts):
        raise Conflict('Unsafe transaction path: ' + value)
    return p


def _root(value):
    root = Path(value)
    if not root.is_absolute() or root.resolve() != root or not root.is_dir():
        raise Conflict('Transaction root must be an existing resolved absolute directory.')
    return root


def _path(root, relative, *, control=False):
    p = _relative(relative)
    if not control and (relative == LOCK or relative == BACKUPS or relative.startswith(BACKUPS + '/')):
        raise Conflict('Transaction cannot modify its own lock or backup store.')
    path = root
    for i, part in enumerate(p.parts):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise Conflict('Symlink in transaction path: ' + str(path))
        if i != len(p.parts) - 1:
            if not stat.S_ISDIR(info.st_mode):
                raise Conflict('Non-directory transaction parent: ' + str(path))
            if (path / '.git').exists() or (path / '.git').is_symlink():
                raise Conflict('Nested repository in transaction path: ' + str(path))
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Conflict('Transaction target must be a singly linked regular file: ' + str(path))
    return path


def _read(root, relative, *, control=False):
    path = _path(root, relative, control=control)
    if not path.exists():
        return None, None
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (
            after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size):
        raise Conflict('File changed while reading: ' + relative)
    return data, stat.S_IMODE(after.st_mode)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _parents(root, path):
    relative = path.parent.relative_to(root)
    parent = root
    for part in relative.parts:
        child = parent / part
        if child.is_symlink():
            raise Conflict('Symlink in transaction parent: ' + str(child))
        if not child.exists():
            child.mkdir(mode=0o700)
            _fsync_dir(parent)
        if not child.is_dir():
            raise Conflict('Non-directory transaction parent: ' + str(child))
        parent = child


def _write(root, relative, data, mode, *, control=False):
    """Atomically replace regular-file bytes, persisting the containing directory."""
    path = _path(root, relative, control=control)
    _parents(root, path)
    if data is None:
        if path.exists():
            path.unlink()
            _fsync_dir(path.parent)
        return
    fd, temporary = tempfile.mkstemp(prefix='.asdg-push-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _path(root, relative, control=control)
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def _lock(root, wait=10.0):
    if fcntl is None:
        raise Conflict('Cooperative file locking is unavailable; no transaction attempted.')
    path = _path(root, LOCK, control=True)
    _parents(root, path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Conflict('Unsafe transaction lock.')
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Conflict('Another push-replace transaction holds the project lock.')
                time.sleep(0.05)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _mode(value, absent=False):
    if value is None and absent:
        return
    if type(value) is not int or value < 0 or value > 0o777:
        raise Conflict('Expected a regular permission mode between 0000 and 0777.')


def _preflight_resources(root, rows, *, backup=True, desired='after'):
    """Check current permissions and conservative free-space needs; not a reservation."""
    requirements = {}

    def reserve(path, size):
        parent = path.parent
        while not parent.exists():
            parent = parent.parent
        if not os.access(parent, os.W_OK | os.X_OK):
            raise Conflict('Transaction parent is not writable/searchable: ' + str(parent))
        device = parent.stat().st_dev
        entry = requirements.setdefault(device, [parent, 1024 * 1024])
        entry[1] += size

    for row in rows:
        path = _path(root, row['path'])
        reserve(path, len(row.get(desired) or b''))
    reserve(_path(root, LOCK, control=True), 4096)
    reserve(_path(root, BACKUPS + '/.preflight', control=True),
            16384 + 4096 * len(rows) + (sum(len(row.get(kind) or b'')
                                          for row in rows for kind in ('before', 'after')) if backup else 0))
    for parent, needed in requirements.values():
        if shutil.disk_usage(parent).free < needed:
            raise Conflict('Insufficient free space for backups and atomic writes: ' + str(parent))


def _normalize(root, plan):
    if not isinstance(plan, dict) or not isinstance(plan.get('plan_id'), str) or not SHA.fullmatch(plan['plan_id']):
        raise Conflict('Transaction requires a SHA-256 plan ID.')
    rows = plan.get('changes')
    publish = plan.get('publish_paths', [])
    if (not isinstance(rows, list) or not isinstance(publish, list)
            or not all(isinstance(p, str) for p in publish) or len(publish) != len(set(publish))):
        raise Conflict('Invalid transaction changes or publication paths.')
    paths, result = set(), []
    for row in rows:
        if not isinstance(row, dict) or not {'path', 'before_sha256', 'after', 'before_mode', 'after_mode'} <= set(row):
            raise Conflict('Incomplete transaction change.')
        rel = row['path']
        _path(root, rel)
        if rel in paths or any(rel.startswith(p + '/') or p.startswith(rel + '/') for p in paths):
            raise Conflict('Duplicate or overlapping transaction paths.')
        paths.add(rel)
        before_hash, after = row['before_sha256'], row['after']
        if before_hash is not None and (not isinstance(before_hash, str) or not SHA.fullmatch(before_hash)):
            raise Conflict('Invalid transaction before hash.')
        if after is not None and not isinstance(after, bytes):
            raise Conflict('Transaction after state must be bytes or None.')
        _mode(row['before_mode'], absent=before_hash is None)
        _mode(row['after_mode'], absent=after is None)
        if (before_hash is None) != (row['before_mode'] is None) or (after is None) != (row['after_mode'] is None):
            raise Conflict('Absent files require absent permission modes.')
        data, mode = _read(root, rel)
        if (_sha(data), mode) != (before_hash, row['before_mode']):
            raise Conflict('Stale transaction preimage: ' + rel)
        if data != after or mode != row['after_mode']:
            result.append(dict(row, before=data, publish=rel in publish))
    if not set(publish) <= paths:
        raise Conflict('Publication path is missing from the change list.')
    try:
        _encoded(plan.get('verification', {}))
    except (TypeError, ValueError) as exc:
        raise Conflict('Verification metadata must be finite JSON.') from exc
    return sorted(result, key=lambda r: (r['publish'], r['path']))


def _journal(root, txid, state, **detail):
    value = {'schema_version': 1, 'transaction_id': txid, 'state': state,
             'updated_at': _now(), **detail}
    raw, _ = _read(root, f'{BACKUPS}/{txid}/manifest.json', control=True)
    if raw is not None:
        created_at = json.loads(raw)['created_at']
        value['elapsed_seconds'] = max(0.0, (datetime.fromisoformat(value['updated_at'])
                                            - datetime.fromisoformat(created_at)).total_seconds())
    _write(root, f'{BACKUPS}/{txid}/journal.json', _encoded(value), 0o600, control=True)


def _assert_no_pending(root):
    folder = root / BACKUPS
    _path(root, BACKUPS + '/.inventory', control=True)
    if not folder.exists():
        return
    for item in sorted(folder.iterdir()):
        if item.is_symlink() or not item.is_dir() or not TX_ID.fullmatch(item.name):
            raise Conflict('Unexpected entry in transaction backup store; review it before applying.')
        try:
            _, journal = _load(root, item.name, allow_incomplete=True)
        except Conflict as exc:
            raise Conflict(f'Unverified prior transaction {item.name}; recover or reconcile it first.') from exc
        if journal['state'] not in ('COMMITTED', 'ROLLED_BACK'):
            raise Conflict(f'Unfinished transaction {item.name}; recover it before applying a new plan.')


def assert_idle(root):
    """Read-only guard against claiming an interrupted installation is synchronized."""
    _assert_no_pending(_root(root))


def _prepare(root, plan, rows):
    txid = 'tx-' + uuid.uuid4().hex
    prefix = f'{BACKUPS}/{txid}'
    marker = _path(root, prefix + '/manifest.json', control=True)
    _parents(root, marker)
    entries = []
    try:
        for index, row in enumerate(rows):
            entry = {'path': row['path'], 'before_sha256': _sha(row['before']),
                     'after_sha256': _sha(row['after']), 'before_mode': row['before_mode'],
                     'after_mode': row['after_mode'], 'publish': row['publish']}
            for kind in ('before', 'after'):
                entry[kind + '_blob'] = f'{index}.{kind}' if row[kind] is not None else None
            entries.append(entry)
        root_stat = root.stat()
        manifest = {'schema_version': 1, 'transaction_id': txid, 'plan_id': plan['plan_id'],
                    'root': str(root), 'root_identity': [root_stat.st_dev, root_stat.st_ino],
                    'created_at': _now(), 'verification': plan.get('verification', {}), 'changes': entries}
        raw = _encoded(manifest)
        _write(root, prefix + '/manifest.json', raw, 0o600, control=True)
        _write(root, prefix + '/manifest.sha256', (_sha(raw) + '\n').encode(), 0o600, control=True)
        _journal(root, txid, 'PREPARING')
        for index, row in enumerate(rows):
            for kind in ('before', 'after'):
                if row[kind] is not None:
                    _write(root, prefix + f'/{index}.{kind}', row[kind], 0o600, control=True)
        _journal(root, txid, 'PREPARED')
    except Exception as exc:
        try:
            _journal(root, txid, 'PREPARATION_INCOMPLETE', error=str(exc))
        except Exception:
            pass  # The durable manifest/previous journal remain the recovery evidence.
        raise TransactionFailure('Backup preparation failed before payload writes: ' + str(exc),
                                 txid, 'PREPARATION_INCOMPLETE') from exc
    return manifest


def _load(root, txid, *, allow_incomplete=False):
    if not isinstance(txid, str) or not TX_ID.fullmatch(txid):
        raise Conflict('Invalid transaction ID.')
    prefix = f'{BACKUPS}/{txid}'
    raw, _ = _read(root, prefix + '/manifest.json', control=True)
    checksum, _ = _read(root, prefix + '/manifest.sha256', control=True)
    if raw is None or checksum != (_sha(raw) + '\n').encode():
        raise Conflict('Missing or modified transaction manifest/checksum.')
    try:
        m = json.loads(raw)
        jraw, _ = _read(root, prefix + '/journal.json', control=True)
        journal = json.loads(jraw) if jraw else {'schema_version': 1, 'transaction_id': txid,
                                                'state': 'PREPARATION_INCOMPLETE'}
    except (ValueError, TypeError) as exc:
        raise Conflict('Unreadable transaction manifest or journal.') from exc
    identity = root.stat()
    if (not isinstance(m, dict) or m.get('schema_version') != 1 or m.get('transaction_id') != txid
            or m.get('root') != str(root) or m.get('root_identity') != [identity.st_dev, identity.st_ino]
            or not isinstance(m.get('changes'), list) or not isinstance(m.get('plan_id'), str)
            or not SHA.fullmatch(m['plan_id']) or not isinstance(journal, dict)
            or journal.get('transaction_id') != txid or journal.get('state') not in STATES):
        raise Conflict('Transaction identity, shape or journal state is invalid.')
    incomplete_allowed = allow_incomplete and (journal['state'] in ('PREPARING', 'PREPARATION_INCOMPLETE')
            or journal.get('disposition') == 'ABANDONED_PREPARATION')
    paths, missing_blobs = set(), []
    for index, row in enumerate(m['changes']):
        if not isinstance(row, dict) or set(row) != {'path', 'before_sha256', 'after_sha256',
                'before_mode', 'after_mode', 'publish', 'before_blob', 'after_blob'}:
            raise Conflict('Invalid transaction file entry.')
        rel = row['path']; _path(root, rel)
        if rel in paths or any(rel.startswith(p + '/') or p.startswith(rel + '/') for p in paths):
            raise Conflict('Duplicate or overlapping saved transaction paths.')
        paths.add(rel)
        if type(row['publish']) is not bool:
            raise Conflict('Invalid publication marker.')
        for kind in ('before', 'after'):
            digest, name, mode = row[kind + '_sha256'], row[kind + '_blob'], row[kind + '_mode']
            _mode(mode, absent=digest is None)
            if digest is None:
                if name is not None or mode is not None:
                    raise Conflict('Invalid absent transaction preimage.')
                data = None
            else:
                if not isinstance(digest, str) or not SHA.fullmatch(digest) or name != f'{index}.{kind}':
                    raise Conflict('Invalid transaction blob reference.')
                data, _ = _read(root, prefix + '/' + name, control=True)
                if data is None and incomplete_allowed:
                    missing_blobs.append(name)
                elif data is None or _sha(data) != digest:
                    raise Conflict('Missing or modified transaction backup blob.')
            row[kind] = data
    m['missing_blobs'] = missing_blobs
    return m, journal


def _matches(root, row, kind):
    data, mode = _read(root, row['path'])
    return (_sha(data), mode) == (row[kind + '_sha256'], row[kind + '_mode'])


def _check_recoverable(root, manifest):
    for row in manifest['changes']:
        if not _matches(root, row, 'before') and not _matches(root, row, 'after'):
            raise Conflict('Later edit or unexpected state prevents recovery: ' + row['path'])


def _transition(root, row, desired):
    if _matches(root, row, desired):
        return
    other = 'before' if desired == 'after' else 'after'
    if not _matches(root, row, other):
        raise Conflict('Concurrent edit prevents transaction write: ' + row['path'])
    _write(root, row['path'], row[desired], row[desired + '_mode'])


def _resume(root, m, verify_callback):
    txid = m['transaction_id']
    _check_recoverable(root, m)
    _journal(root, txid, 'APPLYING')
    for row in m['changes']:
        if not row['publish']:
            _transition(root, row, 'after')
    _journal(root, txid, 'VERIFYING')
    verify_callback()
    _journal(root, txid, 'PUBLISHING')
    for row in m['changes']:
        if row['publish']:
            _transition(root, row, 'after')
    for row in m['changes']:
        if not _matches(root, row, 'after'):
            raise Conflict('Post-publication verification failed: ' + row['path'])
    _journal(root, txid, 'COMMITTED', payload_verification='PASSED',
             realized_files=[{'path': row['path'], 'sha256': row['after_sha256'],
                              'mode': row['after_mode']} for row in m['changes']])


def _rollback(root, m):
    _check_recoverable(root, m)
    _journal(root, m['transaction_id'], 'ROLLING_BACK')
    for row in reversed(m['changes']):
        _transition(root, row, 'before')
    _journal(root, m['transaction_id'], 'ROLLED_BACK')


def _result(root, m, state, journal=None):
    if journal is None:
        raw, _ = _read(root, f"{BACKUPS}/{m['transaction_id']}/journal.json", control=True)
        journal = json.loads(raw) if raw else {}
    return {'transaction_id': m['transaction_id'], 'plan_id': m['plan_id'], 'state': state,
            'created_at': m['created_at'], 'backup_path': str(root / BACKUPS / m['transaction_id']),
            'updated_at': journal.get('updated_at'), 'elapsed_seconds': journal.get('elapsed_seconds'),
            'changed_files': [row['path'] for row in m['changes']],
            'verification_status': 'PASSED' if state == 'COMMITTED' else 'NOT_ESTABLISHED',
            'realized_files': [{'path': row['path'], 'sha256': row['after_sha256'],
                                'mode': row['after_mode']} for row in m['changes']] if state == 'COMMITTED' else []}


def inspect(root, transaction_id):
    """Read and hash-check the manifest, journal and all backup blobs; never modify them."""
    root = _root(root)
    m, journal = _load(root, transaction_id, allow_incomplete=True)
    result = _result(root, m, journal['state'], journal)
    result.update(verification=m.get('verification', {}), journal=journal,
                  missing_backup_blobs=m['missing_blobs'],
                  changes=[{k: v for k, v in row.items() if k not in ('before', 'after')}
                           for row in m['changes']])
    return result


def _record_failure(root, txid, operation, error):
    """Keep the transaction ID even if a failing volume also rejects the error journal."""
    try:
        _journal(root, txid, 'BLOCKED', operation=operation, error=str(error))
        return 'BLOCKED'
    except Exception:
        try:
            raw, _ = _read(root, f'{BACKUPS}/{txid}/journal.json', control=True)
            return json.loads(raw)['state'] if raw else 'PREPARATION_INCOMPLETE'
        except Exception:
            return 'JOURNAL_UNREADABLE'


def execute(root, plan, verify_callback=None, preflight_callback=None, *, wait=10.0):
    """Apply exact preimages and publish receipts only after verification under one lock."""
    root = _root(root)
    rows = _normalize(root, plan)
    if not rows:
        assert_idle(root)
        return {'state': 'UNCHANGED', 'transaction_id': None, 'plan_id': plan['plan_id'],
                'backup_path': None, 'changed_files': []}
    if not callable(verify_callback):
        raise Conflict('A payload verification callback is required before applying changes.')
    _preflight_resources(root, rows)
    with _lock(root, wait):
        _assert_no_pending(root)
        if preflight_callback is not None:
            preflight_callback()
        rows = _normalize(root, plan)
        _preflight_resources(root, rows)
        m = _prepare(root, plan, rows)
        m, _ = _load(root, m['transaction_id'])
        try:
            _resume(root, m, verify_callback)
        except Exception as exc:
            state = 'ROLLED_BACK'
            try:
                _rollback(root, m)
            except Exception as rollback_error:
                state = _record_failure(root, m['transaction_id'], 'rollback', rollback_error)
            raise TransactionFailure(str(exc), m['transaction_id'], state) from exc
        return _result(root, m, 'COMMITTED')


def recover(root, transaction_id, mode='rollback', verify_callback=None, *, wait=10.0):
    """Restore/resume exact recorded states; a later unrelated edit blocks all recovery writes."""
    root = _root(root)
    if mode not in ('rollback', 'resume'):
        raise Conflict('Recovery mode must be rollback or resume.')
    if mode == 'resume' and not callable(verify_callback):
        raise Conflict('Resume requires a payload verification callback.')
    with _lock(root, wait):
        m, journal = _load(root, transaction_id, allow_incomplete=True)
        if mode == 'rollback' and journal['state'] == 'ROLLED_BACK':
            return dict(_result(root, m, 'ROLLED_BACK'), changed_files=[], recovery_unchanged=True)
        if mode == 'resume' and journal['state'] == 'COMMITTED':
            if not all(_matches(root, row, 'after') for row in m['changes']):
                raise Conflict('Committed transaction output has changed; refusing to replay it.')
            verify_callback()
            return dict(_result(root, m, 'COMMITTED'), changed_files=[], recovery_unchanged=True)
        if journal['state'] in ('PREPARING', 'PREPARATION_INCOMPLETE'):
            if mode != 'rollback':
                raise Conflict('Preparation is incomplete; roll it back and prepare a fresh plan.')
            if not all(_matches(root, row, 'before') for row in m['changes']):
                raise Conflict('Cannot abandon preparation: a target no longer matches its before-state.')
            _journal(root, transaction_id, 'ROLLED_BACK', disposition='ABANDONED_PREPARATION',
                     payload_mutations='NONE', retained_missing_blobs=m['missing_blobs'])
            return dict(_result(root, m, 'ROLLED_BACK'), changed_files=[],
                        disposition='ABANDONED_PREPARATION')
        if mode == 'resume' and (journal['state'] in ('ROLLING_BACK', 'ROLLED_BACK')
                                  or journal.get('operation') == 'rollback'):
            raise Conflict('A rolled-back transaction cannot resume; prepare a fresh plan.')
        _preflight_resources(root, m['changes'], backup=False,
                             desired='before' if mode == 'rollback' else 'after')
        try:
            if mode == 'rollback':
                _rollback(root, m)
                state = 'ROLLED_BACK'
            else:
                _resume(root, m, verify_callback)
                state = 'COMMITTED'
        except Exception as exc:
            state = _record_failure(root, transaction_id, mode, exc)
            raise TransactionFailure(str(exc), transaction_id, state) from exc
        return _result(root, m, state)
