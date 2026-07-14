import { compact } from "./engine";
import { Store } from "./store";

function compactHelper(store: Store): number {
  return store.stats().objects;
}

export async function testCompact(): Promise<void> {
  const s = new Store({ maxSize: 8, region: "eu" });
  const n = await compact(s, "k");
  if (n !== compactHelper(s)) {
    throw new Error("mismatch");
  }
}
