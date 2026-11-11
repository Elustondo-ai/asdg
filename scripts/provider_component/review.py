"""Operator entry point for a disposable clone and a hash-bound Git patch."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/lib'), str(ROOT / 'scripts')]
from cli import evaluate_write
from cli_files import safe_path
from cli_model import sha
from provider_component.policy import endpoints, git, provider, starting_state, token


def scope(root, job, paths):
    allowed, reason = evaluate_write(root, paths, {'role_id': job['role_id'], 'workflow': 'provider-component'},
                                     provider_assignment=job)
    if not allowed:
        raise ValueError(reason)


def prepare(root, job, destination):
    scope(root, job, job['targets'])
    state = starting_state(root, job)
    if job['revision'] != state['revision']:
        raise ValueError('Assignment revision differs from HEAD.')
    copy = destination.resolve()
    if copy == root or root in copy.parents or copy in root.parents or os.path.lexists(destination):
        raise ValueError('Choose a new independent directory outside the authoritative checkout.')
    git(root, 'clone', '--quiet', '--no-local', '--no-checkout', '--', str(root), str(copy))
    git(copy, 'checkout', '--quiet', '--detach', state['revision'])
    git(copy, 'remote', 'set-url', 'origin', git(root, 'remote', 'get-url', 'origin').decode().strip())
    for name, entry in state['files'].items():
        dest = safe_path(copy, name)
        if entry is None:
            dest.unlink(missing_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, dest)
            dest.chmod(entry['mode'])
            if sha(dest.read_bytes()) != entry['sha256']:
                raise ValueError('Source changed during preparation.')
    reject_ignored(copy, job)
    git(copy, 'add', '-A', '--', '.')
    baseline = git(copy, 'write-tree').decode().strip()
    if state != starting_state(root, job):
        raise ValueError('Source changed during preparation. Use a fresh copy.')
    return {'assignment': job, 'starting_state': state, 'copy': str(copy), 'baseline_tree': baseline}


def reject_ignored(copy, job):
    names = sorted(set(job['targets']).union(job.get('inputs', [])))
    if git(copy, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', *names):
        raise ValueError('An assigned file is Git-ignored and cannot be faithfully exported.')


def export_patch(root, start):
    copy = Path.cwd().resolve()
    if (copy == root or root in copy.parents or copy in root.parents
            or str(copy) != start['copy'] or not (copy / '.git').is_dir()
            or git(copy, 'rev-parse', 'HEAD').decode().strip() != start['assignment']['revision']):
        raise ValueError('Export from the prepared disposable checkout.')
    reject_ignored(copy, start['assignment'])
    # The sandbox protects .git. Keep the candidate index and objects in scratch.
    with tempfile.TemporaryDirectory(prefix='.asdg-export-', dir=copy) as directory:
        private = Path(directory)
        (private / '.gitignore').write_text('*\n')
        (private / 'objects').mkdir()
        base = start['baseline_tree']
        git(copy, 'read-tree', base, private_index=private)
        git(copy, 'add', '-A', '--', '.', private_index=private)
        return git(copy, 'diff', '--cached', '--no-ext-diff', '--no-textconv', '--binary',
                   '--full-index', '--find-renames', base, '--', private_index=private)


def preview(root, start, patch):
    job = start['assignment']
    paths = endpoints(root, patch)
    scope(root, job, paths)
    state = starting_state(root, job)
    if job['revision'] != state['revision'] or start['starting_state'] != state:
        raise ValueError('Starting revision, index or assigned working files changed.')
    git(root, 'apply', '-p1', '--check', '--whitespace=nowarn', '-', data=patch)
    result = {'root': str(root), 'revision': state['revision'], 'start_sha256': token(start),
              'patch_sha256': sha(patch), 'paths': paths}
    return dict(result, approval=token(result))


def apply_reviewed(root, start, patch, confirmation):
    report = preview(root, start, patch)
    if confirmation != 'APPLY ' + report['approval']:
        raise ValueError('Confirmation differs from the reviewed patch and baseline.')
    git(root, 'apply', '-p1', '--whitespace=nowarn', '-', data=patch)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('assignment', type=Path)
    prep.add_argument('copy', type=Path)
    for op in ('preview', 'apply'):
        sub = commands.add_parser(op)
        sub.add_argument('start', type=Path)
        sub.add_argument('patch', type=Path)
    export = commands.add_parser('export')
    export.add_argument('start', type=Path)
    receipt = commands.add_parser('receipt')
    receipt.add_argument('--role', choices=['ASDG-ADMIN'], required=True)
    receipt.add_argument('documents', nargs='+')
    args = parser.parse_args()
    try:
        if args.action == 'export':
            patch = export_patch(ROOT, json.loads(args.start.read_bytes()))
            with Path('candidate.patch').open('xb') as output:
                output.write(patch)
            print('Exported candidate.patch')
            return
        if Path.cwd().resolve() != ROOT:
            raise ValueError('Run the trusted tool from the authoritative provider root.')
        provider(ROOT)
        if args.action == 'receipt':
            from provider_component.receipts import append_receipts
            result = append_receipts(ROOT, args.role, args.documents)
        elif args.action == 'prepare':
            result = prepare(ROOT, json.loads(args.assignment.read_bytes()), args.copy)
        else:
            start = json.loads(args.start.read_bytes())
            patch = args.patch.read_bytes()
            if args.action == 'apply':
                if not sys.stdin.isatty():
                    raise ValueError('Apply requires the operator’s interactive terminal.')
                confirmation = input('Enter APPLY and the token from your reviewed preview: ')
                result = apply_reviewed(ROOT, start, patch, confirmation)
            else:
                result = preview(ROOT, start, patch)
        print(json.dumps(result, sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError, EOFError, IndexError) as exc:
        sys.exit(f'Provider review stopped: {exc}')


if __name__ == '__main__':
    main()
