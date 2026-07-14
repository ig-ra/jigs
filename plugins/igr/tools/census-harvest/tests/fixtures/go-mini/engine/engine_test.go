package engine

import (
	"testing"

	"example.com/gomini/store"
)

func compactHelper(s *store.Store) uint64 {
	return s.Stats().Objects
}

func TestCompact(t *testing.T) {
	s := store.New(store.Config{MaxSize: 8, Region: "eu"})
	n, err := Compact(s, "k")
	if err != nil {
		t.Fatal(err)
	}
	if n != compactHelper(s) {
		t.Fatalf("mismatch")
	}
}
