"""Records shared by the ticket-flow collectors and pure calculations."""
from dataclasses import dataclass, field
from datetime import datetime

TOKENS = ('new_input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens')
ACTORS = ('claude_main', 'claude_subagents', 'codex')
PILOT = ('IGR-15', 'IGR-16')


@dataclass
class Marker:
    ticket: str
    time: datetime
    kind: str
    source: str
    repo: str | None = None
    identity: str | None = None
    group: str | None = None


@dataclass
class Turn:
    provider: str
    session: str
    identity: str
    ticket: str | None
    repo: str | None
    start: datetime | None
    end: datetime | None
    start_basis: str
    source: str
    minutes: float | None = None
    interval_start: datetime | None = None
    parent: str | None = None
    calls: list = field(default_factory=list)
    stage: str = 'unknown'
    order: str = 'timestamp'
    marker: Marker | None = None
    review_pass: int | None = None
    cycle: int | None = None
    overlap: float = 0.0
    wait: float | None = None
    child_type: str | None = None
    child_description: str | None = None
    child_family: str | None = None
    child_basis: str | None = None
    ticket_basis: str | None = None

    @property
    def actor(self):
        return 'codex' if self.provider == 'codex' else (
            'claude_subagents' if self.parent else 'claude_main')

    @property
    def key(self):
        return self.provider, self.session, self.identity
