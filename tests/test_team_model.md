# Team name, ID and specification tests

[Source](test_team_model.py). Focused tests for the pure rules in [`cli_team_model`](../scripts/lib/cli_team_model.md). They use the real role catalogue and nothing else from the project.

| Evidence | Coverage |
| --- | --- |
| Names as data | Trimming and single spaces; lifecycle words, path-like text and shell characters accepted unchanged; empty, blank, over-long, non-text, control, zero-width and line-separator names refused |
| Identity | Case, spacing and full-width variants share one identity; `ß` folds with `SS`; different names differ; collision lookup returns the saved team or `None` |
| Opaque IDs | Pattern, 300 unique values, avoidance of existing IDs, no name parameter, a name-shaped ID refused |
| Valid round trip | Sessions, subagents and teammates specifications validate, survive JSON, and come back as a separate deep copy; a real leap day and a midnight are accepted; two teams of one type and two slots of one role are valid; a sessions team has no native dispatch lead and keeps its integration owner |
| Malformed input | Forty-five single-field faults, each refused with `Conflict` and each leaving the caller's object unchanged; an unknown version and the float `1.0` are named as unsupported; the earlier values `manual`, `delegated` and `collaborative` are refused with the three current types named |

The faults cover versions, missing and extra fields, IDs, revisions, unsaved names, foreign projects, types, purposes, slots, roles including Admin, leads, rules, timestamps and definition records, including a path escape. The timestamp faults include an impossible date and time, 29 February in a non-leap year, hour 24, second 60 and a number.

These tests prove shape rules only. They exercise no store writer, claim, CLI command, skill, template or native session, and they show nothing about what a runtime loads or enforces.
