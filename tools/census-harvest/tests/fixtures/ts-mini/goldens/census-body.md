## Appendix: Code Census

*SCIP-harvested skeleton (0.4.0) + model judgment. 4 in-scope rows. Anchors re-resolve at implement HEAD.*

| symbol | kind | anchor | signature | vis | in | out | boundary | behavior (judgment) | disposition |
|---|---|---|---|---|---|---|---|---|---|
| `compact` | Function | src/engine.ts:3 | `function compact(store: Store, key: string): Promise<number>` | public | 4 | 14 | Store#getObject, Store#putObject, Store#stats | throws on missing object; bump side-effect via putObject | moves |
| `planCompaction` | Function | src/engine.ts:12 | `function planCompaction(store: Store): string[]` | public | 0 | 4 | Store#cfg |  | stays |
| `mergeRanges` | Function | src/engine.ts:20 | `function mergeRanges(store: Store, lo: number, hi: number): number` | public | 0 | 7 |  | throws on lo>hi before any work |  |
| `report` | Function | src/engine.ts:31 | `function report(store: Store): Stats` | public | 0 | 4 | Store#stats |  | seam |

## Reconciliation (deterministic coverage floor)

- boundary coupling: **6 member-accesses / 4 members** (prod; 8 bare type-mentions excluded).
- symbols harvested: 9 (6 prod / 3 test); in-scope: 4.
- SCIP<->grep grep-only flags: 0 (review in the skeleton).

| boundary member | accesses |
|---|---|
| `Store#stats` | 2 |
| `Store#cfg` | 2 |
| `Store#getObject` | 1 |
| `Store#putObject` | 1 |
