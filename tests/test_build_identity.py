"""Commit-based build identity across ZIP builds, ZIP and clone installs, and client status."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

CORE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE / 'scripts'))
sys.path.insert(0, str(CORE / 'scripts/lib'))
from build_distribution import build, refresh_manifest
from build_identity import BUILD, label
from cli_install import install
from cli_sync import synchronize
from distribution_files import package_files

STAMP = '2026-11-09T12:34:56+00:00'
CANONICAL = 'https://github.com/Elustondo-ai/asdg.git'


def git(root, *args, date=STAMP):
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
               GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='asdg-build-id-')
        self.addCleanup(area.cleanup)
        self.root = Path(area.name).resolve()
        self.source = self.root / 'canonical'
        self.source.mkdir()
        git(self.source, 'init', '-q')
        git(self.source, 'remote', 'add', 'origin', CANONICAL)
        for p in package_files(CORE):
            target = self.source / p.relative_to(CORE)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
        self.head = self.save()

    def save(self, date=STAMP):
        refresh_manifest(self.source)
        git(self.source, 'add', '-A')
        git(self.source, 'commit', '-qm', 'Disposable canonical build', '--allow-empty', date=date)
        return git(self.source, 'rev-parse', 'HEAD')

    def touch_readme(self, text):
        path = self.source / 'README.md'
        self.assertIn('README.md', [p.name for p in package_files(self.source) if p.parent == self.source])
        path.write_text(path.read_text() + text)

    def zip_record(self, archive):
        with zipfile.ZipFile(archive) as stream:
            if 'asdg/' + BUILD not in stream.namelist():
                return None
            return json.loads(stream.read('asdg/' + BUILD))

    def client(self, name):
        root = self.root / name
        root.mkdir()
        git(root, 'init', '-q')
        (root / 'app.py').write_text('print("client application")\n')
        (root / 'AGENTS.md').write_text('# Client project\n\nKeep this guidance.\n')
        return root

    def cli(self, client, *args):
        return subprocess.run([sys.executable, '-B', str(client / 'asdg/scripts/cli.py'), *args],
                              cwd=client, capture_output=True, text=True, timeout=90)

    def status_build(self, client):
        result = self.cli(client, 'status', '--json')
        return json.loads(result.stdout)['build']

    def clone_install(self, client):
        options = dict(source=str(self.source), commit=self.head, target=str(client), client='both',
                       repo=self.source)
        preview = install(**options)
        return install(**options, apply_changes=True, expected_plan=preview['plan'])

    def zip_install(self, client, archive):
        with zipfile.ZipFile(archive) as stream:
            stream.extractall(client)
        preview = json.loads(self.cli(client, 'init', '--client', 'both', '--dry-run', '--json').stdout)
        result = self.cli(client, 'init', '--client', 'both', '--apply', '--plan', preview['plan'], '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_same_commit_twice_gives_identical_zip_and_identifier(self):
        first = build(self.source, self.root / 'today')
        second = build(self.source, self.root / 'tomorrow')
        explicit = build(self.source, self.root / 'explicit', commit=self.head)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(first.read_bytes(), explicit.read_bytes())
        # The real entry point, later and in another timezone, reproduces the same artifact.
        result = subprocess.run([sys.executable, '-B', str(self.source / 'scripts/build_distribution.py'),
                                 '--output', str(self.root / 'elsewhere')], capture_output=True, text=True,
                                env=dict(os.environ, TZ='Pacific/Kiritimati'), timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'elsewhere' / first.name).read_bytes(), first.read_bytes())
        self.assertIn('ASDG build 2026-11-09T12:34:56Z · ' + self.head[:7], result.stdout)
        record = self.zip_record(first)
        self.assertEqual(record['commit'], self.head)
        self.assertEqual(record['committed_at'], '2026-11-09T12:34:56Z')  # Commit time, not build time.
        self.assertEqual(first.name, f"asdg-{record['release']}-20261109T123456Z-{self.head[:7]}.zip")
        self.assertEqual(label(record), 'ASDG build 2026-11-09T12:34:56Z · ' + self.head[:7])

    def test_two_commits_with_the_same_timestamp_are_distinguished(self):
        first = self.zip_record(build(self.source, self.root / 'first'))
        self.touch_readme('\nSecond build, same committer second.\n')
        second_head = self.save()
        second = self.zip_record(build(self.source, self.root / 'second'))
        self.assertEqual(first['committed_at'], second['committed_at'])
        self.assertNotEqual(first['commit_short'], second['commit_short'])
        self.assertNotEqual(first['build_id'], second['build_id'])
        self.assertEqual(second['commit'], second_head)

    def test_bytes_that_differ_from_the_commit_are_never_attributed(self):
        self.touch_readme('\nUncommitted edit.\n')
        refresh_manifest(self.source)
        archive = build(self.source, self.root / 'dirty')
        self.assertIsNone(self.zip_record(archive))
        self.assertNotIn(self.head[:7], archive.name)
        with self.assertRaises(ValueError):
            build(self.source, self.root / 'refused', commit=self.head)

    def test_clone_install_keeps_its_build_after_client_only_commits(self):
        client = self.client('clone client')
        self.clone_install(client)
        record = json.loads((client / 'asdg' / BUILD).read_text())
        self.assertEqual(record['commit'], self.head)
        binding = json.loads((client / '.asdg/project.json').read_text())
        self.assertEqual(binding['installation_source']['build'], record)
        before = self.status_build(client)
        self.assertEqual((before['state'], before['display']), ('RECORDED', label(record)))
        git(client, 'add', '-A')
        git(client, 'commit', '-qm', 'Install ASDG', date='2026-12-01T00:00:00+00:00')
        (client / 'app.py').write_text('print("client-only change")\n')
        git(client, 'commit', '-qam', 'Client-only change', date='2026-12-02T00:00:00+00:00')
        self.assertEqual(self.status_build(client), before)
        self.assertIn(label(record), self.cli(client, 'status').stdout)
        (client / 'asdg/README.md').write_text('Local methodology edit\n')
        self.assertEqual(self.status_build(client)['state'], 'LOCAL_CHANGES')

    def test_zip_install_records_build_and_rejects_a_foreign_record(self):
        archive = build(self.source, self.root / 'zip')
        record = self.zip_record(archive)
        client = self.client('zip client')
        self.zip_install(client, archive)
        source = json.loads((client / '.asdg/project.json').read_text())['installation_source']
        self.assertEqual((source['kind'], source['build']), ('EXTRACTED_PACKAGE', record))
        self.assertEqual(self.status_build(client)['display'], label(record))
        foreign = self.client('foreign client')
        with zipfile.ZipFile(archive) as stream:
            stream.extractall(foreign)
        (foreign / 'asdg' / BUILD).write_text(json.dumps(dict(record, snapshot_sha256='0' * 64)))
        result = self.cli(foreign, 'init', '--client', 'both', '--dry-run', '--json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('build record does not match', result.stdout + result.stderr)
        self.assertFalse((foreign / '.asdg').exists())

    def test_installations_without_a_record_keep_reporting_their_release(self):
        plain = self.root / 'unversioned copy'
        shutil.copytree(self.source, plain, ignore=shutil.ignore_patterns('.git'))
        archive = build(plain, self.root / 'legacy')
        self.assertIsNone(self.zip_record(archive))
        legacy_zip = self.client('legacy zip client')
        self.zip_install(legacy_zip, archive)
        legacy = self.status_build(legacy_zip)
        self.assertEqual(legacy['state'], 'NOT_RECORDED')
        self.assertEqual(legacy['display'], f"ASDG {legacy['release']} (build not recorded)")
        legacy_clone = self.client('legacy clone client')
        self.clone_install(legacy_clone)
        (legacy_clone / 'asdg' / BUILD).unlink()  # As in an existing 0.3.0-pilot.4 clone installation.
        self.assertEqual(self.status_build(legacy_clone)['display'],
                         f"ASDG {legacy['release']} · {self.head[:7]} (build time not recorded)")


    def test_update_after_a_fresh_install_uses_the_installed_commit_as_baseline(self):
        for legacy in (False, True):
            with self.subTest(legacy_without_record=legacy):
                client = self.client('updated client' + (' legacy' if legacy else ''))
                git(client, 'remote', 'add', 'origin', 'https://github.com/Elustondo-ai/client-fixture.git')
                self.clone_install(client)
                if legacy:  # Like Alice's existing install: only the binding names the commit.
                    (client / 'asdg' / BUILD).unlink()
                git(client, 'add', '-A')
                git(client, 'commit', '-qm', 'Install ASDG')
                installed = self.head
                self.touch_readme('\nCanonical change after install.\n')
                self.head = self.save(date='2026-11-10T08:00:00+00:00')
                preview = synchronize('upgrade', self.source, client)
                self.assertEqual(preview['baseline'], 'installed commit ' + installed[:7])
                self.assertEqual(preview['counts']['conflicting'], 0)
                self.assertEqual({r['path'] for r in preview['files'] if r['status'] == 'modified'},
                                 {'asdg/README.md', 'asdg/metadata/MANIFEST.json'})
                synchronize('upgrade', self.source, client, apply=True, expected_plan=preview['plan_id'])
                after = self.status_build(client)
                self.assertEqual((after['state'], after['commit']), ('RECORDED', self.head))
                self.assertEqual(after['committed_at'], '2026-11-10T08:00:00Z')
                self.head = installed  # The next subtest installs the original commit again.
                git(self.source, 'reset', '-q', '--hard', installed)


if __name__ == '__main__':
    unittest.main()
