#!/usr/bin/env python3
"""Plan or create the Git worktree and branch of the next numbered ASDG team."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKTREES = Path('.claude/worktrees')
NUMBERED = re.compile(r'^(?P<stem>.+)-(?P<number>[1-9][0-9]*)$')


class Problem(Exception):
    """A state in which no team worktree may be planned or created."""


def git(folder, *args):
    result = subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True)
    if result.returncode:
        raise Problem(result.stderr.strip() or 'git ' + ' '.join(args) + ' failed')
    return result.stdout


def worktrees(folder):
    """Return (path, branch) for every worktree; the clone itself comes first."""
    rows, path = [], None
    for line in git(folder, 'worktree', 'list', '--porcelain').splitlines():
        if line.startswith('worktree '):
            path = Path(line[9:])
            rows.append([path, None])
        elif line.startswith('branch refs/heads/') and rows:
            rows[-1][1] = line[18:]
    return [tuple(row) for row in rows]


def plan(folder, seen=()):
    """Describe the next team: its number, branch, worktree path and base, changing nothing."""
    folder = Path(folder).resolve()
    rows = worktrees(folder)
    if not rows:
        raise Problem('No Git worktree found.')
    clone = rows[0][0].resolve()
    base = git(folder, 'branch', '--show-current').strip()
    if not base:
        raise Problem('This folder is on no branch (detached HEAD); switch to a branch first.')
    home = clone / WORKTREES
    numbers, team_branches = {1}, set()
    for path, branch in rows[1:]:
        match = NUMBERED.match(path.name)
        if match and path.resolve().parent == home.resolve():
            numbers.add(int(match['number']))
            team_branches.add(branch)
    match = NUMBERED.match(base)
    stem = match['stem'] if match and base in team_branches else base
    for branch in git(folder, 'branch', '--format=%(refname:short)').split():
        match = NUMBERED.match(branch)
        if match and match['stem'] == stem:
            numbers.add(int(match['number']))
    numbers.update(int(number) for number in seen)
    number = max(numbers) + 1
    branch = '%s-%d' % (stem, number)
    left = [line[3:] for line in git(folder, 'status', '--porcelain').splitlines()]
    return {'number': number, 'branch': branch, 'path': str(home / branch), 'clone': str(clone),
            'base': base, 'base_revision': git(folder, 'rev-parse', '--short', 'HEAD').strip(),
            'teams_found': sorted(numbers), 'not_carried': left}


def create(folder, seen=()):
    """Create the planned worktree and branch, and hide the worktrees folder from Git locally."""
    result = plan(folder, seen)
    clone = Path(result['clone'])
    if Path(result['path']).exists():
        raise Problem('The folder %s already exists.' % result['path'])
    git(folder, 'worktree', 'add', '-b', result['branch'], result['path'], result['base'])
    ignored = subprocess.run(['git', '-C', str(clone), 'check-ignore', '-q', str(WORKTREES) + '/x'])
    if ignored.returncode:
        exclude = Path(git(clone, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip()) / 'info/exclude'
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open('a') as handle:
            handle.write(str(WORKTREES) + '/\n')
    result['created'] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', default='.', help='the team folder to branch from; default: here')
    parser.add_argument('--seen', type=int, action='append', default=[],
                        help='a team number seen in a chat title; repeatable')
    parser.add_argument('--create', action='store_true', help='create the worktree; default: plan only')
    args = parser.parse_args(argv)
    try:
        result = (create if args.create else plan)(args.folder, args.seen)
    except Problem as problem:
        print('BLOCKED: %s' % problem, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
