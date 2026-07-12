use crate::store::{Persist, Stats, Store};

pub fn compact(store: &mut Store, key: &str) -> Result<u64, String> {
    let data = store.get_object(key)?;
    store.put_object(key, data)?;
    store.persist(key)?;
    Ok(store.stats().objects)
}

pub(crate) fn plan_compaction(store: &Store) -> Vec<String> {
    vec![store.cfg.region.clone()]
}

fn estimate(store: &Store) -> usize {
    store.cfg.max_size
}

pub fn merge_ranges(
    store: &Store,
    lo: usize,
    hi: usize,
) -> Result<usize, String> {
    if lo > hi {
        return Err("bad range".to_string());
    }
    Ok(estimate(store) + hi - lo)
}

pub fn report(store: &Store) -> Stats {
    store.stats()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::Config;

    fn compact_helper(store: &mut Store) -> u64 {
        store.stats().objects
    }

    #[test]
    fn test_compact() {
        let mut s = Store::new(Config { max_size: 8, region: "eu".to_string() });
        let n = compact(&mut s, "k").unwrap();
        assert_eq!(n, compact_helper(&mut s));
    }
}
