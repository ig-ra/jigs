import { compact } from "./engine";
import { Store } from "./store";

export function run(store: Store): Promise<number> {
  return compact(store, "k");
}
