"""Structure of the Sprint align skill: pages, cross-references, scenarios and client adapters."""
import os
from pathlib import Path
import re
import sys
import unittest

CORE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(CORE / 'scripts/lib'))
from cli_clients import claude_adapter, explicit_only, skill_names
from distribution_files import package_files

SKILL = CORE / 'skills/asdg-sprint-align'
PAGES = ('SKILL.md', 'routing.md', 'reviews.md', 'readiness.md', 'report.md', 'TRY-IT.md')
os.environ.setdefault('ASDG_OPENSPEC', '0')  # Hermetic, like the other test modules.


def links(text):
    return [link.split('#')[0] for link in re.findall(r'\]\(([^)]+)\)', text)]


class SprintAlignSkillTests(unittest.TestCase):
    def test_every_page_is_packaged_and_reachable_from_the_entry_page(self):
        packaged = {path.relative_to(CORE).as_posix() for path in package_files(CORE)}
        entry = links((SKILL / 'SKILL.md').read_text())
        for name in PAGES:
            self.assertIn(f'skills/asdg-sprint-align/{name}', packaged, name)
            if name != 'SKILL.md':
                self.assertIn(name, entry, name)

    def test_the_entry_page_states_the_rule_owner_results_and_limits(self):
        text = (SKILL / 'SKILL.md').read_text()
        for heading in ('## The rule', '## Where it runs', '## Workflow', '## Limits'):
            self.assertIn(heading, text)
        for result in ('READY_FOR_09', 'NOT_READY', 'NEEDS_DECISION'):
            self.assertIn(result, text)
        self.assertIn('stages 02, 03, 04 and 05 assess the same baseline independently', text)
        self.assertIn('Never start, stop, restart or edit a sprint', text)

    def test_reviews_define_four_verdicts_and_six_relationships(self):
        text = (SKILL / 'reviews.md').read_text()
        for verdict in ('ALIGNED', 'CHANGE_REQUIRED', 'NEEDS_DECISION', 'MISSING_EVIDENCE', 'FOUNDATION_ALIGNED'):
            self.assertIn(verdict, text)
        self.assertEqual(len(re.findall(r'^\| (?:Purpose|Use Cases|Evaluation) → ', text, re.MULTILINE)), 6)

    def test_routing_forwards_from_a_specialist_and_excludes_admin(self):
        text = (SKILL / 'routing.md').read_text()
        self.assertIn('A specialist never runs the team-wide workflow', text)
        self.assertIn('Never invent an address', text)
        self.assertIn('A chat under ASDG Admin does not run an alignment', text)

    def test_the_scenarios_cover_the_twelve_cases_and_routing(self):
        text = (SKILL / 'TRY-IT.md').read_text()
        self.assertEqual(re.findall(r'^\| (A\d+) ', text, re.MULTILINE), [f'A{n}' for n in range(1, 13)])
        self.assertEqual(re.findall(r'^\| (R\d+) ', text, re.MULTILINE), ['R1', 'R2', 'R3', 'R4'])

    def test_sprint_start_stage_09_planning_gate_help_and_index_point_to_the_skill(self):
        for relative in ('skills/asdg-sprint-start/SKILL.md', '09-build-and-test-cycle/skills/review-build-task/SKILL.md',
                         '07-planning/skills/prepare-plan/SKILL.md', '00-governance/docs/sprint-gate.md',
                         'skills/asdg-help/SKILL.md', 'skills/README.md', 'docs/usage.md'):
            page = CORE / relative
            targets = {(page.parent / link).resolve() for link in links(page.read_text()) if link and '://' not in link}
            self.assertIn((SKILL / 'SKILL.md').resolve(), targets, relative)

    def test_both_clients_get_an_adapter_that_the_model_may_invoke(self):
        self.assertIn('asdg-sprint-align', skill_names(CORE.parent))
        self.assertFalse(explicit_only(CORE.parent, 'asdg-sprint-align'))
        adapter = claude_adapter(CORE.parent, 'asdg-sprint-align').decode()
        self.assertTrue(adapter.startswith('---\nname: asdg-sprint-align\ndescription: '))
        self.assertNotIn('disable-model-invocation', adapter)
        self.assertIn('asdg/skills/asdg-sprint-align/SKILL.md', adapter)
        self.assertIn('forward the request to the verified parent coordinator', adapter)


if __name__ == '__main__':
    unittest.main()
