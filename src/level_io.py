from __future__ import annotations

import pickle
from pathlib import Path

from src.sample_levels import make_basic_levels
from src.types import Level


def load_levels(path: str | Path) -> list[Level]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("rb") as f:
        levels = pickle.load(f)
    return levels


def save_levels(path: str | Path, levels: list[Level]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        pickle.dump(levels, f)


def export_builtin_levels(path: str | Path) -> list[Level]:
    levels = make_basic_levels()
    save_levels(path, levels)
    return levels


def save_level_by_index(path: str | Path, index: int, level: Level) -> bool:
    if index < 0:
        return False
    levels = load_levels(path)
    if index >= len(levels):
        return False
    levels[index] = level
    save_levels(path, levels)
    return True
