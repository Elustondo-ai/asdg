# Standalone repository migration impact — pre-adaptation assessment

Scope: prepare an uncommitted cutover candidate. No external canonical declaration or publication.
Source: Elustondo-ai/agentic-sdlc-governance main at 0c0bad9479059837c0d6fabe438b2aba4a51e3c7, confirmed against GitHub main on 2026-11-09.
Local source is dirty: tracked deletion of asdg/scripts/lib/cli_events.py. Copy committed bytes, preserving the deletion in the old checkout.
Destination: Elustondo-ai/asdg, unborn main, empty before migration.
614 tracked product files copied, byte hashes verified; all source Git modes are 100644. No tracked product files excluded.

## Must change for standalone operation

- README and active canonical_repository metadata identify the old repository.
- scripts/lib/cli_model.py assumes a parent repository; client paths in the catalogue must remain asdg/ paths for installed copies.
- scripts/check.py can accidentally pass only because this checkout is named asdg; package link and role validation need an independent logical client layout.
- scripts/lib/cli_install_source.py reads only Git asdg/ trees. Canonical clone installation must read root files; extracted consumers keep asdg/.
- scripts/lib/cli_sync_manifest.py and cli_sync.py assume both endpoints contain asdg/. Preserve comparison/approval/conflict semantics while resolving canonical files at root.
- scripts/build_distribution.py defaults output outside the standalone repository. The enclosing scripts/prepare_commit.py wrapper is outside the requested source boundary and is not migrated.
- docs/distribution-build.md, installation.md, install-clone-prompt.md, review-loop.md, AGENTS.md and the provider-only Publish skill contain obsolete active contributor/provider instructions.
- tests/test_agent_config.py, test_portable.py and test_install.py read source through CORE.parent/asdg; use CORE directly.
- report renderer discovery, presentation --all and experimental Piper imports assume an enclosing provider directory.

## Still correct

- ZIP members and installed project paths start with asdg/. Consumer integration templates, hooks, catalogue paths and runtime project/state paths retain this prefix.
- provider identity elustondo.ai/asdg is a product identity, not a GitHub directory.
- promote/upgrade can remain conservative consumer-to-canonical contribution/adoption workflows; no second development repository is needed.
- Explicit portable package selection excludes repository tools while the complete source repository retains them.

## Historical/reference only

- metadata sources, source-manifest, archived delivery manifests, document-review history and refactor receipts preserve actual provenance.
- skills/asdg-focus/installation-2026-10-*.json, 00-governance/types/migrations/speaker-coach-exporters.patch and historical verification/baseline reports describe previous installations.
- Keep these bytes and original paths; do not transfer approvals to adapted files.

## Uncertain / future review

- 00-governance/src and tests retain duplicate legacy provider implementations. Their public/maintained status is unclear; test and report without deleting or redesigning.
- README_NEW.md, agents/ flat stubs, presentation/video/component tools, experimental Piper/eSpeak paths and migration patches are retained repository material, outside the selected portable package where excluded by its existing list.
- Provider presentation source decks and scripts/prepare_commit.py live outside old asdg/ and are deliberately outside this migration boundary. Historical examples depending on them may fail.
- Existing consumer descriptors still name the old canonical repository. Current origin matching intentionally rejects a different canonical identity: an explicit adoption compatibility decision is needed before upgrading those consumers.
- New repository has no committed source or releases yet. Do not point instructions at nonexistent ZIP assets; describe local build and later reviewed publication.

## Self-contained documentation gaps

The migrated README introduces the product and links lifecycle, roles, install/validation and synchronization, but lacks standalone contribution commands and a reliable clone route. Active build instructions require an absent parent wrapper. A short maintainer section and corrected clone paths can close those gaps without broad prose changes. Historical presentation examples require unavailable source decks and must remain identified limitations.

Full pre-adaptation search results are in provider-assumptions-before.txt. Source file hashes and modes are in tracked-source.json.
