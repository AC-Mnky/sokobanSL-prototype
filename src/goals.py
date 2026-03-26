from __future__ import annotations

from src.state_utils import is_empty_value
from src.types import State, StaticState


def is_goal(state: State, static_state: StaticState) -> bool:
    for coord, target in static_state.targets.items():
        mono = state.get(coord)
        if is_empty_value(mono):
            return False
        assert mono is not None
        if mono.is_controllable != target.required_is_controllable:
            return False
        if mono.color != target.required_color:
            return False
    return True
