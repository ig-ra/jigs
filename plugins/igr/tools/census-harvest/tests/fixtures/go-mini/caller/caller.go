package caller

import (
	"example.com/gomini/engine"
	"example.com/gomini/store"
)

func Run(s *store.Store) (uint64, error) {
	return engine.Compact(s, "k")
}
