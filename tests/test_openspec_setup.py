"""Setup plans OpenSpec's missing project files, add-only, through a stand-in openspec command."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE / 'scripts/lib'))
from distribution_files import package_files

# A stand-in for the separately installed command: same arguments, tiny fixed output.
FAKE = r'''#!/bin/sh
if [ "$1" = "--version" ]; then echo "9.9.9"; exit 0; fi
if [ "$FAKE_OPENSPEC" = "fail" ]; then echo "boom" >&2; exit 3; fi
target="$2"; tools="$4"
mkdir -p "$target/openspec"
printf 'schema: spec-driven\n' > "$target/openspec/config.yaml"
case "$tools" in *claude*)
  mkdir -p "$target/.claude/skills/openspec-propose" "$target/.claude/commands/opsx"
  printf 'claude propose skill\n' > "$target/.claude/skills/openspec-propose/SKILL.md"
  printf 'claude propose command\n' > "$target/.claude/commands/opsx/propose.md";;
esac
case "$tools" in *codex*)
  mkdir -p "$target/.agents/skills/openspec-propose"
  printf 'codex propose skill\n' > "$target/.agents/skills/openspec-propose/SKILL.md";;
esac
if [ "$FAKE_OPENSPEC" = "stray" ]; then mkdir -p "$target/elsewhere"; echo x > "$target/elsewhere/file"; fi
exit 0
'''
CLAUDE_FILES = ['.claude/commands/opsx/propose.md', '.claude/skills/openspec-propose/SKILL.md', 'openspec/config.yaml']


class OpenSpecSetupTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-openspec-test-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        self.root = self.area / 'client project'
        for source in package_files(CORE):
            target = self.root / 'asdg' / source.relative_to(CORE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        core, manifest = self.root / 'asdg', self.root / 'asdg/metadata/MANIFEST.json'
        value = json.loads(manifest.read_text())
        value['files'] = {p.relative_to(core).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in package_files(core) if p != manifest}
        manifest.write_text(json.dumps(value) + '\n')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.bin = self.area / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'openspec'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        git = Path(shutil.which('git')).parent
        self.base_path = os.pathsep.join([str(git), '/usr/bin', '/bin'])

    def env(self, installed=True, mode='', switch='1'):
        path = (str(self.bin) + os.pathsep if installed else '') + self.base_path
        return dict(os.environ, PATH=path, ASDG_OPENSPEC=switch, FAKE_OPENSPEC=mode)

    def run_cli(self, *args, entry='init.py', expect=0, env=None):
        result = subprocess.run([sys.executable, '-B', str(self.root / 'asdg/scripts' / entry), *args], cwd=self.root,
                                capture_output=True, text=True, timeout=60, env=env or self.env())
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result

    def preview(self, *args, env=None):
        return json.loads(self.run_cli(*args, '--dry-run', '--json', env=env).stdout)

    def apply(self, *args, env=None):
        report = self.preview(*args, env=env)
        self.run_cli(*args, '--apply', '--plan', report['plan'], env=env)
        return report

    def openspec_rows(self, report):
        return sorted(row['path'] for row in report['files'] if row['kind'] == 'openspec')

    def test_missing_files_are_planned_and_applied_for_the_selected_client_only(self):
        report = self.preview('--client', 'claude')
        self.assertEqual((report['openspec']['state'], report['openspec']['version']), ('PLANNED', '9.9.9'))
        self.assertEqual(self.openspec_rows(report), CLAUDE_FILES)
        self.assertEqual(sorted(report['openspec']['added']), CLAUDE_FILES)
        self.assertTrue(any(note.startswith('OpenSpec 9.9.9: 3 missing') for note in report['notes']))
        self.assertFalse((self.root / 'openspec').exists())  # The preview wrote nothing.
        self.run_cli('--client', 'claude', '--apply', '--plan', report['plan'])
        self.assertEqual((self.root / '.claude/skills/openspec-propose/SKILL.md').read_text(), 'claude propose skill\n')
        self.assertFalse((self.root / '.agents').exists())  # Codex was not selected.
        verify = json.loads(self.run_cli('verify', '--json', entry='cli.py').stdout)
        self.assertEqual((verify['openspec_skills'], verify['openspec_project']), ({'claude': 'PRESENT'}, True))
        again = self.preview('--client', 'claude')
        self.assertEqual((again['openspec']['state'], again['planned_files']), ('PRESENT', []))

    def test_an_existing_file_is_never_overwritten(self):
        config = self.root / 'openspec/config.yaml'
        config.parent.mkdir()
        config.write_text('schema: spec-driven\ncontext: local choice\n')
        report = self.apply('--client', 'claude')
        self.assertEqual(report['openspec']['kept_differing'], ['openspec/config.yaml'])
        self.assertNotIn('openspec/config.yaml', self.openspec_rows(report))
        self.assertEqual(config.read_text(), 'schema: spec-driven\ncontext: local choice\n')
        self.assertTrue((self.root / '.claude/commands/opsx/propose.md').is_file())

    def test_a_missing_command_is_reported_and_setup_continues(self):
        env = self.env(installed=False)
        if shutil.which('openspec', path=env['PATH']):
            self.skipTest('an openspec command sits beside git on this machine')
        report = self.apply('--client', 'claude', env=env)
        self.assertEqual((report['openspec']['state'], self.openspec_rows(report)), ('CLI_NOT_FOUND', []))
        self.assertTrue(any('not installed' in note and 'never downloads' in note for note in report['notes']))
        self.assertTrue((self.root / '.claude/skills/asdg-status/SKILL.md').is_file())
        self.assertFalse((self.root / 'openspec').exists())
        text = self.run_cli('verify', entry='cli.py', env=env).stdout
        self.assertNotIn('OpenSpec', text)  # A project that does not use OpenSpec is not nagged.

    def test_a_failing_or_misbehaving_command_never_blocks_setup(self):
        for mode, problem in (('fail', 'openspec exited 3: boom'), ('stray', 'unexpected path: elsewhere')):
            with self.subTest(mode=mode):
                report = self.preview('--client', 'claude', env=self.env(mode=mode))
                self.assertEqual((report['openspec']['state'], self.openspec_rows(report)), ('FAILED', []))
                self.assertIn(problem, report['openspec']['problem'])
                self.assertTrue(any('could not be planned' in note for note in report['notes']))

    def test_the_step_can_be_switched_off(self):
        by_flag = self.preview('--client', 'claude', '--no-openspec')
        by_env = self.preview('--client', 'claude', env=self.env(switch='0'))
        for report in (by_flag, by_env):
            self.assertEqual((report['openspec']['state'], self.openspec_rows(report)), ('SKIPPED', []))
        self.assertEqual(by_flag['openspec']['skills'], {'claude': 'MISSING'})

    def test_verify_notes_a_client_without_the_skills_in_an_openspec_project(self):
        self.apply('--client', 'codex')
        self.apply('--client', 'claude', '--no-openspec')
        report = json.loads(self.run_cli('verify', '--json', entry='cli.py').stdout)
        self.assertEqual(report['openspec_skills'], {'codex': 'PRESENT', 'claude': 'MISSING'})
        text = self.run_cli('verify', entry='cli.py').stdout
        self.assertIn('OpenSpec skills are not installed for claude', text)
        self.assertIn('ALL GOOD!', text)  # Information, not damage.


if __name__ == '__main__':
    unittest.main()
