from __future__ import annotations

from src.core_events import run_event_cycle
from src.core_move import apply_movement
from src.types import Action, State, StaticState


def apply_action(state: State, action: Action, static_state: StaticState) -> State:
    moved = apply_movement(state, action)
    return run_event_cycle(state, moved, static_state)
