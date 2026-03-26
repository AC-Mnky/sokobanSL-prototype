from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, TypeAlias

Coord: TypeAlias = tuple[int, int]
Action: TypeAlias = tuple[int, int]
Color: TypeAlias = int
ButtonType: TypeAlias = Literal["s", "l"]

VALID_ACTIONS: set[Action] = {(1, 0), (-1, 0), (0, 1), (0, -1)}


@dataclass(slots=True)
class TargetData:
    required_is_controllable: bool
    required_color: int


@dataclass(slots=True)
class ButtonData:
    button_type: ButtonType
    color: int


Event: TypeAlias = ButtonData


@dataclass(slots=True)
class MonoData:
    is_empty: bool = False
    is_wall: bool = False
    is_controllable: bool = False
    color: int = 0
    data: Optional["State"] = None


State: TypeAlias = dict[Coord, Optional[MonoData]]


@dataclass(slots=True)
class StaticState:
    targets: dict[Coord, TargetData]
    buttons: dict[Coord, list[ButtonData]]


@dataclass(slots=True)
class Level:
    static_state: StaticState
    initial_state: State
