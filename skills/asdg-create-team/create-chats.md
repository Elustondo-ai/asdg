# Create confirmed missing team chats

Use only within [Create team](SKILL.md), after project and reuse verification.

The rules on this page apply to both clients. The tool names in this first part are Codex's; [Claude sessions](#in-claude) gives the equivalents.
Use native `create_thread` for each confirmed missing role, in small batches, with the verified project ID and local environment.
Omit model and reasoning overrides; honor any explicit user preferences. Do not create subagents or cloud tasks, and no worktree except a later team's under [numbered teams](numbered-teams.md).
Let each new chat compose its title through [the current title contract](../asdg-focus/rename-chat.md): short role, optional focus, optional attitude; keep the project binding in its receipt.
Each initial prompt must explicitly request `$asdg-focus` with its verified absolute path and that chat's catalogue role ID; no per-role picker skill is needed.
State the project root and request only activation, its required read-only opening/status, a brief role confirmation, then waiting for the user.
New chats start with subject NoFocus and attitude NoAttitude unless the user explicitly assigns them; never copy the caller's attitude or overwrite a reused chat's fields.
State that team setup assigns no documentation or application work; preserve role boundaries, existing files, approvals and sprint state.
A new chat has no inherited conversation history: pass relevant explicit user constraints with provenance, not a fabricated approval.
Do not ask the new chats to create peers, message this chat, run a project task or continue autonomously.
Retain each returned thread ID and host. After dispatch, use bounded `wait_threads` calls for up to eight targets, at most 60 seconds per wait.
Creation success is not focus activation: confirm the returned progress/receipt or report activation pending or failed.
For an uncertain creation outcome, inspect native inventory before retrying; never blindly create a duplicate.
Stop further creation after a shared permission or service failure; retain successes and report remaining roles.

## In Claude

Use this part only when the current surface offers native session tools; the Claude desktop app does, a plain terminal does not. Discover them and use their current schemas.
The project is the verified repository folder. List its sessions for reuse candidates and inspect a candidate's own record for an explicit Focus selection; a title alone never confirms a role.
Verify `.claude/skills/asdg-focus/SKILL.md` and each role's sources before creating anything. State how many chats will be created.
Start one session per confirmed missing role in the team's folder: the clone for the first team, the team's own worktree for a [numbered team](numbered-teams.md). Each is a fresh conversation, not a copy of this one, and never gets a worktree of its own unless the user asks.
Each initial prompt names the project root, asks the session to follow the canonical Focus workflow at `asdg/skills/asdg-focus/SKILL.md` for its catalogue role ID, to confirm the role briefly, and then to wait for the user.
Retain every returned session identifier. A started session is not an activated role: confirm its first report shows the role loaded, or report activation pending or failed.
Create in the batches the surface accepts. A refusal for a limit on sessions running at once is not a failure: wait for the started chats to report, then continue.
After the roster is confirmed, follow [ordering in Claude](ordering.md#in-claude): one offered sort by name, changed only with approval, and the team lead title for the calling chat. Group, pin or move Claude sessions only on the user's request.
What a surface actually did is reported per run; this page promises no session creation on a surface where it has not been observed.
