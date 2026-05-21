from __future__ import annotations

from dataclasses import dataclass, field
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
    # Legacy pickle fields; no longer affect S/L.
    reject_save: bool = False
    reject_load: bool = False
    buttons: list[ButtonData] | None = None
    data: Optional["State"] = None


State: TypeAlias = dict[Coord, Optional[MonoData]]


@dataclass(slots=True)
class StaticState:
    targets: dict[Coord, TargetData]
    # Legacy pickle only; migrated into initial_state on load.
    buttons: dict[Coord, list[ButtonData]] = field(default_factory=dict)


LEVEL_FORMAT_VERSION = 2


@dataclass(slots=True)
class Level:
    static_state: StaticState
    initial_state: State
    format_version: int = LEVEL_FORMAT_VERSION
