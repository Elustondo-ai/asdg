"""Append operator-scoped, exact-byte Admin documentation receipts."""
import fcntl
import json
import os
from pathlib import Path

from cli_files import Change, apply, safe_path
from cli_model import now, sha
from cli_ownership import local_path, ownership_decision
from documentation import review_record
from provider_component.policy import git, provider

LEDGER = Path('00-governance/types/document-reviews.json')


def append_receipts(root, role, documents):
    provider(root)
    if role != 'ASDG-ADMIN' or not documents:
        raise ValueError('An explicit Admin documentation scope is required.')
    context = {'workflow': 'admin', 'role_id': role, 'targets': documents}
    allowed, reason, application = ownership_decision(root, documents, context, repo=root)
    if not allowed or application:
        raise ValueError(reason)
    ledger_path = safe_path(root, LEDGER)
    lock = os.open(ledger_path.parent, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        raw = ledger_path.read_bytes()
        ledger = json.loads(raw)
        if ledger.get('schema_version') != 1 or not isinstance(ledger.get('events'), list):
            raise ValueError('Invalid provider ledger.')
        added = []
        for name in dict.fromkeys(documents):
            path = local_path(root, name)
            if path.as_posix() != name or path.suffix != '.md':
                raise ValueError('Expected an exact provider Markdown path.')
            contents = (root / path).read_bytes()
            tracked = git(root, 'ls-tree', 'HEAD', '--', name)
            before = git(root, 'show', 'HEAD:' + name) if tracked else None
            if contents == before:
                raise ValueError('Document has no modification against HEAD: ' + name)
            current = next((e for e in reversed(ledger['events']) if e.get('path') == name), {})
            if (current.get('sha256') == sha(contents) and current.get('event') == 'AI-MODIFIED'
                    and current.get('human_approval') is None):
                continue
            ledger['events'].append(review_record(name, before, contents, now(), role=role))
            added.append(name)
        if added:
            after = (json.dumps(ledger, ensure_ascii=False, indent=2) + '\n').encode()
            apply([Change(root, LEDGER, raw, after, ledger_path.stat().st_mode & 0o777)])
        return {'ledger': str(LEDGER), 'appended': added}
    finally:
        os.close(lock)
