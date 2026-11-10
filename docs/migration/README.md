# ASDG standalone-source migration review

Prepared 2026-11-09 for Pablo. Working tree only; no stage, commit, push, release, settings/catalog change or external cutover. Other projects were not modified.

## Source and destination

Source: `Elustondo-ai/agentic-sdlc-governance`, `main`, `0c0bad9479059837c0d6fabe438b2aba4a51e3c7`, confirmed as current GitHub main. Version: `0.3.0-pilot.4`, candidate-for-review, native enforcement NOT_VERIFIED.
The old local working tree was dirty: ` D asdg/scripts/lib/cli_events.py`. Committed bytes were used, so that file is present here; the old deletion is untouched.
Destination: `Elustondo-ai/asdg`, unborn `main`, initially empty with verified origin. [Top-level listing](top-level.txt).

## Migration and adaptation

All 614 tracked files under old `asdg/` were copied to this root, initially byte-for-byte. All Git modes were `100644`; modes remain preserved, including all 103 hidden template paths. No tracked product file was excluded or deleted. No nested source `asdg/` exists.
43 original files were minimally adapted; 571 remain unchanged. [Original file hashes/modes](tracked-source.json), [adapted paths](adapted-files.json), [review patch](root-adaptations.patch), [original delivery manifest](original-MANIFEST.json).
Adaptations resolve canonical-root versus embedded-consumer files, pinned source Git paths, synchronization target/receipt paths, structural checks, local package output, optional tool roots, tests and active installation/maintenance references. Role identities, lifecycle stages, approval gates, package selection and installed consumer paths are preserved.
Added a local build/cache `.gitignore`, code companions and source-only migration evidence. No enclosing-provider files were imported: parent README/AGENTS, launcher, prepare_commit wrapper, discovery configuration, project evidence and presentation decks remain outside the requested boundary.
[Pre-adaptation impact report](impact.md), [before search](provider-assumptions-before.txt), [remaining classified references](provider-assumptions-after.md).

## Validation

[Commands/environments](commands.md) and complete `logs/` record source, exploratory and final attempts. Final portable run: 150 tests in 142.597 seconds, OK with 2 renderer skips (`logs/complete-tests.log`); final structure/integrity: `logs/complete-check.log`.
The unchanged source passed 148 portable tests, with two renderer tests skipped under default Python. Explicit renderer-environment report tests passed all 10 in both source and destination, covering those skipped cases.
Root-clone installation and root-source upgrade/promotion regressions pass. Arbitrarily renamed source passes integrity; repeated 423-member ZIP builds are byte-identical, with exactly one `asdg/` prefix and no source-only migration reports or Publish skill.
Ancillary results: component 3/3 pass in both roots; renderer-enabled presentation 30/31 pass in both, with the same existing macOS temporary-path assertion failure. Renderer-enabled video: source 7/9 pass, destination 3/9 pass; examples require external decks/build resources.
Legacy provider tests: source 257 run, 35 failures, 64 errors, 4 skips; destination 257 run, 146 errors, 4 skips. Legacy structure checker: source 17 issues, destination 21. [Every ancillary failing test and its classification](failures.md); full tracebacks remain in logs.
Exploratory portable failures exposed copied source `.git` in fixtures and a Path/string test-adaptation error; both were corrected before the final run. Earlier changing-tree runs are retained as exploratory evidence, not final validation.
Default Python lacks optional media dependencies; the existing Python 3.11 renderer environment was used without modifying it. Native client discovery/trust, live media/SDK operation and Python 3.9 runtime execution remain unverified. No failing check is waived or converted to approval.

## Provider assumptions and readiness

Must resolve before a full cutover claim: establish which retained `00-governance/src`/tests are supported versus historical, then adapt their active parent-provider dependencies; reconcile optional video tests with absent external decks or explicitly classify their supported boundary. No tests were deleted or skipped to conceal this gap.
Must resolve for existing-consumer updates: installed descriptors name the old canonical origin; synchronization deliberately rejects a different canonical identity. A bounded, explicit adoption/compatibility policy is needed; no consumer binding was changed here.
Historical references can remain: metadata source records, archived manifests, document-review history, dated Focus installation receipts, migration patches and old verification reports. These preserve real provenance and approval bindings.
Optional future cleanup: README_NEW.md, flat agents stubs, duplicate legacy runtime, experimental media/component scaffolds and historical provider terminology. All were retained for review.
The README now explains root source versus installed layout, lifecycle/role links, clone installation, verification and contribution/build commands. Installation and synchronization documents are self-contained for a newly adopted source identity; existing-consumer identity transition and legacy optional examples remain explicit gaps.
Recommendation: the portable baseline is prepared and reviewable, but the repository is NOT yet ready for an unqualified canonical-source cutover. The smallest remaining decisions/work are the retained-provider support boundary and the old-to-new canonical identity adoption path. Human review/commit and any external declaration remain separate.
The version is intentionally unchanged; the locally refreshed pilot.4 candidate is not the previously published artifact. Select a new reviewed version before any later publication. No new-repository release assets are assumed.

## Git state

[Exact git status --short](git-status-short.txt). [Exact git diff --stat](git-diff-stat.txt) is empty because the repository has no commits and all prepared files are untracked; the separate source-relative patch supplies reviewable adaptation differences. Generated ZIPs/checksums are ignored under `build/distributions/`.
Stop here for Pablo's review. This report records preparation and test evidence, not methodology acceptance or external canonical cutover.
