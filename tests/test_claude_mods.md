# Claude mod setup tests

[Source](test_claude_mods.py). Checks that setup installs [Claude mods](../mods/README.md) and that an initialized client can refresh its integration files after local methodology edits.
Each test builds a disposable client from the package list, seals its manifest, and drives the real `init.py` and `cli.py verify`.

| Test | Evidence |
| --- | --- |
| The packaged mod is complete and named after its folder | `mod_names` finds `asdg-sprint-status`; `claude_files` plans its four runtime files; a manifest with another name raises `Conflict`; without a manifest the folder is not a mod |
| Claude setup installs only the runtime files unchanged | Installed bytes equal the source; companions and tests are absent; Claude reports `COMPLETE` |
| Codex-only setup installs no mod | No `.claude` folder exists |
| An edited installed mod is reported and never overwritten | `verify` reports `DAMAGED` naming the file; setup refuses; the edit survives |
| An initialized client refreshes integrations after local edits | Preview reports `LOCAL_CHANGES`, no build and a note, and writes nothing; apply installs the mod; the manifest bytes are unchanged |
| A first install with a stale manifest is still refused | `Package integrity failed`; no `.asdg` or `.claude` is created |

Run with `python3 -B -m unittest discover -s asdg/tests -p "test_claude_mods.py"`.

## Limits

The tests prove planning, copying and structural verification only. They start no Claude session, so they show nothing about loading, trust prompts or drawing.
The mod's own behavior is covered by [its tests](../mods/asdg-sprint-status/hooks/register.test.md), which need the `claude` command.
