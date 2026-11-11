# Provider handoff regressions
[test_policy.py](test_policy.py) exercises the actual Git exporter, patch preview, application and receipt writer in independent, disposable local clones. Fixtures reuse the current Git revision. No new commits or network access are required.
Run `python3 -B -m unittest discover -s scripts/provider_component -v`. Cases cover changed patch bytes and scope, staged and unstaged starting state, mode, additions, deletions, rename endpoints, mixed patches, protected paths, portable files and client exclusion. Receipt tests compare all prior events and metadata and repeat the append.
Native Codex permission evidence is recorded separately in the planning review.
