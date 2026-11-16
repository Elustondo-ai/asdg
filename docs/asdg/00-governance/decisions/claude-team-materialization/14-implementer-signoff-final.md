# Implementer sign-off by Claude Code — final

Status: **REVIEW**, recorded 2026-11-14 at the user's request, relayed by Codex. It follows my [earlier implementer review](13-implementer-signoff-claude.md), which is preserved unchanged. No other page was changed.

**Verdict: SIGNED OFF as an executable roadmap.** I can implement from the corrected [roadmap](12-implementation-roadmap.md). This is technical sign-off only. It is not user approval, not permission to start, and not native verification: Gate 1 can still return a no-go for Delegated on Desktop, and step 9 for Collaborative.

## Exact bytes signed off

The sign-off applies to these files at these SHA-256 hashes, and to no later revision of them.

| File | SHA-256 |
| --- | --- |
| `12-implementation-roadmap.md` | `ce62ffc3716ef3be616afa76ed988ec3140ac6df1a7053247497b92293c41613` |
| `images/implementation-roadmap.svg` | `61b8f16fa3f70e8a68df9f470ca3b2c904733c5e860a1e22db53c45cc4fecffd` |
| `01-team-contract.md` | `331c869dff932a3be59efc8212fe351bb968404d10e545dc4fc986f2133d21f9` |
| `02-runtime-and-state.md` | `b57e41a8e28d6d5bc1a6859522eb0664f453f2417cb37854f56ba95dd9d5ca27` |
| `03-delivery-and-acceptance.md` | `436da5389881eb335534cb858751be1cc2544830ede3233df9366cef05fb7999` |
| `04-evidence.md` | `76d615c64c83e0484f88ca6d6e805031b9aa5321938c5718f835d9000ace6bb5` |
| `05-concurrency-and-ownership.md` | `58dc1fec62a7e2a07fd48c15f61a8aa3354fb1b943fa5380c662a859ce6be2f8` |
| `08-writer-and-policy.md` | `36e86fd2e9a58ad865b5ba728cf17014abf83cec2f0276a4931a4ebfbd8b189d` |
| `README.md` | `97e82b1c712c7fec6ea408bac9728e3e9fd3c2dccbccd55c1e5ba98b0323b470` |

## Corrections from the earlier review

| Correction | Result |
| --- | --- |
| 1. Adapter update path | Incorporated as option (a). Roadmap step 2 and the `cli_clients.py`, `cli_project.py` row of [08](08-writer-and-policy.md) require an ownership-aware refresh: replace only on an exact match with the verified installed-build rendering, keep edited or unprovable adapters as conflicts, and cover new adapters and the chooser in one preview and token. The installed-build-to-candidate acceptance is added. [01](01-team-contract.md) and [02](02-runtime-and-state.md) now route Focus repair through this extension. |
| 2. Gate 1 exit | Incorporated. [03](03-delivery-and-acceptance.md) and roadmap step 1 record Collaborative as Deferred. |
| 3. Delivery rhythm | Incorporated. Step 2 is delivered with Manual and may be subdivided; step 5 runs in the actual client after delivery; change records and ledger receipts are kept. |

## Implementation notes, no change required

- **Baseline capture.** The refresh runs in the client, which has no access to canonical history, and the upgrade replaces the old templates. I will record the installed-build adapter renderings during the upgrade apply, while the old templates are still on disk and the build record shows no local changes. This is inside step 2.
- **Wording.** The opening section of 08 still says Focus repair uses "the existing adapter refresh". Its table row and closing paragraph define the extension, so I read that sentence as the extended refresh.
- **Authorization.** The reading in my earlier review still applies: an assigned step covers its routine work; commit, push, Alice updates, hook entries or trust in a real client, CLI installation, the experimental teams setting, a real host identity file and a recovery release each need the user's own word.

## First executable step

**Preparation step 1, Gate 1 on Desktop.** Remaining prerequisites:

- the user's assignment of step 1; this sign-off is not that assignment;
- a disposable Git project with one linked worktree, outside Alice and canonical, which I can create under that assignment;
- at least two fresh Desktop sessions opened on that folder, one before its first `.claude/agents/` file exists and one after;
- the user accepting the trust prompt there, if the surface shows one, so the probe hook runs.

Nothing needs installing for step 1.

## What was checked

All pages are within 50 nonblank lines and relative links resolve. The latest hash of every file in `review.json` matched disk, and my four earlier reviews keep their original hashes. The refresh behaviour behind correction 1 was read in canonical at `f2b8591`. Canonical's checks were not run. No implementation, native trial, installation, setting change, commit or push was made.
