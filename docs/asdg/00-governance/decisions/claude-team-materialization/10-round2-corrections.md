# Round 2 corrections and final review request

Status: **REVIEW REQUESTED**, 2026-11-14. [Claude round 2](09-review-claude-round2.md) found no original blocker remaining and requested seven corrections. This page maps their incorporation; native evidence and user acceptance remain separate.

| Correction | Where incorporated |
| --- | --- |
| 1. Chooser/client policy | 01 corrects current versus proposed behavior; 08 gives the Claude renderer its own explicit-only metadata, preserving shared policy. |
| 2. Session/foreign-host claims | 02 names verified skill session ID and hook correlation, host-local identity, foreign-host recovery, conflict-copy interruption, and single-host limitation despite Drive synchronization. |
| 3. Protected apply paths | 03 Gate 1 tests config/common-directory writes; 04 cites protected paths; apply previews supply a human-run fallback, not weakened protections. |
| 4. Hook ownership/increment/filter | 08 names reviewed team setup-observer preview/apply in increment 3 and worker controls in increment 4; settings edits are separate from discovery and filter to the claim owner/registered members. |
| 5. Lead boundary | 02, 03, 05, 08 distinguish restricted workers from the instruction-bound lead. No whole-team path-enforcement claim. |
| 6. Loading receipt | 02 defines invocation plus returned embedded fingerprint, strengthened by hook identity when available; no worker shell needed and early evidence is explicitly weaker. |
| 7. Teammate identity | 02 requires mapping IDs/names to registered members; no assumed teammate agent_type. Unknown mapping blocks document-write readiness. |

Smaller points: Manual validates Focus and routes repairs to the existing refresh; status includes Unknown/Unsupported; Gate 1 uses hand-made disposable definitions before a generator exists. The existing-directory hot-reload behavior is recorded, supporting the prohibition on active-run repairs.

Round 3 returned [no remaining blocker](11-review-claude-round3.md). Its non-blocking clarifications are now incorporated: complete stores, early uncorrelated session IDs, scoped control failures, chooser metadata, disposable hook probes, and current review status. No native test or implementation was performed; final clarifications have not had another independent pass.

Historical review request: please check the corrections against pages 01–05 and 08 and return a final design verdict. Distinguish a genuine contradiction from a deliberate later native go/no-go test. No runtime trial, implementation, setting change, commit, or push is requested. Preserve 06 and 09 as historical reviews.
