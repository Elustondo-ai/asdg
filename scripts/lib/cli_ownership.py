"""Best-effort role write ownership; independent of sprint authorization."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from cli_files import Conflict, safe_path
from cli_model import CORE, REPO, catalogue
from cli_project import distribution


def local_path(root: Path, value: str) -> Path:
    """Normalize one literal file target without following links or traversal."""
    if not isinstance(value, str) or not value or value != value.strip() or any(c in value for c in '\\*?[]\n\r'):
        raise Conflict('Write target must be a literal local file.')
    path = Path(value)
    if path.is_absolute():
        path = path.relative_to(root)
    if not path.parts or '..' in path.parts:
        raise Conflict('Write target escapes the project.')
    safe_path(root, path)
    return path


def owned_directory(role: str, repo: Path = REPO) -> Path | None:
    """Derive every project-role destination from the canonical catalogue."""
    for row in catalogue(repo)[0]:
        if row['role_id'] == role:
            return Path('docs/asdg') / Path(row['folder']).name
    return None


def checker_target(root: Path, path: Path) -> bool:
    """Reserve the checker, its import names and enclosing directories for owner application."""
    checker = Path('scripts/lib/cli_ownership.py')
    if root != CORE:
        checker = Path('asdg') / checker
    target = root / path
    if target.exists() and (root / checker).exists() and target.samefile(root / checker):
        return True
    folded = Path(*(part.casefold() for part in path.parts))
    if folded in checker.parents:
        return True
    if not folded.is_relative_to(checker.parent):
        return False
    names = folded.relative_to(checker.parent).parts
    if names[0] == '__pycache__':
        return len(names) == 1 or names[1].startswith('cli_ownership.')
    return names[0] == checker.stem or (names[0].startswith('cli_ownership.') and names[0] != 'cli_ownership.md')


def standalone_source(root: Path) -> bool:
    """Verify that root is the canonical standalone ASDG source, not a client or a copy."""
    if not (root / '.git').is_dir() or (root / '.git').is_symlink() or os.path.lexists(root / 'asdg'):
        return False
    cwd = Path.cwd()
    if any(os.path.lexists(parent / '.asdg') for parent in (root, *root.parents, cwd, *cwd.parents)):
        return False
    canonical = 'https://github.com/Elustondo-ai/asdg'
    origins = {canonical, canonical + '.git', 'git@github.com:Elustondo-ai/asdg.git',
               'ssh://git@github.com/Elustondo-ai/asdg.git'}

    def git(*args: str) -> bytes:
        # Git's repository and configuration environment overrides must not supply the identity.
        return subprocess.check_output(['/usr/bin/git', '-C', str(root), *args], stderr=subprocess.DEVNULL,
                                       timeout=5, env={'PATH': os.defpath, 'GIT_CONFIG_NOSYSTEM': '1',
                                                       'GIT_CONFIG_GLOBAL': os.devnull})
    try:
        return (distribution(root).get('canonical_repository') == canonical
                and git('rev-parse', '--show-toplevel').rstrip(b'\n') == os.fsencode(root)
                and git('config', '--local', '--get', 'remote.origin.url').decode().strip() in origins)
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
        return False


def admin_refusal(root: Path, path: Path) -> str | None:
    """Scope of human-authorized Admin maintenance; None permits the exact target.

    Standalone source: every methodology file in the verified checkout.
    Embedded client: the `asdg/` copy, the generated root bootstrap and Admin's
    Stage 07 change records. Never Git metadata, client application files or state.
    """
    if any(part.casefold() == '.git' for part in path.parts):
        return f'WRITE BLOCKED: Git metadata and Git operations remain human-controlled: {path}.'
    target = root / path
    if any(parent.is_symlink() for parent in (target, *target.parents) if root in parent.parents):
        return f'WRITE BLOCKED: Admin target crosses a symbolic link: {path}.'
    if target.exists() and (not target.is_file() or target.stat().st_nlink != 1):
        return f'WRITE BLOCKED: Admin targets are single-link files, not directories or aliases: {path}.'
    if any(os.path.lexists(root / parent / '.git') for parent in path.parents if parent.parts):
        return f'WRITE BLOCKED: {path} belongs to a nested repository.'
    # Source mode follows verified identity, not the location of the running checker.
    if standalone_source(root):
        if path.parts[0] == 'asdg':
            return f'WRITE BLOCKED: {path}: `asdg/` is the consumer layout, not part of the standalone source.'
        return None
    if root == CORE:
        return f'WRITE BLOCKED: {path}: this checkout is not the verified standalone ASDG source.'
    record = (len(path.parts) == 4 and path.parts[:3] == ('docs', 'asdg', '07-planning')
              and path.name.startswith('02.') and path.suffix in {'.md', '.json'})
    if path.parts[0] == 'asdg' or path == Path('AGENTS.md') or record:
        return None
    return f'OUT_OF_SCOPE: {path} is outside the embedded methodology; Admin does not own client application files or state.'


def ownership_decision(root: Path, paths: list[str], context: dict, repo: Path = REPO) -> tuple[bool, str, list[str]]:
    """Return allow/reason/application targets; caller separately checks sprint scope.

    Context is a declaration from the conversation (CLI) or session-bound harness
    (hook), never authentication. Exception targets are exact, task-authorized files.
    """
    role = context.get('role_id')
    owner = owned_directory(role, repo)
    if owner is None and role != 'ASDG-ADMIN':
        return False, 'WRITE BLOCKED: unknown role identity; reload or reaffirm the role.', []
    if not paths:
        return False, 'WRITE BLOCKED: specify every target.', []
    workflow = context.get('workflow')
    exceptions = {local_path(root, p) for p in context.get('targets', [])}
    application = []
    for value in paths:
        path = local_path(root, value)
        # Admin is an authority class, not a list of exceptions: an exact target the human
        # authorized for this maintenance task is decided by the methodology scope alone.
        if role == 'ASDG-ADMIN' and workflow == 'admin' and path in exceptions:
            refusal = admin_refusal(root, path)
            if refusal:
                return False, refusal, []
            continue
        if checker_target(root, path):
            return False, 'WRITE BLOCKED: ownership checker changes require authorized ASDG Admin maintenance.', []
        # Policy/control paths are never application or ordinary documentation.
        protected = any(p in {'.git', '.codex', '.claude', '.agents', 'AGENTS.md', 'SKILL.md'} for p in path.parts)
        # Reserve the source stage namespace before client exceptions or application fallback.
        if root == CORE and re.match(r'^(?:0[0-9]|1[0-2])-', path.parts[0]):
            return False, f'WRITE BLOCKED: standalone methodology target {path} requires authorized ASDG Admin maintenance.', []
        if protected or path.parts[0] == 'asdg':
            return False, f'WRITE BLOCKED: protected methodology/control target {path}.', []
        if path == Path('.asdg/document-reviews.json') and workflow == 'review-receipt':
            continue  # Append-only authorship; semantic validation remains in the workflow.
        if path in exceptions:
            if workflow in {'approve', 'purpose-review'} and path == Path('.asdg/lifecycle.json'):
                if workflow == 'approve' or role == 'ASDG-02':
                    continue
            if workflow in {'sprint-start', 'sprint-close'} and path == Path('.asdg/sprint.json'):
                continue
            if workflow == 'sprint-close' and path.parent == Path('.asdg/sprint-closeouts') and path.suffix == '.json':
                from uuid import UUID
                UUID(path.stem)
                continue
            if workflow == 'shared-record' and role == 'ASDG-COORDINATOR' and path.parts[:2] == ('docs', 'shared'):
                continue
        if path.parts[0] == '.asdg':
            return False, f'WRITE BLOCKED: shared state requires its explicit utility: {path}.', []
        if role == 'ASDG-08' and workflow == 'openspec' and path in exceptions:
            store = local_path(root, context.get('openspec_store', ''))
            # Never let a declared store override specialist or control ownership.
            if store.parts[0] not in {'docs', 'asdg', '.asdg', '.git', '.codex', '.claude', '.agents'} and store in path.parents:
                continue
        if owner is not None and owner in path.parents:
            from cli_hook import documentation_target
            if documentation_target(root, str(path)):
                continue
        if role == 'ASDG-09' and owner in path.parents:
            application.append(str(path))
            continue
        if path.parts[:2] == ('docs', 'asdg'):
            return False, f'OUT_OF_SCOPE: {path}; save a proposal in {owner or "the authorized Admin record"} or return a handoff to its owner.', []
        if role == 'ASDG-09' and path.parts[0] not in {'.asdg', 'asdg'}:
            application.append(str(path))
            continue
        return False, f'OUT_OF_SCOPE: {path}; propose the change in {owner or "the authorized Admin record"} or return a handoff.', []
    return True, 'Role ownership checked; workflow authorization and content obligations still apply.', application
