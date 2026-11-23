import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { NextSprint, Sprint } from '../types'

const PANE = 'sprint'
const TITLE = 'ASDG sprint'
const RECORD = '.asdg/sprint.json'
// Kept by 07 Planning: the next sprint while it is proposed and being approved.
const PROPOSED = 'docs/asdg/07-planning/proposed-sprint.json'
const REFRESH_MS = 20000

// Change the tag when Sprint's fields change: it declines what an earlier
// version stored, which outlives a reload.
const sprint = atom({ plugin: 'asdg-sprint-status', key: 'sprint' } as const, null, {
  shape: 'sprint-2',
})

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter(one => typeof one === 'string') : []

const text = (value: unknown): string | null => (typeof value === 'string' ? value : null)

// Read-only: the proposed next sprint, or null when the file is absent or
// unusable. It never changes or stands in for the sprint record.
const loadNext = async ($: EngineInterface): Promise<NextSprint | null> => {
  try {
    const file = JSON.parse(await $.fs.read(PROPOSED))
    const id = text(file.sprint_id)

    return id === null
      ? null
      : {
          id,
          state: text(file.state) ?? 'proposed',
          objective: text(file.objective),
          plan: text(file.plan),
          previous: text(file.previous),
        }
  } catch {
    return null
  }
}

// Read-only: the sprint record the ASDG CLI writes, and the checked-out branch.
const load = async ($: EngineInterface): Promise<Sprint> => {
  const none: Sprint = {
    isAsdgProject: false,
    status: 'inactive',
    id: null,
    objective: null,
    scope: [],
    acceptance: [],
    branch: null,
    next: null,
  }
  let branch: string | null = null

  try {
    const head = (await $.fs.read('.git/HEAD')).trim()
    branch = head.startsWith('ref: refs/heads/')
      ? head.slice('ref: refs/heads/'.length)
      : head.slice(0, 7)
  } catch {
    branch = null
  }

  try {
    const record = JSON.parse(await $.fs.read(RECORD))
    const status = typeof record.status === 'string' ? record.status : 'unknown'

    return {
      isAsdgProject: true,
      status,
      id: typeof record.sprint_id === 'string' ? record.sprint_id : null,
      objective: typeof record.objective === 'string' ? record.objective : null,
      scope: strings(record.scope),
      acceptance: strings(record.acceptance_criteria),
      branch,
      next: status === 'active' ? null : await loadNext($),
    }
  } catch {
    return { ...none, branch }
  }
}

const refresh = async ($: EngineInterface): Promise<void> => {
  // Never throws: a failed look leaves the last known status on screen and
  // must not cost a tool call its result.
  try {
    const now = await load($)
    const before = await read($, sprint)

    // Write only on a change, so a quiet poll redraws nothing.
    if (JSON.stringify(before) !== JSON.stringify(now)) {
      await update($, sprint, () => now)
    }
  } catch {
    return
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'asdg-sprint-pane',
      description: 'Show the ASDG sprint objective, scope and acceptance criteria in a pane',
    })
    await refresh($)
    $.clock.every(REFRESH_MS, () => void refresh($))

    return next(e)
  })

  // A sprint starts, closes or changes branch through a command, so look
  // again after each one and at the end of every turn.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    await refresh($)

    return ran
  })

  on('turn.complete', async ($, e, next) => {
    await refresh($)

    return next(e)
  })

  on('command.run', { command: 'asdg-sprint-pane' }, async $ => {
    await refresh($)
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'Sprint pane opened.' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const now = await read($, sprint)

    if (e.props.hasSurvey || now === null || !now.isAsdgProject) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    const isActive = now.status === 'active'
    const where = now.branch === null ? '' : ` · ${now.branch}`

    return (
      <Box gap={1}>
        {isActive ? (
          <Text bold>{now.id ?? 'Sprint'} active</Text>
        ) : (
          <Text dimColor>No active sprint</Text>
        )}
        <Text dimColor wrap="truncate-end">
          {where}
          {isActive && now.objective !== null ? ` · ${now.objective}` : ''}
          {!isActive && now.next !== null ? ` · next: ${now.next.id} ${now.next.state}` : ''}
        </Text>
        <Button
          key="details"
          label="Details"
          onPress={() => void $.ui.open({ id: PANE, title: TITLE })}
        />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const now = await read($, sprint)

    if (now === null || !now.isAsdgProject) {
      return (
        <Box>
          <Text dimColor>This project has no ASDG sprint record.</Text>
        </Box>
      )
    }

    if (e.props.placement === 'widget') {
      return (
        <Box flexDirection="column">
          <Text bold>{now.status === 'active' ? `${now.id} active` : 'No active sprint'}</Text>
          <Text dimColor>{now.branch ?? ''}</Text>
          {now.status !== 'active' && now.next !== null && (
            <Text dimColor>
              Next: {now.next.id} {now.next.state}
            </Text>
          )}
        </Box>
      )
    }

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="column">
          <Text bold>
            {now.status === 'active' ? `${now.id} · active` : 'No active sprint'}
          </Text>
          <Text dimColor>Branch: {now.branch ?? 'unknown'}</Text>
        </Box>
        {now.status !== 'active' && now.next !== null && (
          <Box flexDirection="column">
            <Text bold>
              Next sprint: {now.next.id} · {now.next.state}
            </Text>
            {now.next.previous !== null && <Text dimColor>{now.next.previous}</Text>}
            {now.next.objective !== null && <Text>{now.next.objective}</Text>}
            {now.next.plan !== null && <Text dimColor>Plan: {now.next.plan}</Text>}
          </Box>
        )}
        {now.objective !== null && (
          <Box flexDirection="column">
            <Text bold>Objective</Text>
            <Text>{now.objective}</Text>
          </Box>
        )}
        {now.scope.length > 0 && (
          <Box flexDirection="column">
            <Text bold>Scope</Text>
            {now.scope.map(path => (
              <Text>{path}</Text>
            ))}
          </Box>
        )}
        {now.acceptance.length > 0 && (
          <Box flexDirection="column">
            <Text bold>Acceptance criteria</Text>
            {now.acceptance.map((criterion, index) => (
              <Text>
                {index + 1}. {criterion}
              </Text>
            ))}
          </Box>
        )}
      </Box>
    )
  })
}
