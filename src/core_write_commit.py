from __future__ import annotations

from collections import defaultdict

from src.state_utils import clone_state, ensure_coord_none, mono_deep_equal
from src.types import Coord, MonoData, State


def commit_writes(state: State, writes: list[State]) -> State:
    next_state = clone_state(state) or {}
    per_coord: dict[Coord, list[MonoData]] = defaultdict(list)

    for write in writes:
        for coord, value in write.items():
            ensure_coord_none(next_state, coord)
            if value is None:
                continue
            per_coord[coord].append(value)

    for coord, candidates in per_coord.items():
        groups: list[tuple[MonoData, int]] = []
        for cand in candidates:
            matched = False
            for i, (sample, count) in enumerate(groups):
                if mono_deep_equal(sample, cand):
                    groups[i] = (sample, count + 1)
                    matched = True
                    break
            if not matched:
                groups.append((cand, 1))
        groups.sort(key=lambda x: x[1], reverse=True)
        if len(groups) == 1 or groups[0][1] > groups[1][1]:
            next_state[coord] = groups[0][0]
        # tie: keep old value

    return next_state
