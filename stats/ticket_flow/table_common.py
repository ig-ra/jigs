"""Shared schemas and missingness rules for the four output tables."""
from math import fsum

from .model import ACTORS, TOKENS

AUDIT_FIELDS = ('provider', 'id', 'timestamp', 'ticket', 'ticket_basis', 'repo', 'actor', 'session',
    'parent_session', 'turn', 'turn_start', 'start_basis', 'source', 'marker_time', 'marker_source',
    'marker_repo', 'stage', 'stage_order', 'review_pass', 'cycle', 'activity', 'activity_basis',
    'activity_source', 'child_type', 'child_description', 'child_family', 'child_basis', *TOKENS, 'missing_reason')
MEASURES = tuple(f'{actor}_{token}' for actor in ACTORS for token in TOKENS) + (
    'claude_main_minutes_raw', 'codex_minutes_raw', 'foreground_wait_min', 'turn_overlap_min',
    'simplify_passes', 'native_review_passes', 'own_review_passes', 'fix_rounds', 'fix_cycles', 'calls', 'turns')
ESTIMATES = ('dispatches', 'estimated_rounds_low', 'estimated_rounds_high',
    'estimated_minutes_low', 'estimated_minutes_high', 'completed_dispatch_minutes')
PR_SUMS = ('pr_files', 'pr_additions', 'pr_deletions', 'pr_commits', 'initial_commits', 'fix_commits',
    'initial_additions', 'initial_deletions', 'fix_additions', 'fix_deletions',
    'bot_reviews', 'bot_comments', 'bot_threads')
PR_FIELDS = ('prs', *PR_SUMS, 'churn_ratio', 'fix_split_status', 'review_after_bot')
STAGE_FIELDS = ('ticket', 'stage', 'review_pass', 'cycle', *MEASURES, 'coverage')
TICKET_FIELDS = ('ticket', *MEASURES, *ESTIMATES, *PR_FIELDS, 'coverage')
RUN_FIELDS = ('ticket', 'actor', 'metric', 'value', 'numerator', 'denominator', 'repo', 'pr', 'source')


def in_window(time, start, end):
    return time is not None and start <= time < end


def sum_required(values):
    values = list(values)
    return None if any(v is None for v in values) else (
        fsum(values) if any(isinstance(v, float) for v in values) else sum(values))


def iso(value):
    return value.isoformat() if value else None


def coverage(calls, turns, markers=()):
    if any(c.get('missing_reason') or c.get('stage') == 'unknown' or c.get('stage_order') == 'ambiguous' or
           not c.get('ticket') or not c.get('repo') or not c.get('activity') or
           any(c.get(k) is None for k in TOKENS) for c in calls):
        return 'partial'
    if any(not t.ticket or not t.repo or t.minutes is None or t.wait is None or t.stage == 'unknown' or
           t.order == 'ambiguous' or t.parent and any(getattr(t, 'child_' + field) is None
               for field in ('type', 'description', 'family')) for t in turns):
        return 'partial'
    return 'partial' if any(m.kind == 'native_review' for m in markers) else 'complete'
