export interface Config {
  maxSize: number;
  region: string;
}

export interface Stats {
  objects: number;
}

export class Store {
  cfg: Config;
  private count: number;

  constructor(cfg: Config) {
    this.cfg = cfg;
    this.count = 0;
  }

  getObject(key: string): Promise<Uint8Array | null> {
    if (key === "") {
      return Promise.resolve(null);
    }
    return Promise.resolve(new Uint8Array([1, 2, 3]));
  }

  putObject(key: string, data: Uint8Array): boolean {
    if (key === "" || data.length === 0) {
      return false;
    }
    this.bump();
    return true;
  }

  stats(): Stats {
    return { objects: this.count };
  }

  protected bump(): void {
    this.count += 1;
  }
}
