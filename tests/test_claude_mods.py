"""Claude mods are installed by setup, and setup still runs after local methodology edits."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE / 'scripts/lib'))
from cli_clients import MOD_FILES, claude_files, mod_names
from cli_files import Conflict
from distribution_files import package_files

MOD = 'asdg-sprint-status'
import os
os.environ.setdefault('ASDG_OPENSPEC', '0')  # Hermetic: setup's OpenSpec step would run a separately installed command.


class ClaudeModTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-mods-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        self.root = self.client('client project')

    def client(self, name):
        root = self.area / name
        for source in package_files(CORE):
            target = root / 'asdg' / source.relative_to(CORE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        core, manifest = root / 'asdg', root / 'asdg/metadata/MANIFEST.json'
        value = json.loads(manifest.read_text())
        value['files'] = {p.relative_to(core).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in package_files(core) if p != manifest}
        manifest.write_text(json.dumps(value) + '\n')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        return root

    def run_cli(self, *args, entry='cli.py', expect=0):
        result = subprocess.run([sys.executable, '-B', str(self.root / 'asdg/scripts' / entry), *args],
                                cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result

    def preview(self, *args):
        return json.loads(self.run_cli(*args, '--dry-run', '--json', entry='init.py').stdout)

    def init(self, *args):
        report = self.preview(*args)
        self.run_cli(*args, '--apply', '--plan', report['plan'], entry='init.py')
        return report

    def claude_status(self, expect=0):
        return json.loads(self.run_cli('verify', '--json', expect=expect).stdout)['integrations']['claude']

    def test_the_packaged_mod_is_complete_and_named_after_its_folder(self):
        self.assertEqual(mod_names(self.root), [MOD])
        installed = {path.as_posix() for path, _ in claude_files(self.root)}
        self.assertTrue({f'.claude/skills/{MOD}/{name}' for name in MOD_FILES} <= installed)
        manifest = self.root / 'asdg/mods' / MOD / '.claude-plugin/plugin.json'
        manifest.write_text(json.dumps({'name': 'another-name'}))
        with self.assertRaises(Conflict):
            claude_files(self.root)
        manifest.unlink()
        self.assertEqual(mod_names(self.root), [])  # Without a manifest the folder is not a mod.

    def test_claude_setup_installs_only_the_runtime_files_unchanged(self):
        self.init('--client', 'claude')
        installed = self.root / '.claude/skills' / MOD
        for name in MOD_FILES:
            self.assertEqual((installed / name).read_bytes(), (self.root / 'asdg/mods' / MOD / name).read_bytes(), name)
        self.assertEqual(sorted(p.relative_to(installed).as_posix() for p in installed.rglob('*') if p.is_file()),
                         sorted(MOD_FILES))  # Companions and tests stay in the distribution.
        self.assertEqual(self.claude_status()['status'], 'COMPLETE')

    def test_codex_only_setup_installs_no_mod(self):
        self.init('--client', 'codex')
        self.assertFalse((self.root / '.claude').exists())

    def test_an_edited_installed_mod_is_reported_and_never_overwritten(self):
        self.init('--client', 'claude')
        module = self.root / '.claude/skills' / MOD / 'hooks/register.tsx'
        module.write_text(module.read_text() + '// local edit\n')
        edited = module.read_bytes()
        status = self.claude_status(expect=1)
        self.assertEqual(status['status'], 'DAMAGED')
        self.assertTrue(any('register.tsx' in problem for problem in status['problems']))
        result = self.run_cli('--client', 'claude', '--dry-run', entry='init.py', expect=1)
        self.assertIn('Refusing to overwrite existing file', result.stdout + result.stderr)
        self.assertEqual(module.read_bytes(), edited)

    def test_an_initialized_client_refreshes_integrations_after_local_methodology_edits(self):
        self.init('--client', 'codex')
        manifest = (self.root / 'asdg/metadata/MANIFEST.json').read_bytes()
        readme = self.root / 'asdg/README.md'
        readme.write_text(readme.read_text() + '\nLocal methodology edit.\n')
        report = self.preview('--client', 'claude')
        self.assertEqual(report['source']['integrity'], 'LOCAL_CHANGES')
        self.assertIsNone(report['source']['build'])
        self.assertTrue(any('Local methodology changes' in note for note in report['notes']))
        self.assertFalse((self.root / '.claude').exists())  # The preview wrote nothing.
        text = self.run_cli('--client', 'claude', '--dry-run', entry='init.py').stdout
        self.assertIn('LOCAL CHANGES', text)
        self.assertNotIn('Package integrity matched', text)
        self.run_cli('--client', 'claude', '--apply', '--plan', report['plan'], entry='init.py')
        self.assertTrue((self.root / '.claude/skills' / MOD / 'hooks/register.tsx').is_file())
        self.assertEqual((self.root / 'asdg/metadata/MANIFEST.json').read_bytes(), manifest)  # Provenance kept.
        self.assertFalse((self.root / 'asdg/metadata/build.json').exists())
        self.assertEqual(self.claude_status()['status'], 'COMPLETE')

    def test_a_first_install_with_a_stale_manifest_is_still_refused(self):
        self.root = self.client('never initialized')
        readme = self.root / 'asdg/README.md'
        readme.write_text(readme.read_text() + '\nChanged before any install.\n')
        result = self.run_cli('--client', 'claude', '--dry-run', entry='init.py', expect=1)
        self.assertIn('Package integrity failed', result.stdout + result.stderr)
        self.assertFalse((self.root / '.asdg').exists())
        self.assertFalse((self.root / '.claude').exists())


if __name__ == '__main__':
    unittest.main()
