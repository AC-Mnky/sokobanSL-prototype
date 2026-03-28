from __future__ import annotations

from src.types import ButtonData, Level, MonoData, StaticState, TargetData


def _air() -> MonoData:
    return MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)

def _player(color: int = 0) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=True, color=color, data=None)

def _wall() -> MonoData:
    return MonoData(is_empty=False, is_wall=True, is_controllable=False, color=0, data=None)

def _box() -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=False, color=0, data=None)

def _disk(color: int, data: dict | None) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=False, color=color, data=data)


def make_basic_levels() -> list[Level]:
    levels = []

    static_state = StaticState(
        targets={(1, 0): TargetData(required_is_controllable=True, required_color=1)},
        buttons={(0, 1): [ButtonData(button_type="s", color=1), ButtonData(button_type="l", color=1)]},
    )
    initial_state = {
        (0, 0): _player(1),
        (2, 0): _wall(),
        (1, 1): _disk(1, {(-1, -1): None, (0, -1): None}),
    }
    levels.append(Level(static_state=static_state, initial_state=initial_state))

    static_state = StaticState(
        targets={(5, 2): TargetData(required_is_controllable=True, required_color=0),
                 (5, 3): TargetData(required_is_controllable=False, required_color=0),
                 (5, 4): TargetData(required_is_controllable=False, required_color=0),},
        buttons={(2, 1): [ButtonData(button_type="s", color=1)],
                 (3, 1): [ButtonData(button_type="l", color=1)]},
    )
    initial_state = {}
    for i in range(-1, 7):
        for j in range(-1, 7):
            initial_state[(i, j)] = _wall()
    for i in range(0, 6):
        for j in range(0, 6):
            initial_state[(i, j)] = _air()

    initial_state[(0, 3)] = _player(0)
    initial_state[(1, 2)] = _box()
    initial_state[(0, 0)] = _disk(1, {(2, 3): None, (2, 4): None, (3, 3): None, (3, 4): None})
    levels.append(Level(static_state=static_state, initial_state=initial_state))

    return levels
