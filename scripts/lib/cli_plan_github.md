# GitHub planning transport

This module maps explicit planner synchronization to GitHub.com Issues and Projects; it never changes local sprint authorization.

| Component | Responsibility | Collaborators |
| --- | --- | --- |
| `GitHub` | Authenticate, paginate reads, expose narrow mutations | Sync orchestrator, fixed GitHub API |
| `snapshot` | Read repository issues and matching Project fields | REST Issues, GraphQL Projects |
| `validate_fields` | Reject unavailable or ambiguous field values | Preview and apply |
| `split_marker` / `marked_body` | Preserve issue identity and exact prose | Issue creation, updates, recovery |

`GitHub(token=None, transport=None)` uses an existing `GH_TOKEN`, `GITHUB_TOKEN` or authenticated `gh` CLI. An injected transport takes `(method, API-relative path, JSON body)` and returns decoded JSON for tests. Production requests use only `https://api.github.com`, reject redirects, time out after 30 seconds, and never retry mutations automatically. Credentials and response error bodies are not printed.

`snapshot(repository, project_config)` accepts `owner/repository` and `{owner, number, title}`. A number binds an existing Project; a missing/inaccessible numbered Project is an error. Without a number, a unique exact title is reused; duplicate or closed matches fail. Only absence from a successful complete listing permits creation.

The snapshot contains `repository`, `repository_id`, `project`, `issues`, `fields` and `missing_fields`. Issues include stable `id`, `issue_number`, node/item IDs, URL, update time and logical fields. All repository Issues, open and closed, are read; pull requests and other-repository Project items are excluded. Issue, Project, field, item and item-value collections are paginated. Missing/inaccessible entries and duplicate identities fail closed.

Managed field keys are `status`, `priority`, `team` and `sprint`, mapped to `Status`, `ASDG Priority`, `ASDG Team` and `ASDG Sprint`. Missing Status gets Todo/In Progress/Done options; other missing fields are text. Existing compatible select fields resolve exact unique option names. Existing ASDG Sprint iteration fields resolve exact unique iteration titles, including completed iterations. The adapter never invents sprint dates or changes iteration configuration.

`create_project` returns Project metadata and links the repository. `create_field` makes one named field. `create_issue` returns an open issue with a stable HTML marker; closing is a separate operation. `update_issue` patches only supplied title/body/state values and preserves existing markers. `add_item` returns the Project item ID. `update_fields` changes or clears exactly one field per call so the caller can journal each mutation.

GitHub supplies no compare-and-swap transaction across these objects. The orchestrator owns preview freshness, local backups, mutation journaling and recovery. `GitHubRejected`, a `Conflict` subclass, identifies missing/invalid credentials before transmission, definite HTTP 400/401/403/404/409/410/422 rejection, or a well-formed GraphQL request-error response with no `data` entry. Other transport/server failures and all GraphQL errors with `data` present, even null, retain an unknown outcome as `Conflict`; they never authorize automatic retry. HTTP error response bodies are closed without printing their contents.

Protocol sources: [Projects API workflow](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects), [Projects GraphQL schema](https://docs.github.com/en/graphql/reference/projects), [REST Issues](https://docs.github.com/en/rest/issues/issues), and [GraphQL request versus field errors](https://graphql.org/learn/response/).

Tests use injected protocol responses; they do not establish live token permissions or service acceptance.
