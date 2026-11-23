# Sprint align skill tests

[Source](test_sprint_align_skill.py). Checks the structure of [Sprint align](../skills/asdg-sprint-align/SKILL.md): what code can verify about a workflow that agents carry out.

| Test | Evidence |
| --- | --- |
| Every page is packaged and reachable from the entry page | The six pages are package members and the entry page links the other five |
| The entry page states the rule, owner, results and limits | Its four sections, the three results, the rule's key sentence and the no-state-change limit are present |
| Reviews define four verdicts and six relationships | The verdict names and exactly six relationship rows exist |
| Routing forwards from a specialist and excludes Admin | The forwarding rule, the no-invented-address rule and the Admin exclusion are present |
| The scenarios cover the twelve cases and routing | Rows A1 to A12 and R1 to R4 exist, in order |
| Sprint start, stage 09, Planning, the gate, Help, the index and usage point to the skill | Each page links the entry page |
| Both clients get an adapter that the model may invoke | The template is a public skill, not explicit-only, and the Claude adapter links the canonical workflow and carries the forwarding instruction |

Run with `python3 -B -m unittest discover -s asdg/tests -p "test_sprint_align_skill.py"`.

## Limits

These are wording and link checks. They execute no alignment, start no chat and prove nothing about how a client or an agent behaves; that is observed in a real client and recorded per trial, as [the scenarios](../skills/asdg-sprint-align/TRY-IT.md) require.
The adapter is resolved from the directory above the distribution, so the test expects the embedded layout `asdg/` or a checkout named `asdg`.
