"""Leader / laggard detection by pattern-signature clustering."""

from __future__ import annotations

from bot.scanner.models import TickerState
from bot.ta.similarity import pattern_similarity


def assign_roles(
    states: list[TickerState],
    similarity_threshold: float = 0.7,
) -> list[TickerState]:
    """Group symbols by pattern similarity; assign leader/laggard/standalone roles.

    Algorithm:
    1. Build pairwise similarity matrix.
    2. Greedy clustering: any pair with similarity ≥ threshold is in the same group.
    3. Within each group ≥ 2:
       - Leader = member with highest (pct_change + MACD-favorability×10).
       - Laggards = other group members that have news.
       - Remaining group members without news stay standalone.
    4. Singletons = standalone.

    Returns a new list with roles assigned (originals are not mutated).
    """
    if not states:
        return []

    n = len(states)
    # Union-find for clustering
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    for i in range(n):
        for j in range(i + 1, n):
            sim = pattern_similarity(
                states[i].pattern_signature,
                states[j].pattern_signature,
            )
            if sim >= similarity_threshold:
                union(i, j)

    # Group by cluster root
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    updated = [s.model_copy() for s in states]

    for indices in clusters.values():
        if len(indices) == 1:
            updated[indices[0]] = updated[indices[0]].model_copy(
                update={"role": "standalone"}
            )
            continue

        # Score for leader election: pct_change + MACD favorability bonus
        def _leader_score(idx: int) -> float:
            s = updated[idx]
            return s.pct_change + s.macd_state.favorability * 10.0

        best_idx = max(indices, key=_leader_score)
        updated[best_idx] = updated[best_idx].model_copy(update={"role": "leader"})

        for idx in indices:
            if idx == best_idx:
                continue
            role = "laggard" if updated[idx].has_news else "standalone"
            updated[idx] = updated[idx].model_copy(update={"role": role})

    return updated
