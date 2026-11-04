"""Chart history for one panel, capped at 2000 points."""

from __future__ import annotations

from collections import deque

from contracts.definitions import MAX_HISTORY_POINTS, HistoryPoint, Snapshot

WINDOW = 20


class History:
    """Stores history points and the recent acceptance window."""

    def __init__(self) -> None:
        """Start empty."""
        self.points: list[HistoryPoint] = []
        self._recent: deque[tuple[int, int]] = deque(maxlen=WINDOW)

    def add(self, snap: Snapshot) -> None:
        """Append a point; thin the older half when over the cap."""
        self._recent.append((snap.proposed_total, snap.accepted_total))
        old_proposed, old_accepted = self._recent[0]
        proposed = snap.proposed_total - old_proposed
        rate = (snap.accepted_total - old_accepted) / proposed if proposed > 0 else 0.0
        self.points.append(
            HistoryPoint(
                snap.evaluations,
                snap.elapsed_seconds,
                snap.similarity,
                snap.best_similarity,
                snap.cost,
                min(1.0, max(0.0, rate)),
                dict(snap.extras),
            )
        )
        if len(self.points) > MAX_HISTORY_POINTS:
            half = len(self.points) // 2
            self.points = self.points[:half:2] + self.points[half:]

    def sample(self, max_points: int) -> list[HistoryPoint]:
        """Return at most max_points evenly spaced points, newest included."""
        n = len(self.points)
        if n <= max_points:
            return list(self.points)
        if max_points <= 1:
            return self.points[-1:]
        step = (n - 1) / (max_points - 1)
        return [self.points[round(k * step)] for k in range(max_points)]
