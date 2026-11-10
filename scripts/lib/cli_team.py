"""Preview native team effects for the canonical Create team workflow; never create chats."""
from __future__ import annotations

from cli_files import Conflict
from cli_model import catalogue

WORKFLOW = 'asdg/skills/asdg-create-team/SKILL.md'


def team_plan(root, repo, clients, inventory=None):
    """Bind a verified native inventory to init; absence is unknown, never empty."""
    agents, _ = catalogue(repo)
    roles = [a['role_id'] for a in agents]
    result = {'workflow': WORKFLOW, 'roles': roles, 'admin_included': False,
              'default_role': roles[0], 'clients': {}, 'ready': False}
    if inventory is not None and 'codex' not in clients:
        raise Conflict('Native team inventory is only supported for the Codex integration.')
    for client in clients:
        if client == 'claude':
            result['clients'][client] = {'mode': 'role-adapters', 'status': 'PREPARED_BY_FILE_INSTALL',
                'native_chats': 'UNSUPPORTED', 'actions': []}
            continue
        status, actions = 'NATIVE_INVENTORY_REQUIRED', []
        project_id = None
        if inventory is not None:
            if (not isinstance(inventory, dict) or inventory.get('project_root') != str(root)
                    or not isinstance(inventory.get('project_id'), str) or not inventory['project_id']
                    or inventory.get('inventory_complete') is not True
                    or not isinstance(inventory.get('roles'), list)):
                raise Conflict('Incomplete or mismatched native team inventory; no chats may be created.')
            project_id = inventory['project_id']
            found, ids = {}, set()
            for row in inventory['roles']:
                if (not isinstance(row, dict) or row.get('role_id') not in roles
                        or row['role_id'] in found or row.get('activation') != 'confirmed'
                        or row.get('project_root') != str(root) or row.get('subject') != 'NoFocus'
                        or row.get('attitude') != 'NoAttitude' or not isinstance(row.get('thread_id'), str)
                        or not row['thread_id'] or row['thread_id'] in ids):
                    raise Conflict('Ambiguous or inconsistent native team role receipt; preserve chats and reconcile explicitly.')
                found[row['role_id']] = row
                ids.add(row['thread_id'])
            actions = [{'role_id': role, 'action': 'reuse' if role in found else 'create',
                        'thread_id': found[role]['thread_id'] if role in found else None}
                       for role in roles]
            status = 'ALREADY_SATISFIED' if len(found) == len(roles) else 'PLANNED'
        result['clients'][client] = {'mode': 'native-project-chats', 'status': status,
                                    'project_id': project_id, 'actions': actions}
    return result
