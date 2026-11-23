# OpenSpec setup tests

[Source](test_openspec_setup.py). Checks the setup step in [`cli_openspec`](../scripts/lib/cli_openspec.md) end to end through the real `init.py` and `cli.py verify`, in a disposable client.

| Test | Evidence |
| --- | --- |
| Missing files are planned and applied for the selected client only | Preview reports `PLANNED` with three rows of kind `openspec` and writes nothing; apply creates them; no Codex file appears; `verify` reports Claude `PRESENT`; a repeat preview plans nothing |
| An existing file is never overwritten | A local `openspec/config.yaml` is reported under `kept_differing`, is not planned and keeps its bytes |
| A missing command is reported and setup continues | `CLI_NOT_FOUND`, a note that ASDG never downloads it, ASDG's own adapters installed, and no OpenSpec line in `verify` |
| A failing or misbehaving command never blocks setup | A non-zero exit and an output outside the allowed folders both give `FAILED` with the reason and no rows |
| The step can be switched off | `--no-openspec` and `ASDG_OPENSPEC=0` both give `SKIPPED` |
| Verify notes a client without the skills in an OpenSpec project | Codex `PRESENT`, Claude `MISSING`, a note in the text, and still `ALL GOOD!` |

## Fixture

`FAKE` is a small shell script named `openspec`, placed first on `PATH`. It answers `--version` with `9.9.9` and writes a fixed set of files for `init`; `FAKE_OPENSPEC=fail` makes it exit 3 and `stray` makes it write outside the allowed folders.
`env(installed, mode, switch)` builds the environment: `PATH` holds the stand-in, git's folder, `/usr/bin` and `/bin` only, so a real OpenSpec elsewhere is not found. The missing-command test skips when a real `openspec` sits in one of those folders.

Run with `python3 -B -m unittest discover -s asdg/tests -p "test_openspec_setup.py"`.

## Limits

The stand-in proves ASDG's handling, not OpenSpec's behavior. No test runs the real command; that was done by hand, once, with OpenSpec 1.15.0.
Every other test module sets `ASDG_OPENSPEC=0`, so the suite gives the same result with or without OpenSpec installed.
