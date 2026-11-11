# Operator procedure for a provider component
Pablo runs the trusted [review tool](review.py) from the authoritative provider root. ASDG-09 opens only the independent clone. [Ownership and scope](policy.md) apply throughout.

1. Outside the source checkout, Google Drive, temporary directories shared with the agent, and all implementation writable roots, create a private directory for the assignment, starting record and returned patch. Set `review_dir` to that absolute directory and `copy` to a **new**, separate checkout path. Keep the source checkout outside every implementation writable root.
2. In your terminal, obtain the physical root with `pwd -P` and full revision with `git rev-parse HEAD`. Review this assignment shape, substitute the real values, and save it as `$review_dir/assignment.json`. Select ASDG-09 explicitly for that assignment.
```json
{"root":"/absolute/provider","revision":"FULL_HEAD","role_id":"ASDG-09","component":"example","objective":"Exercise the example","targets":["components/example/result.txt"],"acceptance":["result.txt contains fixture-ok"]}
```
3. Run the following from the authoritative root. Keep the successful start record under your control. Give ASDG-09 the assignment, acceptance criteria and a read-only copy of the successful start record.
```sh
provider=$(pwd -P)
tool="$provider/scripts/provider_component/review.py"
python3 -B "$tool" prepare "$review_dir/assignment.json" "$copy" > "$review_dir/start.json"
```
4. Put the explicit ASDG-09 selection, assignment, acceptance tests and absolute export command from step 5 in `$review_dir/task.txt`. Use the tested Codex CLI settings below from the copy. Inspect effective permissions, ensure the implementation has no other writer to the source or review directory, and use a fresh session for each assignment.
```sh
(cd "$copy" && codex -a never exec --ephemeral --ignore-user-config --ignore-rules --sandbox workspace-write -c 'features.apps=false' -c 'sandbox_workspace_write.exclude_tmpdir_env_var=true' -c 'sandbox_workspace_write.exclude_slash_tmp=true' - < "$review_dir/task.txt")
```
5. Run the acceptance tests inside the clone. From that same sandbox, invoke the trusted script by absolute path to export all tracked changes and non-ignored new files. It uses a temporary private index, compares against the prepared starting tree and creates a new `candidate.patch` in the clone. Inspect ignored files separately.
```sh
python3 -B "$provider/scripts/provider_component/review.py" export "$review_dir/start.json"
```
6. After the implementation session exits, copy the candidate into the private review directory from your own terminal. Inspect the whole patch, the original assignment and test evidence. Preview from the authoritative root. The result names both endpoints, the patch SHA-256, starting revision and a confirmation token covering the entire start record.
```sh
cp "$copy/candidate.patch" "$review_dir/candidate.patch"
python3 -B "$tool" preview "$review_dir/start.json" "$review_dir/candidate.patch"
python3 -B "$tool" apply "$review_dir/start.json" "$review_dir/candidate.patch"
```
7. Type `APPLY <approval-token-from-reviewed-preview>` personally in the trusted terminal. Keep the authoritative tree free of concurrent writers during validation and apply. Git consumes the same in-memory patch bytes that passed validation. Review `git status --short` and the applied changes, including new files. A commit is a separate decision.
