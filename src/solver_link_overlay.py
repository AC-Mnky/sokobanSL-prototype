from __future__ import annotations

from src.core_step import apply_action
from src.state_utils import clone_state
from src.types import Action, Coord, State, StaticState


def _manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def controllable_coords_sorted(state: State) -> tuple[Coord, ...]:
    cells = sorted(
        c
        for c, m in state.items()
        if m is not None and (not m.is_empty) and m.is_controllable
    )
    return tuple(cells)


def build_solver_link_segments(
    initial_state: State,
    static_state: StaticState,
    solution: tuple[Action, ...],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    sim = clone_state(initial_state) or {}
    layers: list[tuple[Coord, ...]] = [controllable_coords_sorted(sim)]
    for action in solution:
        sim = apply_action(sim, action, static_state)
        layers.append(controllable_coords_sorted(sim))

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for t in range(len(layers) - 1):
        for px in layers[t]:
            for q in layers[t + 1]:
                if _manhattan(px, q) <= 1:
                    a = (float(px[0]) + 0.5, float(px[1]) + 0.5)
                    b = (float(q[0]) + 0.5, float(q[1]) + 0.5)
                    segments.append((a, b))
    return segments
