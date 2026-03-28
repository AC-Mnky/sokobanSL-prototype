from __future__ import annotations

from src.state_utils import sub_coord
from src.types import Coord, Level, MonoData, State


def migrate_mono_disk_data_to_relative(mono: MonoData, disk_world_pos: Coord) -> None:
    """Rewrite mono.data keys from world coords to offsets from disk_world_pos. Mutates mono."""
    if mono.data is None:
        return
    items = list(mono.data.items())
    mono.data = {}
    for wcoord, cell in items:
        rel = sub_coord(wcoord, disk_world_pos)
        if cell is not None:
            migrate_mono_disk_data_to_relative(cell, wcoord)
        mono.data[rel] = cell


def migrate_state_disk_data_to_relative(state: State) -> None:
    for coord, mono in list(state.items()):
        if mono is None or mono.is_empty:
            continue
        if mono.data is not None:
            migrate_mono_disk_data_to_relative(mono, coord)


def migrate_level_disk_data_to_relative(level: Level) -> None:
    migrate_state_disk_data_to_relative(level.initial_state)
