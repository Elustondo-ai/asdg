# Build identity tests

[Source](test_build_identity.py). Prove that a build is named by its canonical commit, that installed clients keep that name, and that unmatched bytes are never attributed.

| Fixture or helper | Responsibility |
| --- | --- |
| `setUp`, `save(date)` | Copy the selected package into a disposable standalone canonical repository, refresh its manifest and commit it at a fixed committer time. |
| `client(name)` | Create a disposable Git client with application files and its own guidance. |
| `clone_install`, `zip_install` | Install through `cli_install.install` with a pinned commit, or extract a built ZIP and run the client's own `init` preview and apply. |
| `status_build`, `zip_record` | Read `build` from the client's `status --json` and the `metadata/build.json` inside a ZIP. |

```text
fixed-time commit ──► build twice / via CLI in another TZ ──► identical ZIP and ASDG build <UTC> · <hash>
same-second commits ──► same timestamp, different hash and build_id
clone or ZIP install ──► client build.json + installation_source.build ──► client-only commits ──► same status line
```

Covered behavior:

- the same commit builds byte-identical ZIPs, including through the real entry point under `TZ=Pacific/Kiritimati`, named by commit time rather than build time;
- two commits with the same committer timestamp differ by short hash and `build_id`;
- uncommitted package bytes build an unattributed ZIP, and an explicit `--commit` for them fails;
- clone and ZIP installs record the build in the client; later client-only commits leave `status` unchanged, while a local methodology edit reports `LOCAL_CHANGES`;
- a ZIP whose record does not describe its files is refused before any write;
- an update after a fresh install, with or without a build record, uses the installed commit as its baseline, has no conflicts and records the new build;
- installations without a record, like existing `0.3.0-pilot.4` clients, still report their release label (and binding commit when known).

[`test_sync.py`](test_sync.md) covers the upgrade path. Run `python3 -B -m unittest tests.test_build_identity -v` from the canonical root; no network, model or real repository is touched.
