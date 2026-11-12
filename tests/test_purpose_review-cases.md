# Purpose acceptance tests: case guide

[Module guide](test_purpose_review.md) · [Source](test_purpose_review.py)

Each method below belongs to `PurposeReviewTests`, takes `self`, returns `None` and uses unittest assertions.
Names describe the intended regression checks; this index is not an execution result.

| Test method | Responsibility |
| --- | --- |
| `test_single_statement_review_preserves_both_gates` | one illustrated statement and its navigation pass through readiness and separate User acceptance. |
| `test_dropping_supplement_requires_new_review` | unregistering a reviewed supplement makes the acceptance stale. |
| `test_unchanged_nested_registration_remains_accepted` | an unchanged retired nested registration with earlier criteria still reviews and accepts. |
| `test_file_presence_never_implies_readiness_or_user_acceptance` | file presence never implies readiness or user acceptance. |
| `test_changed_document_image_and_navigation_invalidate_the_baseline` | changed document, image and navigation invalidate the baseline. |
| `test_empty_context_requires_current_human_purpose_acceptance` | empty context requires current human purpose acceptance. |
| `test_registered_and_unregistered_context_are_not_replaced_by_empty_acceptance` | registered and unregistered context are not replaced by empty acceptance. |
| `test_context_scaffold_is_empty_but_substantive_readme_and_symlink_are_not` | context scaffold is empty but substantive readme and symlink are not. |
| `test_reassessment_requires_new_acceptance_and_preserves_history` | reassessment requires new acceptance and preserves history. |
| `test_cannot_accept_without_agent_gate_or_explicit_statement` | cannot accept without agent gate or explicit statement. |
| `test_missing_criterion_or_unsafe_path_fails_closed` | missing criterion or unsafe path fails closed. |
| `test_missing_image_broken_link_and_symlink_prevent_current_readiness` | missing image, broken link and symlink prevent current readiness. |
| `test_layout_migration_preserves_legacy_history_without_transferring_acceptance` | retired flat-to-nested migration keeps legacy history without transferring acceptance. |
| `test_current_layout_scaffold_and_empty_plan_folders_are_empty_context` | legacy Context scaffold and empty retired plan folders still read as empty Context. |
| `test_supplement_can_reference_shared_stage_image` | a supplement may reference the shared stage image but not escape it. |
| `test_state_schema_is_backward_compatible_and_review_is_purpose_only` | state schema is backward compatible and review is purpose only. |
| `test_navigation_may_link_to_methodology_but_not_escape_the_client` | navigation may link to methodology but not escape the client. |
| `test_definition_alone_is_acceptable_without_evidence_or_plan` | a Purpose definition alone, with no evidence or plan, reaches acceptance under the seven criteria. |
| `test_legacy_criteria_history_stays_valid_but_mixed_sets_fail` | earlier eight-criterion history stays valid; mixed or incomplete criteria sets fail. |
