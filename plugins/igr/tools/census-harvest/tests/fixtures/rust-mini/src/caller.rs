use crate::engine;
use crate::store::Store;

pub fn run(store: &mut Store) -> Result<u64, String> {
    engine::compact(store, "k")
}
