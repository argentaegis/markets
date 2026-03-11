"""CandidateStore — lifecycle management for trade candidates.

Stores candidates with validity tracking and replace-dedup on
(symbol, strategy, direction). Expired candidates are swept on
each evaluation cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.candidate import TradeCandidate


def _dedup_key(c: TradeCandidate) -> tuple[str, str, str]:
    return (c.symbol, c.strategy, c.direction.value)


class CandidateStore:
    """Stores trade candidates with validity tracking and deduplication.

    Reasoning: Candidates have a lifecycle — they're created, active for a
    window, then expire. The store manages this lifecycle centrally.
    """

    def __init__(self) -> None:
        self._candidates: list[TradeCandidate] = []

    def add(self, candidates: list[TradeCandidate]) -> list[TradeCandidate]:
        """Deduplicate against existing active candidates, then store.

        Replace semantics: a new candidate whose (symbol, strategy, direction)
        matches an existing one removes the old and stores the new.
        Returns the candidates actually added.
        """
        if not candidates:
            return []

        new_keys = {_dedup_key(c) for c in candidates}
        self._candidates = [
            c for c in self._candidates if _dedup_key(c) not in new_keys
        ]
        self._candidates.extend(candidates)
        return list(candidates)

    def get_active(self, now: datetime | None = None) -> list[TradeCandidate]:
        """Return all non-expired candidates."""
        ts = now if now is not None else datetime.now(timezone.utc)
        return [c for c in self._candidates if c.valid_until > ts]

    def invalidate_expired(self, now: datetime) -> list[TradeCandidate]:
        """Remove and return candidates past their valid_until."""
        expired = [c for c in self._candidates if c.valid_until <= now]
        self._candidates = [c for c in self._candidates if c.valid_until > now]
        return expired

    def enforce_retention(self, max_per_strategy: int) -> list[TradeCandidate]:
        """Remove oldest candidates exceeding per-strategy limit. Return removed.

        Groups by strategy name. Within each group, keeps the newest
        max_per_strategy candidates (by created_at). Removes and returns
        the rest. Strategies with <= limit candidates are untouched.
        """
        groups: dict[str, list[TradeCandidate]] = {}
        for c in self._candidates:
            groups.setdefault(c.strategy, []).append(c)

        keep: list[TradeCandidate] = []
        removed: list[TradeCandidate] = []
        for candidates in groups.values():
            sorted_desc = sorted(candidates, key=lambda c: c.created_at, reverse=True)
            keep.extend(sorted_desc[:max_per_strategy])
            removed.extend(sorted_desc[max_per_strategy:])

        self._candidates = keep
        return removed
