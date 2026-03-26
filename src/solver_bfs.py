from __future__ import annotations

from collections import deque
from typing import Callable, Generator

from src.core_step import apply_action
from src.state_utils import clone_state, freeze_state
from src.types import Action, State, StaticState, VALID_ACTIONS


SolverYield = tuple[str, int, tuple[Action, ...], int]


def solve(
    initial_state: State,
    static_state: StaticState,
    goal_predicate: Callable[[State, StaticState], bool],
    step_chunk: int = 1024,
) -> Generator[SolverYield, None, None]:
    init = clone_state(initial_state) or {}
    if goal_predicate(init, static_state):
        yield ("solved", 0, tuple(), 0)
        return

    queue: deque[tuple[State, tuple[Action, ...], int]] = deque([(init, tuple(), 0)])
    visited = {freeze_state(init)}
    searched = 0

    while queue:
        state, path, depth = queue.popleft()
        searched += 1
        if searched % step_chunk == 0:
            yield ("solving", depth, tuple(), searched)

        for action in VALID_ACTIONS:
            next_state = apply_action(state, action, static_state)
            frozen = freeze_state(next_state)
            if frozen in visited:
                continue
            visited.add(frozen)
            next_path = path + (action,)
            if goal_predicate(next_state, static_state):
                yield ("solved", len(next_path), next_path, searched)
                return
            queue.append((next_state, next_path, depth + 1))
