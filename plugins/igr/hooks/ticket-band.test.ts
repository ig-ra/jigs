// Run: bun test ./plugins/igr/hooks/ticket-band.test.ts
// Execute the hook with a synthetic Claude runtime; no app or private data needed.
import { expect, test } from 'bun:test'

const source = await Bun.file(new URL('./ticket-band.tsx', import.meta.url)).text()
const compiled = new Bun.Transpiler({ loader: 'tsx' }).transformSync(source)
  .replace(/^import .* from ["']claude-code["'];?$/m, '')
  .replace('export const register', 'const register')

async function session(cwd: string, files: Map<string, string>, tmp = '/tmp/') {
  let value: string | null = null
  let refresh: () => Promise<void>
  const reads: string[] = []
  const handlers: Record<string, Function> = {}
  const register = new Function('atom', 'read', 'update', `${compiled}\nreturn register;`)(
    () => null,
    async () => value,
    async (_$: unknown, _raw: unknown, update: () => string | null) => { value = update() },
  )
  register((event: string, ...args: unknown[]) => { handlers[event] = args.at(-1) as Function })
  await handlers['session.start']({
    session: { cwd: async () => cwd },
    env: { get: async () => tmp },
    fs: { read: async (path: string) => {
      reads.push(path)
      if (!files.has(path)) throw new Error('missing fixture file')
      return files.get(path)
    } },
    clock: { every: (_interval: number, callback: () => Promise<void>) => { refresh = callback } },
  }, {}, () => {})
  return { value: () => value, reads, refresh: () => refresh() }
}

const tree = '/repo/.worktrees/owner/team-7'
const local = `${tree}/igr/state.json`
const legacy = '/tmp/igr-ticket/team-7/state.json'

test('worktree state wins, including from a child directory', async () => {
  const result = await session(`${tree}/src`, new Map([[local, 'new'], [legacy, 'old']]))
  expect(result.value()).toBe('new')
  expect(result.reads).toEqual([local])
})

test('legacy temp state remains visible until the worktree state appears', async () => {
  const files = new Map([[legacy, 'old']])
  const result = await session(tree, files)
  expect(result.value()).toBe('old')
  files.set(local, 'new')
  await result.refresh()
  expect(result.value()).toBe('new')
  expect(result.reads).toEqual([local, legacy, local])
})

test('missing state clears the band, with the empty-TMPDIR fallback', async () => {
  const result = await session(tree, new Map([[local, 'new']]), '')
  expect(result.value()).toBe('new')
  const empty = await session(tree, new Map(), '')
  expect(empty.value()).toBeNull()
  expect(empty.reads).toEqual([local, legacy])
})

test('canonical sessions do not read ticket state', async () => {
  const result = await session('/repo', new Map([['/repo/igr/state.json', 'unrelated']]))
  expect(result.value()).toBeNull()
  expect(result.reads).toEqual([])
})
