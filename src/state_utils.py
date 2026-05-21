from __future__ import annotations

from dataclasses import MISSING, fields
from typing import Any, Hashable, Optional

from src.types import (
    LEVEL_FORMAT_VERSION,
    ButtonData,
    Coord,
    Level,
    MonoData,
    State,
    StaticState,
    TargetData,
)


def clone_buttons(buttons: list[ButtonData] | None) -> list[ButtonData] | None:
    if not buttons:
        return None
    return [ButtonData(button_type=b.button_type, color=b.color) for b in buttons]


def get_buttons(mono: Optional[MonoData]) -> list[ButtonData]:
    if mono is None or not mono.buttons:
        return []
    return mono.buttons


def merge_buttons(
    a: list[ButtonData] | None,
    b: list[ButtonData] | None,
) -> list[ButtonData] | None:
    merged = list(a or []) + list(b or [])
    return merged if merged else None


def freeze_buttons(buttons: list[ButtonData] | None) -> Hashable:
    if not buttons:
        return ()
    return tuple((b.button_type, b.color) for b in buttons)


def clone_mono(mono: Optional[MonoData]) -> Optional[MonoData]:
    if mono is None:
        return None
    cloned_data = clone_state(mono.data) if mono.data is not None else None
    return MonoData(
        is_empty=mono.is_empty,
        is_wall=mono.is_wall,
        is_controllable=mono.is_controllable,
        color=mono.color,
        reject_save=mono.reject_save,
        reject_load=mono.reject_load,
        buttons=clone_buttons(mono.buttons),
        data=cloned_data,
    )


def clone_state(state: Optional[State]) -> Optional[State]:
    if state is None:
        return None
    return {coord: clone_mono(mono) for coord, mono in state.items()}


def clone_static_state(static_state: Optional[StaticState]) -> Optional[StaticState]:
    if static_state is None:
        return None
    return StaticState(
        targets={
            coord: TargetData(
                required_is_controllable=target.required_is_controllable,
                required_color=target.required_color,
            )
            for coord, target in static_state.targets.items()
        },
        buttons={
            coord: [ButtonData(button_type=b.button_type, color=b.color) for b in buttons]
            for coord, buttons in static_state.buttons.items()
        },
    )


def buttons_deep_equal(a: list[ButtonData] | None, b: list[ButtonData] | None) -> bool:
    if not a and not b:
        return True
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    return all(x.button_type == y.button_type and x.color == y.color for x, y in zip(a, b))


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
        and a.reject_save == b.reject_save
        and a.reject_load == b.reject_load
        and buttons_deep_equal(a.buttons, b.buttons)
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
    if mono.data is None:
        return (
            "mono",
            mono.is_empty,
            mono.is_wall,
            mono.is_controllable,
            mono.color,
            mono.reject_save,
            mono.reject_load,
            freeze_buttons(mono.buttons),
            ("state-none",),
        )
    return (
        "mono",
        mono.is_empty,
        mono.is_wall,
        mono.is_controllable,
        mono.color,
        mono.reject_save,
        mono.reject_load,
        freeze_buttons(mono.buttons),
        freeze_state(mono.data),
    )


_COORD_ORDER_CACHE: dict[frozenset[Coord], tuple[Coord, ...]] = {}


def freeze_state(state: Optional[State]) -> Hashable:
    if state is None:
        return ("state-none",)
    key_set = frozenset(state.keys())
    coords = _COORD_ORDER_CACHE.get(key_set)
    if coords is None:
        coords = tuple(sorted(key_set, key=lambda c: (c[0], c[1])))
        _COORD_ORDER_CACHE[key_set] = coords
    return tuple((coord, freeze_mono(state.get(coord))) for coord in coords)


def ensure_coord_none(state: State, coord: Coord) -> None:
    if coord not in state:
        state[coord] = None


def air_mono(buttons: list[ButtonData] | None = None) -> MonoData:
    return MonoData(
        is_empty=True,
        is_wall=False,
        is_controllable=False,
        color=0,
        reject_save=False,
        reject_load=False,
        buttons=clone_buttons(buttons),
        data=None,
    )


