/** The next sprint while 07 Planning proposes it; never the sprint record itself. */
export type NextSprint = {
  id: string
  /** Free text from the file, such as `proposed` or `awaiting approval`. */
  state: string
  objective: string | null
  /** Path of the plan page. */
  plan: string | null
  /** One line on the sprint before it, such as `SPRINT-003 closed (unfinished)`. */
  previous: string | null
}

export type Sprint = {
  /** False when the project has no `.asdg/sprint.json`: the band stays empty. */
  isAsdgProject: boolean
  status: string
  id: string | null
  objective: string | null
  scope: string[]
  acceptance: string[]
  branch: string | null
  /** Shown only when no sprint is active; null when the file is absent. */
  next: NextSprint | null
}

declare module 'claude-code' {
  interface PluginState {
    'asdg-sprint-status': { sprint: Shaped<Sprint | null> }
  }
}
