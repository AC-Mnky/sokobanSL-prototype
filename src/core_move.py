from __future__ import annotations

from src.state_utils import clone_state, ensure_coord_none, is_empty_value, step_coord
from src.types import Action, Coord, MonoData, State, VALID_ACTIONS


def _can_push_through_chain(state: State, start: Coord, action: Action) -> bool:
    cur = start
    while True:
        ensure_coord_none(state, cur)
        mono = state[cur]
        if is_empty_value(mono):
            return True
        if mono is not None and mono.is_wall:
            return False
        cur = step_coord(cur, action)


def apply_movement(state: State, action: Action) -> State:
    if action not in VALID_ACTIONS:
        return clone_state(state) or {}

    next_state = clone_state(state) or {}
    controllables = [
        coord
        for coord, mono in next_state.items()
        if mono is not None and (not mono.is_empty) and mono.is_controllable
    ]

    movers: set[Coord] = set()
    for c in controllables:
        ahead = step_coord(c, action)
        if _can_push_through_chain(next_state, ahead, action):
            cur = ahead
            movers.add(c)
            while True:
                ensure_coord_none(next_state, cur)
                mono = next_state[cur]
                if is_empty_value(mono):
                    break
                movers.add(cur)
                cur = step_coord(cur, action)

    if not movers:
        return next_state

    moving_values: dict[Coord, MonoData] = {}
    for src in movers:
        mono = next_state.get(src)
        if mono is not None and not mono.is_empty:
            moving_values[src] = mono

    for src in moving_values:
        next_state[src] = None

    for src, mono in moving_values.items():
        dst = step_coord(src, action)
        ensure_coord_none(next_state, dst)
        next_state[dst] = mono

    return next_state
