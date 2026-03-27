from __future__ import annotations

from collections import deque
from time import perf_counter
from typing import Callable, Generator

from src.core_step import apply_action
from src.state_utils import clone_state, freeze_state
from src.types import Action, State, StaticState, VALID_ACTIONS


SolverYield = tuple[str, int, tuple[Action, ...], int, float]


def _build_path(
    parents: list[int],
    actions_from_parent: list[Action | None],
    node_idx: int,
) -> tuple[Action, ...]:
    out: list[Action] = []
    cur = node_idx
    while cur != 0:
        action = actions_from_parent[cur]
        assert action is not None
        out.append(action)
        cur = parents[cur]
    out.reverse()
    return tuple(out)


def solve(
    initial_state: State,
    static_state: StaticState,
    goal_predicate: Callable[[State, StaticState], bool],
    step_chunk: int = 1024,
) -> Generator[SolverYield, None, None]:
    t0 = perf_counter()
    init = clone_state(initial_state) or {}
    if goal_predicate(init, static_state):
        yield ("solved", 0, tuple(), 0, perf_counter() - t0)
        return

    # Store only node index + depth in queue; path is rebuilt on demand by parent links.
    states: list[State] = [init]
    parents: list[int] = [-1]
    actions_from_parent: list[Action | None] = [None]
    queue: deque[tuple[int, int]] = deque([(0, 0)])
    visited = {freeze_state(init)}
    searched = 0

    while queue:
        node_idx, depth = queue.popleft()
        state = states[node_idx]
        searched += 1
        if searched % step_chunk == 0:
            yield ("solving", depth, tuple(), searched, perf_counter() - t0)

        for action in VALID_ACTIONS:
            next_state = apply_action(state, action, static_state)
            if next_state is state:
                continue
            frozen = freeze_state(next_state)
            if frozen in visited:
                continue
            visited.add(frozen)
            next_idx = len(states)
            states.append(next_state)
            parents.append(node_idx)
            actions_from_parent.append(action)
            if goal_predicate(next_state, static_state):
                solution = _build_path(parents, actions_from_parent, next_idx)
                yield ("solved", len(solution), solution, searched, perf_counter() - t0)
                return
            queue.append((next_idx, depth + 1))