def vacate_occupant(mono: MonoData) -> MonoData:
    return air_mono(mono.buttons)


def place_occupant(moving: MonoData, dst_mono: Optional[MonoData]) -> MonoData:
    """Place solid/air occupant at dst; buttons stay on the cell layer (from dst only), not on the mover."""
    placed = clone_mono(moving)
    assert placed is not None
    placed.buttons = clone_buttons(get_buttons(dst_mono))
    return placed


def normalize_mono(mono: MonoData) -> MonoData:
    """Rebuild MonoData so new fields exist (old pickles may omit slots). Recurses into data."""
    kw: dict[str, Any] = {}
    for f in fields(MonoData):
        try:
            v: Any = getattr(mono, f.name)
        except AttributeError:
            if f.default is not MISSING:
                v = f.default
            elif f.default_factory is not MISSING:
                v = f.default_factory()
            else:
                raise
        if f.name == "data" and v is not None:
            v = {c: normalize_mono(m) if m is not None else None for c, m in v.items()}
        elif f.name == "buttons" and v:
            v = clone_buttons(v)
        kw[f.name] = v
    return MonoData(**kw)


def normalize_state_monos(state: State) -> None:
    for coord in list(state.keys()):
        m = state.get(coord)
        if m is not None:
            state[coord] = normalize_mono(m)


def migrate_level_buttons(level: Level) -> None:
    static_buttons = level.static_state.buttons
    if not static_buttons:
        return
    for coord, buttons in list(static_buttons.items()):
        migrated = [ButtonData(button_type=b.button_type, color=b.color) for b in buttons]
        mono = level.initial_state.get(coord)
        if mono is None:
            level.initial_state[coord] = air_mono(migrated)
        else:
            mono.buttons = merge_buttons(mono.buttons, migrated)
    static_buttons.clear()


def prepare_level_for_save(level: Level) -> Level:
    """Return a v2-ready level copy: buttons in state, empty static.buttons."""
    out = Level(
        static_state=StaticState(
            targets={
                coord: TargetData(
                    required_is_controllable=t.required_is_controllable,
                    required_color=t.required_color,
                )
                for coord, t in level.static_state.targets.items()
            },
            buttons={},
        ),
        initial_state=clone_state(level.initial_state) or {},
        format_version=LEVEL_FORMAT_VERSION,
    )
    return out


def prepare_level_after_load(level: Level) -> None:
    normalize_state_monos(level.initial_state)
    fv = getattr(level, "format_version", 1)
    if fv < LEVEL_FORMAT_VERSION or level.static_state.buttons:
        migrate_level_buttons(level)


def normalize_level_monos(level: Level) -> None:
    prepare_level_after_load(level)


def ensure_coord_air(state: State, coord: Coord) -> None:
    if coord not in state or state[coord] is None:
        state[coord] = air_mono()


def append_button(state: State, coord: Coord, button: ButtonData) -> None:
    ensure_coord_air(state, coord)
    mono = state[coord]
    assert mono is not None
    mono.buttons = merge_buttons(mono.buttons, [button])


def clear_buttons_at(state: State, coord: Coord) -> None:
    mono = state.get(coord)
    if mono is None:
        return
    mono.buttons = None
    if mono.is_empty and not mono.data:
        state.pop(coord, None)


def has_buttons(mono: Optional[MonoData]) -> bool:
    return bool(get_buttons(mono))


def is_empty_value(mono: Optional[MonoData]) -> bool:
    return mono is None or mono.is_empty


def is_solid_value(mono: Optional[MonoData]) -> bool:
    return not is_empty_value(mono)


def step_coord(coord: Coord, action: tuple[int, int]) -> Coord:
    return (coord[0] + action[0], coord[1] + action[1])


def add_coord(a: Coord, b: Coord) -> Coord:
    return (a[0] + b[0], a[1] + b[1])


def sub_coord(a: Coord, b: Coord) -> Coord:
    return (a[0] - b[0], a[1] - b[1])
