"""Canonical team plan and init approval regressions; no native client is simulated as observed."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from cli_files import Conflict
from cli_model import catalogue
from cli_team import team_plan

ROOT = Path(__file__).resolve().parents[1]


class TeamPlanTests(unittest.TestCase):
    def inventory(self, count=0):
        roles = catalogue(ROOT)[0]
        return {'project_root': '/target', 'project_id': 'native-project', 'inventory_complete': True,
                'roles': [{'role_id': r['role_id'], 'thread_id': 'id-' + str(r['stage']),
                           'project_root': '/target', 'activation': 'confirmed',
                           'subject': 'NoFocus', 'attitude': 'NoAttitude'} for r in roles[:count]]}

    def plan(self, inventory=None, clients=('codex',)):
        return team_plan(Path('/target'), ROOT, clients, inventory)

    def test_fresh_team_has_governance_and_twelve_specialists_without_admin(self):
        plan = self.plan(self.inventory())
        actions = plan['clients']['codex']['actions']
        self.assertEqual(len(actions), 13)
        self.assertTrue(all(r['action'] == 'create' for r in actions))
        self.assertEqual(actions[0]['role_id'], 'ASDG-COORDINATOR')
        self.assertFalse(plan['admin_included'])
        self.assertEqual(plan['workflow'], 'asdg/skills/asdg-create-team/SKILL.md')

    def test_matching_team_is_already_satisfied_and_inventory_preserved(self):
        inventory = self.inventory(13)
        before = copy.deepcopy(inventory)
        plan = self.plan(inventory)['clients']['codex']
        self.assertEqual(plan['status'], 'ALREADY_SATISFIED')
        self.assertTrue(all(a['action'] == 'reuse' for a in plan['actions']))
        self.assertEqual([a['thread_id'] for a in plan['actions']], [r['thread_id'] for r in before['roles']])
        self.assertEqual(inventory, before)
        self.assertEqual(self.plan(inventory), self.plan(inventory))

    def test_confirmed_partial_inventory_only_plans_missing_roles(self):
        plan = self.plan(self.inventory(4))['clients']['codex']
        self.assertEqual([a['action'] for a in plan['actions']], ['reuse'] * 4 + ['create'] * 9)

    def test_unknown_inventory_never_means_missing_team(self):
        plan = self.plan()['clients']['codex']
        self.assertEqual(plan['status'], 'NATIVE_INVENTORY_REQUIRED')
        self.assertEqual(plan['actions'], [])

    def test_inconsistent_partial_state_is_rejected_without_mutation(self):
        mutations = [lambda v: v.update(inventory_complete=False),
                     lambda v: v.update(project_root='/foreign'),
                     lambda v: v['roles'].append(v['roles'][0].copy()),
                     lambda v: v['roles'][0].update(activation='pending'),
                     lambda v: v['roles'][0].update(subject='Security'),
                     lambda v: v['roles'][0].update(attitude='Black'),
                     lambda v: v['roles'][1].update(thread_id=v['roles'][0]['thread_id'])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                inventory = self.inventory(2)
                mutate(inventory)
                before = copy.deepcopy(inventory)
                with self.assertRaises(Conflict):
                    self.plan(inventory)
                self.assertEqual(inventory, before)

    def test_client_modes_do_not_invent_claude_chat_automation(self):
        plan = self.plan(clients=('claude',))
        self.assertEqual(plan['clients']['claude']['mode'], 'role-adapters')
        self.assertEqual(plan['clients']['claude']['native_chats'], 'UNSUPPORTED')
        self.assertEqual(self.plan(self.inventory(), ('codex', 'claude'))['default_role'], 'ASDG-COORDINATOR')

    def test_canonical_workflow_orders_approval_files_team_status(self):
        init = (ROOT / 'skills/asdg-init/SKILL.md').read_text()
        self.assertLess(init.index('STOP. Only a standalone APPROVE'), init.index('## Apply and verify'))
        self.assertLess(init.index('## Apply and verify'), init.index('## Complete the team'))
        integration = (ROOT / 'skills/asdg-create-team/initialization.md').read_text()
        for phrase in ['cannot roll back installed files', 'same APPROVE', 'before each creation', 'preserve successful chats']:
            # Contracts are checked separately from native behavior.
            self.assertIn(phrase, init + integration)
        self.assertIn('Follow [missing-chat creation](create-chats.md)', (ROOT / 'skills/asdg-create-team/SKILL.md').read_text())
        self.assertIn('Creation success is not focus activation', (ROOT / 'skills/asdg-create-team/create-chats.md').read_text())
