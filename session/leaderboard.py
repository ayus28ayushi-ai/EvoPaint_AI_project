"""Builds the ranked leaderboard."""

from __future__ import annotations

from contracts.definitions import LeaderboardEntry, MilestoneHit, Snapshot


def build_leaderboard(
    snaps: list[Snapshot],
    finished: list[bool],
    milestones: list[dict[int, MilestoneHit]],
    previous_ranks: dict[int, int],
) -> list[LeaderboardEntry]:
    """Rank panels by best similarity; ties go to the lowest panel index."""
    order = sorted(range(len(snaps)), key=lambda i: (-snaps[i].best_similarity, i))
    return [
        LeaderboardEntry(
            rank=rank,
            panel_index=i,
            algorithm_id=snaps[i].algorithm_id,
            best_similarity=snaps[i].best_similarity,
            evaluations=snaps[i].evaluations,
            rank_change=previous_ranks.get(i, rank) - rank,
            finished=finished[i],
            milestones=dict(milestones[i]),
        )
        for rank, i in enumerate(order, start=1)
    ]
