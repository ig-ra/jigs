## Census skeleton (SCIP-harvested; mechanical only — judgment via `census merge`)

| symbol | kind | anchor | signature | vis | in | out | boundary members | test? |
|---|---|---|---|---|---|---|---|---|
| `` | Module | src/engine.test.ts:1 | `module "engine.test.ts"` | private | 0 | 0 |  | TEST |
| `compactHelper` | Function | src/engine.test.ts:4 | `function compactHelper(store: Store): number` | private | 1 | 4 | Store#stats | TEST |
| `testCompact` | Function | src/engine.test.ts:8 | `function testCompact(): Promise<void>` | public | 0 | 12 | Store#`<constructor>` | TEST |
| `` | Module | src/engine.ts:1 | `module "engine.ts"` | private | 2 | 0 |  |  |
| `compact` | Function | src/engine.ts:3 | `function compact(store: Store, key: string): Promise<number>` | public | 4 | 14 | Store#getObject, Store#putObject, Store#stats |  |
| `planCompaction` | Function | src/engine.ts:12 | `function planCompaction(store: Store): string[]` | public | 0 | 4 | Store#cfg |  |
| `estimate` | Function | src/engine.ts:16 | `function estimate(store: Store): number` | private | 1 | 4 | Store#cfg |  |
| `mergeRanges` | Function | src/engine.ts:20 | `function mergeRanges(store: Store, lo: number, hi: number): number` | public | 0 | 7 |  |  |
| `report` | Function | src/engine.ts:31 | `function report(store: Store): Stats` | public | 0 | 4 | Store#stats |  |

## Boundary coupling (coverage floor — member accesses only, prod)

| member | accesses |
|---|---|
| `Store#stats` | 2 |
| `Store#cfg` | 2 |
| `Store#getObject` | 1 |
| `Store#putObject` | 1 |

## SCIP<->grep reconciliation
| file | SCIP member-lines | grep hit-lines |
|---|---|---|
| src/engine.ts | 6 | 6 |

**grep-only lines (SCIP didn't resolve — review): 0**
