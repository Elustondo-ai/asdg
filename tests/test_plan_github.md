# GitHub planner protocol tests

These tests run the actual adapter against a deterministic fake transport without creating external Issues or Projects.

| Component | Responsibility | Collaborators |
| --- | --- | --- |
| `Fake` | Route REST/GraphQL requests and capture mutation payloads | `GitHub` transport injection |
| Fixture helpers | Build issue, Project, field and paginated responses | Protocol tests |
| `GitHubPlanTests` | Exercise boundaries and observable payloads | `cli_plan_github`, `unittest.mock` |

Coverage includes every paginated collection, repository/PR filtering, absent versus inaccessible Projects, duplicate titles/fields/identities, malformed pagination, GraphQL field-union selection, marker round trips, narrow issue updates, Project creation and field mutations, select/iteration resolution, credential failures and sanitized definite-rejection versus unknown-outcome errors without retries.

Run `python3 -B -m unittest discover -s tests -p 'test_plan_github.py' -v` from the canonical source. No network authentication is required. Passing results validate adapter behavior against the recorded protocol contract; native skill discovery and live GitHub behavior remain separate checks.
