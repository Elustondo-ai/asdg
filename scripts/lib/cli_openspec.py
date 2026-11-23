"""Plan OpenSpec's own project files for the selected clients, using the installed openspec command."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from cli_files import Conflict, read_bytes, safe_path

TOOLS = {'codex': 'codex', 'claude': 'claude'}
# Where OpenSpec may place project files. Anything else it produces is refused and nothing is planned.
ROOTS = ('openspec', '.claude', '.agents')
# The native skill ASDG's proposal wrapper needs, per client.
MARKERS = {'codex': Path('.agents/skills/openspec-propose/SKILL.md'),
           'claude': Path('.claude/skills/openspec-propose/SKILL.md')}
TIMEOUT = 60


def enabled() -> bool:
    """ASDG_OPENSPEC=0 switches the step off, for hermetic tests and machines that must not run it."""
    return os.environ.get('ASDG_OPENSPEC', '1').strip().lower() not in ('0', 'off', 'false', 'no')


def presence(root: Path, clients) -> dict:
    """File presence only, no command run: does each client hold the native proposal skill?"""
    found = {}
    for name in clients:
        if name in MARKERS:
            try:
                found[name] = 'PRESENT' if read_bytes(safe_path(root, MARKERS[name])) is not None else 'MISSING'
            except Conflict:
                found[name] = 'MISSING'
    return found


def _run(cli: str, *args, cwd=None) -> str:
    env = dict(os.environ, DO_NOT_TRACK='1', OPENSPEC_TELEMETRY='0', CI='1', NO_COLOR='1')
    result = subprocess.run([cli, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=TIMEOUT, env=env, cwd=cwd)
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        raise OSError(f'openspec exited {result.returncode}' + (': ' + lines[-1][:160] if lines else ''))
    return result.stdout


def generated(cli: str, clients) -> dict:
    """Run `openspec init` in a disposable folder and return what it wrote, as {relative path: bytes}."""
    with tempfile.TemporaryDirectory(prefix='asdg-openspec-') as area:
        target = Path(area) / 'project'
        target.mkdir()
        _run(cli, 'init', str(target), '--tools', ','.join(TOOLS[name] for name in clients),
             '--no-animation', '--no-copilot-cloud', cwd=area)
        files = {}
        for path in sorted(target.rglob('*')):
            relative = path.relative_to(target)
            if path.is_symlink() or relative.parts[0] not in ROOTS:
                raise OSError('openspec produced an unexpected path: ' + relative.as_posix())
            if path.is_file():
                files[relative.as_posix()] = path.read_bytes()
        return files


def plan_openspec(root: Path, clients, *, skip: bool = False) -> tuple[dict, list]:
    """Return (report, additions). Additions are files missing in the target; existing files are never touched.

    A missing command, a failed run or an unexpected output yields a report and no additions: a
    separately installed tool never blocks ASDG setup.
    """
    clients = [name for name in clients if name in TOOLS]
    report = {'state': 'SKIPPED', 'clients': clients, 'version': None, 'added': [], 'kept_differing': [],
              'skills': presence(root, clients)}
    if skip or not enabled() or not clients:
        return report, []
    cli = shutil.which('openspec')
    if cli is None:
        report['state'] = 'CLI_NOT_FOUND'
        return report, []
    try:
        report['version'] = _run(cli, '--version').strip().splitlines()[-1][:40]
        files = generated(cli, clients)
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        report.update(state='FAILED', problem=str(exc)[:200])
        return report, []
    additions, added, kept = [], [], []
    try:
        for name, data in files.items():
            old = read_bytes(safe_path(root, name))
            if old is None:
                additions.append((Path(name), data))
                added.append(name)
            elif old != data:
                kept.append(name)
    except Conflict as exc:  # For example a symlink where OpenSpec's files would go.
        report.update(state='FAILED', problem=str(exc)[:200])
        return report, []
    report.update(state='PLANNED' if additions else 'PRESENT', added=added, kept_differing=kept)
    return report, additions


def note(report: dict) -> str | None:
    """One plain sentence for the setup report, or None when there is nothing to say."""
    state = report['state']
    if state == 'CLI_NOT_FOUND':
        return ('OpenSpec: the openspec command is not installed, so its project files were not planned. '
                'ASDG never downloads it; install it separately and repeat setup.')
    if state == 'FAILED':
        return 'OpenSpec: its setup could not be planned (' + report.get('problem', 'unknown') + '); ASDG setup continues without it.'
    if state == 'PLANNED':
        kept = f"; {len(report['kept_differing'])} existing differing file(s) kept as they are" if report['kept_differing'] else ''
        return (f"OpenSpec {report['version']}: {len(report['added'])} missing project file(s) planned for "
                f"{', '.join(report['clients'])}{kept}. Their content comes from the openspec command; rows show path and hash.")
    if state == 'PRESENT' and report['kept_differing']:
        return f"OpenSpec: nothing to add; {len(report['kept_differing'])} existing file(s) differ from openspec {report['version']} and were kept."
    return None
