package engine

import "example.com/gomini/store"

func Compact(s *store.Store, key string) (uint64, error) {
	data, err := s.GetObject(key)
	if err != nil {
		return 0, err
	}
	if err := s.PutObject(key, data); err != nil {
		return 0, err
	}
	return s.Stats().Objects, nil
}

func planCompaction(s *store.Store) []string {
	return []string{s.Cfg.Region}
}

func estimate(s *store.Store) int {
	return s.Cfg.MaxSize
}

func MergeRanges(
	s *store.Store,
	lo int,
	hi int,
) (int, error) {
	if lo > hi {
		return 0, errBadRange
	}
	return estimate(s) + hi - lo, nil
}

func Report(s *store.Store) store.Stats {
	return s.Stats()
}
