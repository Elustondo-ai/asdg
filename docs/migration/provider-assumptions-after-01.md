# Remaining provider references — 1

| File:line | Classification | Text |
| --- | --- | --- |
| 00-governance/docs/baseline-checkpoint-plan-r01.md:16 | historical/reference only — preserve exact provenance | asdg_provider="$PWD/agentic-sdlc-governance" |
| 00-governance/docs/logging-acceptance.md:7 | historical/reference only — preserve exact provenance | Open the existing agentic-sdlc-governance repository; wait for Drive synchronization. |
| 00-governance/docs/state-engine-verification.md:5 | historical/reference only — preserve exact provenance | Implementation and tests are confined to `agentic-sdlc-governance`; test projects live in temporary |
| 00-governance/src/agent_log_hook.py:9 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation | REPO = Path(__file__).resolve().parents[3] |
| 00-governance/src/cli_model.py:18 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation | REPO = Path(__file__).resolve().parents[3] |
| 00-governance/src/validate_agents.py:164 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation |     root = root or Path(__file__).resolve().parents[3] |
| 00-governance/tests/test_agent_config.py:6 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation | ROOT = Path(__file__).resolve().parents[3] |
| 00-governance/tests/test_agent_packages.py:9 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation | ROOT = Path(__file__).resolve().parents[3] |
| 00-governance/tests/test_cli_bootstrap.py:14 | uncertain — retained legacy provider implementation; resolve before claiming full-source validation | REPO = Path(__file__).resolve().parents[3] |
| 00-governance/types/document-reviews.json:28680 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |       "path": "scripts/prepare_commit.py", |
| 00-governance/types/document-reviews.json:28693 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |       "path": "scripts/prepare_commit.md", |
| 00-governance/types/document-reviews.json:28706 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |       "path": "scripts/tests/test_prepare_commit.py", |
| 00-governance/types/document-reviews.json:28719 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |       "path": "scripts/tests/test_prepare_commit.md", |
| 00-governance/types/migrations/speaker-coach-exporters.patch:12 | historical/reference only — preserve exact provenance |  METHOD = CONSUMER.parent / "agentic-sdlc-governance" |
| 00-governance/types/migrations/speaker-coach-exporters.patch:23 | historical/reference only — preserve exact provenance |  METHOD = CONSUMER.parent / "agentic-sdlc-governance" |
| components/video-builder/src/build_piper_video.py:13 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report | CORE = Path(__file__).resolve().parents[3] |
| components/video-builder/src/build_piper_video.py:14 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report | REPO = CORE if (CORE / '.git').exists() else CORE.parent |
| components/video-builder/tests/test_video.py:9 | must fix or explicitly retire — historical external deck/root dependency |         root=Path(__file__).resolve().parents[4]/'docs'/'presentations'/'codex-agent-skills-and-adapters' |
| components/video-builder/tests/test_video.py:14 | must fix or explicitly retire — historical external deck/root dependency |         root=Path(__file__).resolve().parents[4]/'docs'/'presentations'/'codex-agent-skills-and-adapters' |
| docs/provenance.md:4 | historical/reference only — preserve exact provenance | [agentic-sdlc-governance](https://drive.google.com/drive/folders/1CzNrE_O6Vb39BK5d4EXtA3Uj2kSAYoqL). |
| metadata/MANIFEST.json:14 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| metadata/MANIFEST.json:20 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| metadata/deliveries/0.3.0-pilot.2.json:14 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| metadata/deliveries/0.3.0-pilot.3.json:14 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| metadata/distribution.json:27 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| metadata/distribution.json:33 | historical/reference only — preserve exact provenance |       "repository": "https://github.com/Elustondo-ai/agentic-sdlc-governance", |
| scripts/build_distribution.py:65 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |     parser.add_argument('--output', type=Path, default=(CORE if (CORE / '.git').exists() else CORE.parent) / 'build/distributions') |
| scripts/lib/agent_log_hook.py:9 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report | REPO = Path(__file__).resolve().parents[3] |
| scripts/lib/cli_model.py:19 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report | REPO = CORE if (CORE / '.git').exists() else CORE.parent |
| skills/asdg-focus/installation-2026-10-18.json:5 | historical/reference only — preserve exact provenance |   "destination": "Drive project folder 1CzNrE_O6Vb39BK5d4EXtA3Uj2kSAYoqL (agentic-sdlc-governance)", |
| skills/asdg-focus/installation-2026-10-19.json:4 | historical/reference only — preserve exact provenance |   "scope": "Existing Drive-backed agentic-sdlc-governance checkout; no change to consumer bindings, registry, native subagent definitions, permissions or lifecycle state", |
| skills/asdg-presentation/src/sources.py:7 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report | sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "00-governance/src")) |
| tests/test_distribution.py:25 | still correct or compatibility — root resolver, embedded consumer path, or historical explanation; see impact report |         self.core = self.root / 'provider/asdg' |
