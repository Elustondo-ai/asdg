# Numbered team tests

These tests check [team_worktree.py](../skills/asdg-create-team/team_worktree.md), the script behind [numbered teams](../skills/asdg-create-team/numbered-teams.md), and that [Create team admin](../skills/asdg-create-team-admin/SKILL.md) is packaged.

| Test | What it shows |
| --- | --- |
| `test_first_extra_team_is_number_two_and_plan_changes_nothing` | From a clone on `sprint-04` the plan is team 2, branch `sprint-04-2`, inside `.claude/worktrees/`; uncommitted files are listed as not carried and nothing is created |
| `test_create_adds_worktree_and_branch_and_hides_the_folder_locally` | `create` makes the worktree and branch and adds the folder to `.git/info/exclude`, leaving Git status clean |
| `test_next_number_follows_the_last_team_from_the_clone_or_from_a_team_folder` | Team 3 is `sprint-04-3` whether planned from the clone or from team 2's folder, and always sits inside the clone |
| `test_numbers_seen_in_titles_or_left_as_branches_are_never_reused` | A number passed as seen, or left behind as a branch, raises the next number |
| `test_a_branch_that_only_looks_numbered_keeps_its_name_as_stem` | `release-2` in the clone is not a team, so its team 2 is `release-2-2` |
| `test_blocked_states_exit_two_and_change_nothing` | A detached HEAD and a folder that is not a checkout exit 2 without creating anything |
| `test_both_team_skills_are_packaged_indexed_and_linked` | The new files are in the package list, the skill index, Help, the title contract, the Admin entry and the adapter templates |

## Fixtures

Each test builds a small Git repository in a temporary folder with one commit on `sprint-04`. No chat is created and no project file is read.

## Run

```sh
cd asdg && python3 -B -m unittest tests.test_numbered_teams
```

## Limits

The tests cover Git planning and packaging only. Starting chats inside a worktree, titles and Admin activation need a real client run.
