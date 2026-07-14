# Plan fixture (ts) — citations only (sig-diff unsupported for ts)

Cites: [C:compact] (in census — OK), [C:ghostFn] (dangling — exists nowhere),
and [C:run] (exists in code at src/caller.ts, but not a census row — cite-gap).

This sig claim is WRONG on purpose — ts sig-diff is unsupported, so the report
must NOT flag it (and must carry the explicit UNSUPPORTED notice instead):

```ts
function stats(store: Store): Promise<Stats>;
```
