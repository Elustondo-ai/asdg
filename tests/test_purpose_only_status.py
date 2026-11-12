"""A new project with only an accepted Purpose: acceptance stands alone, other views stay unknown."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
sys.path.insert(0, str(CORE / 'scripts/lib'))
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(CORE / 'skills/asdg-report-project-status'))
from continuation_fixture import create_fixture
from purpose_review import CRITERIA, PREFIX, PURPOSE_DOCUMENT
from report_packets import ordered_report

RETIRED = {'intended', 'current', 'planned', 'planned-release', 'planned-sprint'}


class PurposeOnlyProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = tempfile.TemporaryDirectory(prefix='asdg-purpose-only-')
        cls.root = create_fixture(Path(cls.area.name) / 'client', 'accepted')
        output = subprocess.run([sys.executable, '-B', 'asdg/scripts/cli.py', 'status', '--json'],
                                cwd=cls.root, check=True, capture_output=True, text=True).stdout
        cls.status = json.loads(output)
        cls.stages = {s['number']: s for s in cls.status['lifecycle_stages']}

    @classmethod
    def tearDownClass(cls):
        cls.area.cleanup()

    def test_purpose_is_accepted_on_its_own_criteria(self):
        purpose = self.stages[2]
        self.assertEqual(purpose['artifacts'], [str(PREFIX / PURPOSE_DOCUMENT)])
        self.assertEqual(purpose['completion']['status'], 'ACCEPTED')
        reviews = json.loads((self.root / '.asdg/lifecycle.json').read_text())['stages']['02']['reviews']
        self.assertEqual(set(reviews[0]['criteria']), set(CRITERIA))

    def test_no_implementation_or_planning_record_exists(self):
        for number in range(3, 13):
            with self.subTest(stage=number):
                self.assertEqual(self.stages[number]['artifacts'], [])
        self.assertEqual(self.stages[7]['readiness'], 'MISSING')
        planning = self.root / 'docs/asdg/07-planning'
        self.assertEqual(sorted(p.name for p in planning.iterdir()), ['README.md'])
        self.assertEqual(self.status['sprint_state']['status'], 'inactive')

    def test_initialization_creates_no_retired_perspective_structure(self):
        found = [p for p in (self.root / 'docs/asdg').rglob('*') if p.is_dir() and p.name in RETIRED]
        self.assertEqual(found, [])
        purpose = self.root / PREFIX
        self.assertEqual(sorted(p.name for p in purpose.iterdir()), ['01-purpose.md', 'README.md', 'images'])

    def test_report_section_derives_intended_and_leaves_other_views_unknown(self):
        purpose = str(PREFIX / PURPOSE_DOCUMENT)
        checked = ['asdg status --json', 'docs/asdg/', 'docs/asdg/07-planning/']
        run = {'run_id': 'purpose-only', 'project': 'client', 'snapshot': self.status['evaluated_at'],
               'client': 'claude', 'owner': 'ASDG-02'}
        slide = lambda kind, headline, point, sources: {
            'kind': kind, 'headline': headline, 'points': [point], 'sources': sources,
            'visual_brief': 'Show which records were checked and what they establish.',
            'notes': headline + ' ' + point}
        packet = dict(run, role_id='ASDG-02', loaded=['asdg/02-purpose/AGENTS.md',
                      'asdg/02-purpose/skills/elicit-purpose/SKILL.md'], slides=[
            slide('definition', 'Intended: the accepted Purpose', 'User accepted the reviewed definition.',
                  [purpose, '.asdg/lifecycle.json']),
            slide('status', 'Actual: unknown', 'No implementation, test or operating evidence exists.', checked),
            slide('plan', 'Planned: unknown', 'No Stage 07 planning record exists.', checked)])
        run['outcomes'] = {'ASDG-02': {'packet': packet}}
        catalogue = json.loads((CORE / '00-governance/types/agent-catalog.json').read_text())
        report = ordered_report(run, catalogue)
        self.assertEqual(report['status'], 'COMPLETE')
        self.assertEqual([s['kind'] for s in report['slides']], ['definition', 'status', 'plan'])


if __name__ == '__main__':
    unittest.main()
