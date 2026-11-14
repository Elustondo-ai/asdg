# Build a portable ASDG ZIP

`build_distribution.py` selects and verifies the canonical package before creating a local artifact.
It uses Python's standard library and makes no network or model requests.

![Reviewed package files become a verified ZIP, then a locally initialized client.](../docs/images/distribution-flow.svg)

| Interface | Responsibility and effects |
| --- | --- |
| `refresh_manifest(core)` | Validate selected sources and record current hashes; changes only the current manifest, never delivery history or approval. |
| `attribute(core, entries, version, commit=None)` | Return a [build record](lib/build_identity.md) only when every selected file equals the commit (default HEAD); an explicit unmatched `--commit` fails, an unmatched HEAD prints `UNATTRIBUTED`. |
| `build(core, output, commit=None)` | Check integrity, freeze/recheck bytes, add `asdg/metadata/build.json` when attributed, write deterministic ZIP entries and a checksum sidecar; returns the ZIP path. |
| `main()` | Parse `--output`, `--commit` and explicit `--refresh-manifest`; print the ZIP path and `ASDG build <UTC> · <short hash>`; report failures with nonzero exit. |

The file-list resolver rejects traversal, symlinks, duplicates and missing files.
The package checker validates links against selected files, so a provider-only file cannot hide a missing dependency.
Archive entries begin with `asdg/`, use stable timestamps and regular-file permissions, and preserve source bytes.
An attributed ZIP is named `asdg-<release>-<build_id>.zip`; rebuilding that commit later reproduces its bytes. Unattributed builds keep `asdg-<release>.zip` and may replace that local artifact; building never publishes or modifies client state.
Run the [distribution tests](../tests/test_distribution.md) to check exclusion, reproducibility and extraction behavior.

In a standalone Git source checkout the default output is local `build/distributions/`; the ZIP still has exactly one top-level `asdg/`.
