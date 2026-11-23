# Team worktree script

`team_worktree.py` plans or creates the Git worktree and branch of the next numbered team. [Numbered teams](numbered-teams.md) says when to use it; this page says what it does.

## Use

Run it from the folder of the team you are branching from, normally the folder the calling chat works in.

- `python3 asdg/skills/asdg-create-team/team_worktree.py` prints the plan as JSON and changes nothing.
- Add `--create` to create the worktree and the branch.
- Add `--seen N`, once per number, for a team number seen in a chat title whose worktree no longer exists.
- `--folder PATH` names another team folder to branch from.

## What it decides

| Value | Rule |
| --- | --- |
| Clone | The first entry of `git worktree list`: the one folder made by `git clone`. |
| Teams found | Team 1, plus every worktree in the clone's `.claude/worktrees/` whose folder name ends in `-N`, plus local branches named `<stem>-N`, plus each `--seen`. |
| Number | The highest team found, plus one. A number is never reused while its worktree, branch or seen title remains. |
| Stem | The current branch; when that branch belongs to a team worktree, its `-N` is removed first. From `sprint-04-2` the stem is `sprint-04`. |
| Branch | `<stem>-<number>`, cut from the current branch's last commit. |
| Path | `<clone>/.claude/worktrees/<branch>`. |
| Not carried | The uncommitted and untracked files of the folder it ran in. A new worktree starts from the last commit, so these stay behind. |

## What `--create` changes

It runs `git worktree add -b <branch> <path> <base>`.
If Git does not already ignore `.claude/worktrees/`, it appends that folder to the clone's `.git/info/exclude`, a local file that is never committed.
It copies no file, pushes nothing, and starts no chat.

## Exit codes

- `0`: the plan or the created worktree was printed.
- `2`: `BLOCKED` on standard error; the folder is not a Git checkout, is on no branch, or the target folder already exists. Nothing was changed.

## Limits

It reads Git only. It cannot see chats, so a team whose worktree and branch were both removed is found only through `--seen`.
Tested by [numbered team tests](../../tests/test_numbered_teams.md) in disposable repositories.
