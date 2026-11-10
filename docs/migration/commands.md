# Validation commands and environments

Run on 2026-11-09. Default `python3`: Python 3.15.0. Existing renderer interpreter: old checkout `.venv/bin/python`, Python 3.11. No dependencies or credentials were changed.
Source comparison uses a full Git archive of verified commit `0c0bad9479059837c0d6fabe438b2aba4a51e3c7` under `/private/tmp/asdg-cutover-evidence/source`, not the dirty old working tree.

## Repository inspection

```sh
pwd
git status
git branch --show-current
git remote -v
# Old checkout: same inspection plus
git rev-parse HEAD
git log -1 --format=fuller
git ls-tree -rz HEAD -- asdg/
```

Connected GitHub repository metadata verified both origins/default branches, new repository size zero, and current old main's full commit. No remote mutation.
Mechanical copy used Git tree/blob reads and a full source Git archive; `tracked-source.json` binds each product file to source blob, SHA-256 and mode. All 614 destination bytes matched immediately after copying.

## Maintained portable checks

From source archive: `python3 -B asdg/scripts/check.py --integrity` and `python3 -B -m unittest discover -s asdg/tests -v`.
From standalone destination:

```sh
python3 -B scripts/build_distribution.py --refresh-manifest
python3 -B scripts/check.py --integrity
python3 -B -m unittest discover -s tests -v
PYTHONPATH=tests python3 -B -m unittest test_install.InstallTests.test_standalone_canonical_clone_installs_and_rejects_dirty_selected_bytes test_sync.SyncTests.test_standalone_canonical_upgrade_and_promotion_keep_root_layout -v
```

Full-suite tests make their own Git commits only inside disposable fixtures, as the original tests already do. Neither real repository was staged or committed.
Build twice with explicit `--output` temporary directories; compare complete ZIP bytes and SHA-256. Inspect each member for exactly one `asdg/` prefix, no `asdg/asdg/`, no provider Publish skill or source-only migration report.
Copy source without `.git`/build outputs to an arbitrarily named temporary directory, then invoke its `scripts/check.py --integrity` from outside it. This validates source-name independence without sibling-provider lookup.

## Ancillary comparison

Use `python3 -B -m unittest discover -s <path> -v` separately for each suite, first source archive paths with `asdg/`, then destination root-relative paths:

- `00-governance/tests`
- `skills/asdg-component/tests`
- `skills/asdg-presentation/tests`
- `components/video-builder/tests`

Run `python3 -B [asdg/]00-governance/src/validate_agents.py` in both roots.
Repeat presentation and video suites with the existing renderer interpreter. Run `-B -m unittest discover -s [asdg/]tests -p test_report_project_status.py -v` with that interpreter in both roots to execute the two tests skipped by the default interpreter.
Full logs include default-Python missing-dependency attempts. Renderer-enabled results supersede those environment-only attempts but do not erase their evidence.

## Search, state and limits

`rg` searched hidden files for `agentic-sdlc-governance`, parent-depth/root calculations, `prepare_commit`, provider-root paths, and source-specific `asdg/` references. Before/after inventories retain classifications.
Compare every original file hash and executable mode again; record all adaptations in `adapted-files.json` and `root-adaptations.patch`.
Final readback: `git status --short`, `git diff --stat`, old checkout status and branch, and destination top-level listing.
`ps` inspection was unavailable under the sandbox; test process completion is taken from tool exit status and final unittest summaries.
Native Codex/Claude discovery, trusted hook interception, live audio, SDK calls and Python 3.9 runtime execution were not performed. The package checker checks Python 3.9 syntax.
