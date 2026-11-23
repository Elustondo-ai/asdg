# First pass and reconciliation

Four stages look at the same sprint baseline separately, then their conclusions are brought together. Independence means each first report is written before seeing the others' new conclusions; it does not mean withholding upstream context.

| Stage | Question for this sprint | Evidence it must cite |
| --- | --- | --- |
| 02 Purpose | Why the change matters | Outcome, constraints, non-goals, and how the sprint goal relates to the product purpose |
| 03 Use Cases | Who does what, and what happens | Actors, scenarios, observable outcomes, exceptional interactions |
| 04 Evaluation | How success is established | Criteria, method, observations, justified thresholds or measurement limits |
| 05 Architecture | How the solution supports the need | Responsibilities, interfaces, data flow, constraints, alternatives, material uncertainty |

Assess the consuming project's artifacts at its registered documentation root, normally `docs/asdg/`. The folders inside `asdg/` define the methodology and are not evidence about the application.
Stage 01 is consulted when domain assumptions change. Stage 07 takes part from the start as planning owner.

## The brief

Planning writes one brief and gives the same text to all four: the sprint snapshot, a stable ID for each material commitment (for example `S003-ANSWER`), relevant constraints, current explicit stakeholder direction, and the exact source paths with revisions or hashes.

## Each first-pass report

Read-only against the shared baseline. Each stage saves its own report in its own stage folder, so parallel reviewers cannot overwrite one another, and returns the link.
It states the reviewed baseline; the commitments covered; source sections and revisions; missing, contradictory or ambiguous content; required amendments or an evidenced no-change conclusion; downstream implications; and one verdict:
`ALIGNED`, `CHANGE_REQUIRED`, `NEEDS_DECISION` or `MISSING_EVIDENCE`.
Existing adequate content is reused and a no-change finding is valid. Empty folders, stage labels, links or an unsubstantiated pass are not.
Technical maintenance traces to an existing workflow, quality requirement or operational invariant; never invent a user-facing feature to justify it.

## Reconcile the cascade

Planning assembles the coverage record; the coordinator takes each concrete disagreement back to its owner. Judge meaning, not matching words.

| Relationship | Must hold |
| --- | --- |
| Purpose → Use Cases | The scenarios deliver the intended outcome for the intended actors |
| Purpose → Evaluation | Passing the evaluation would demonstrate the benefit and respect its constraints |
| Purpose → Architecture | The solution stays within product boundaries and non-goals |
| Use Cases → Evaluation | Success paths, failures and state changes have observable criteria and a method |
| Use Cases → Architecture | Responsibilities, interfaces and information flow can deliver each behavior |
| Evaluation → Architecture | The design exposes the observations the evaluation needs |

Link every material commitment to its purpose rationale, scenario or technical obligation, evaluation criterion and architectural support; mappings may be many-to-many. Check the reverse too: new behavior, tests or components need an authorized reason.
Close a gap with the smallest change in the owning artifact, then recheck the affected relationships. Never weaken a requirement to pass a test, rewrite Purpose to justify arbitrary work, or blur a disagreement. Agents voting does not settle a product decision.
A current explicit human instruction outranks an older deferral; the stale documents and any sprint-record mismatch are still reconciled through the existing procedures. A changed document does not inherit approval of its earlier bytes.
Use one assessment round and normally one correction round. A conflict that remains returns as a decision brief: evidence, impact, viable options, recommendation and decision owner. Reaching the round limit is not success.
When all four are reconciled the result is `FOUNDATION_ALIGNED`; a material technical uncertainty may remain if it is explicitly framed for stage 06.
