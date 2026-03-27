from __future__ import annotations

from src.state_utils import air_mono, is_empty_value, step_coord
from src.types import Action, Coord, MonoData, State, VALID_ACTIONS


def _can_push_through_chain(state: State, start: Coord, action: Action) -> bool:
    cur = start
    while True:
        mono = state.get(cur)
        if is_empty_value(mono):
            return True
        if mono is not None and mono.is_wall:
            return False
        cur = step_coord(cur, action)


def apply_movement(state: State, action: Action) -> State:
    if action not in VALID_ACTIONS:
        return state
    controllables = [
        coord
        for coord, mono in state.items()
        if mono is not None and (not mono.is_empty) and mono.is_controllable
    ]

    movers: set[Coord] = set()
    for c in controllables:
        ahead = step_coord(c, action)
        if _can_push_through_chain(state, ahead, action):
            cur = ahead
            movers.add(c)
            while True:
                mono = state.get(cur)
                if is_empty_value(mono):
                    break
                movers.add(cur)
                cur = step_coord(cur, action)

    if not movers:
        return state

    moving_values: dict[Coord, MonoData] = {}
    for src in movers:
        mono = state.get(src)
        if mono is not None and not mono.is_empty:
            moving_values[src] = mono

    next_state = dict(state)
    for src in moving_values:
        next_state[src] = air_mono()

    for src, mono in moving_values.items():
        dst = step_coord(src, action)
        next_state[dst] = mono

    return next_state
