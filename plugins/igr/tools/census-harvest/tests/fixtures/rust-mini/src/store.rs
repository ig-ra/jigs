pub struct Config {
    pub max_size: usize,
    pub region: String,
}

pub struct Stats {
    pub objects: u64,
}

pub struct Store {
    pub cfg: Config,
    count: u64,
}

pub trait Persist {
    fn persist(&self, key: &str) -> Result<(), String>;
}

impl Store {
    pub fn new(cfg: Config) -> Store {
        Store { cfg, count: 0 }
    }

    pub fn get_object(&self, key: &str) -> Result<Vec<u8>, String> {
        if key.is_empty() {
            return Err("empty key".to_string());
        }
        Ok(vec![1, 2, 3])
    }

    pub fn put_object(&mut self, key: &str, data: Vec<u8>) -> Result<(), String> {
        if key.is_empty() || data.is_empty() {
            return Err("bad input".to_string());
        }
        self.bump();
        Ok(())
    }

    pub fn stats(&self) -> Stats {
        Stats { objects: self.count }
    }

    fn bump(&mut self) {
        self.count += 1;
    }
}

impl Persist for Store {
    fn persist(&self, key: &str) -> Result<(), String> {
        if key.is_empty() {
            return Err("empty key".to_string());
        }
        Ok(())
    }
}
