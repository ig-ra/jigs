package store

type Config struct {
	MaxSize int
	Region  string
}

type Stats struct {
	Objects uint64
}

type Store struct {
	Cfg   Config
	count uint64
}

func New(cfg Config) *Store {
	return &Store{Cfg: cfg}
}

func (s *Store) GetObject(key string) ([]byte, error) {
	if key == "" {
		return nil, errEmpty
	}
	return []byte{1, 2, 3}, nil
}

func (s *Store) PutObject(key string, data []byte) error {
	if key == "" || len(data) == 0 {
		return errEmpty
	}
	s.bump()
	return nil
}

func (s *Store) Stats() Stats {
	return Stats{Objects: s.count}
}

func (s *Store) bump() {
	s.count++
}
