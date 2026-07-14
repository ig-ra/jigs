import { Stats, Store } from "./store";

export async function compact(store: Store, key: string): Promise<number> {
  const data = await store.getObject(key);
  if (data === null) {
    throw new Error("missing object");
  }
  store.putObject(key, data);
  return store.stats().objects;
}

export function planCompaction(store: Store): string[] {
  return [store.cfg.region];
}

function estimate(store: Store): number {
  return store.cfg.maxSize;
}

export function mergeRanges(
  store: Store,
  lo: number,
  hi: number,
): number {
  if (lo > hi) {
    throw new Error("bad range");
  }
  return estimate(store) + hi - lo;
}

export function report(store: Store): Stats {
  return store.stats();
}
