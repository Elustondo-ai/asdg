---
name: asdg-create-team
description: Set up ASDG governance and twelve specialist chats in the current project, or, when a complete team already exists, the next numbered team in its own worktree and branch. Use when the user requests their ASDG team; creating or explaining this skill alone does not create chats.
---

# ASDG create team

In Codex, give the user thirteen project chats: governance 00 and specialists 01–12, each with its own conversation focus.
These are user-owned chats sharing one repository; creating them does not assign project work or start a sprint.
For initialization, follow [init integration](initialization.md); it reuses this workflow, never a second team implementation.
Read client instructions and [session policy](../asdg-focus/session-policy.md); preserve this chat's focus.
A request to create the team, including invoking this skill for setup, authorizes the missing chats, their initial Focus prompts, a later team's worktree and local branch, and project-local ordering below, subject to the shared-preference approval gate.
An exact approved Init plan explicitly including team effects also authorizes those effects; discovery, status or editing this skill does not.

## Client mode

Codex uses native project chats below. Claude first verifies the thirteen role sources and generated skill adapters, then follows the same resolve, reuse and create steps wherever the current surface provides native session tools, as [Claude sessions](create-chats.md#in-claude) describes.
Where the surface has none, such as a plain terminal, say so, load Governance for a new project chat and offer manual specialist Focus. Never call one client's tools for the other client's target, and never report prepared sources as created chats.
Managed Claude teams, saved named agreements with a separate Start, follow [team workflows](../../00-governance/docs/team-workflows.md) only where the installed package provides the team command; otherwise report them unavailable; the role chats above are unaffected.
Creating a managed team configures it and starts nothing. Never write team state, agent definitions or client settings directly from this skill.

## Resolve the project and roles

Resolve the client root as `../../..` from this canonical skill directory.
Read [the catalogue](../../00-governance/types/agent-catalog.json) and [Focus choices](../asdg-focus/focus-choices.md).
Use their thirteen identities and labels; verify the single installed `.agents/skills/asdg-focus/SKILL.md` adapter and each catalogue role's sources.
Run `python3 asdg/scripts/cli.py status --json`; inspect current facts without treating missing stage evidence as a setup blocker.
If initialization or required role sources are missing, report the prerequisite; do not initialize or install as a side effect.
Discover the native Codex project/chat tools and use their current schemas; this workflow requires user-visible project chat creation.
Call `list_projects`; match the verified repository path and execution host to its saved project ID.
If the target is ambiguous, ask the user to select it before creating chats. Do not substitute another project or a projectless chat.

## Reuse before creating

Reuse completes one team; it never fills a new team with another team's chats. When the project's last team is already complete, this request creates the next one under [numbered teams](numbered-teams.md): a new worktree, a new branch and thirteen new chats.
Call `list_threads` with enough results to inspect this project's active chats, including pinned entries.
Use titles only to find candidates; read candidate chats for an explicit Focus selection and successful activation.
Reuse only after verifying project, role receipt, subject and stable thread ID; a title alone is not confirmation. Keep distinct subject/attitude sessions independent.
The calling chat may fill its own role when its thread ID and retained activation receipt are known.
If several chats remain plausible for a role/subject, ask which to reuse; do not silently choose the first or newest, merge their state, or create another to evade ambiguity.
If likely matches have unresolved focus or the inventory is incomplete, mark those roles unresolved and ask only about those gaps.
Preserve existing chats: no messages, focus changes, renaming, archiving or worktree moves merely to reuse them.
Keep the role-to-chat mapping in this conversation; do not create shared active-role state or read internal app databases.

## Create the missing chats

Follow [missing-chat creation](create-chats.md); retain confirmed role-to-chat IDs before ordering.

Follow [sidebar ordering](ordering.md) after confirming the roster.

## Show the team

Return a compact thirteen-role roster with actual chat titles and created/reused/unresolved outcomes; distinguish pending activation. For a numbered team, add its number, folder, branch and the files not carried.
Emit the native `::created-thread{threadId="..."}` link for every newly created chat.
State any missing tools or partial result plainly; offer the verified Focus skill for manual setup when native creation is unavailable.
The user can continue in any specialist chat; team setup leaves this chat's focus and all project-action gates unchanged.
