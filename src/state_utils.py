from __future__ import annotations

from typing import Any, Hashable, Optional

from src.types import Coord, MonoData, State


def clone_mono(mono: Optional[MonoData]) -> Optional[MonoData]:
    if mono is None:
        return None
    cloned_data = clone_state(mono.data) if mono.data is not None else None
    return MonoData(
        is_empty=mono.is_empty,
        is_wall=mono.is_wall,
        is_controllable=mono.is_controllable,
        color=mono.color,
        data=cloned_data,
    )


def clone_state(state: Optional[State]) -> Optional[State]:
    if state is None:
        return None
    return {coord: clone_mono(mono) for coord, mono in state.items()}


def mono_deep_equal(a: Optional[MonoData], b: Optional[MonoData]) -> bool:
    if a is b:
        return True
    if a is None or b is None:
        return False
    return (
        a.is_empty == b.is_empty
        and a.is_wall == b.is_wall
        and a.is_controllable == b.is_controllable
        and a.color == b.color
        and state_deep_equal(a.data, b.data)
    )


def state_deep_equal(a: Optional[State], b: Optional[State]) -> bool:
    if a is b:
        return True
    if a is None or b is None:
        return False
    if a.keys() != b.keys():
        return False
    return all(mono_deep_equal(a[k], b[k]) for k in a)


def freeze_mono(mono: Optional[MonoData]) -> Hashable:
    if mono is None:
        return ("none",)
    return (
        "mono",
        mono.is_empty,
        mono.is_wall,
        mono.is_controllable,
        mono.color,
        freeze_state(mono.data),
    )


def freeze_state(state: Optional[State]) -> Hashable:
    if state is None:
        return ("state-none",)
    items = sorted(state.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    return tuple(((x, y), freeze_mono(mono)) for (x, y), mono in items)


def ensure_coord_none(state: State, coord: Coord) -> None:
    if coord not in state:
        state[coord] = None


def air_mono() -> MonoData:
    # Runtime "empty" is represented as MonoData(is_empty=True), not None.
    return MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)


def ensure_coord_air(state: State, coord: Coord) -> None:
    if coord not in state or state[coord] is None:
        state[coord] = air_mono()


def is_empty_value(mono: Optional[MonoData]) -> bool:
    return mono is None or mono.is_empty


def is_solid_value(mono: Optional[MonoData]) -> bool:
    return not is_empty_value(mono)


def step_coord(coord: Coord, action: tuple[int, int]) -> Coord:
    return (coord[0] + action[0], coord[1] + action[1])
