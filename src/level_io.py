from __future__ import annotations

import pickle
from pathlib import Path

from src.sample_levels import make_basic_levels
from src.state_utils import normalize_level_monos
from src.types import Level


def _level_dir(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix == ".pkl":
        return p.parent / p.stem
    return p


def _iter_level_files(levels_dir: Path) -> list[Path]:
    if not levels_dir.exists():
        return []
    return sorted(levels_dir.glob("*.pkl"), key=lambda fp: fp.name.lower())


def load_levels_with_names(path: str | Path) -> list[tuple[str, Level]]:
    levels_dir = _level_dir(path)
    entries: list[tuple[str, Level]] = []
    for fp in _iter_level_files(levels_dir):
        with fp.open("rb") as f:
            level = pickle.load(f)
        normalize_level_monos(level)
        entries.append((fp.stem, level))
    return entries


def load_levels(path: str | Path) -> list[Level]:
    return [level for _, level in load_levels_with_names(path)]


def save_levels(path: str | Path, levels: list[Level]) -> None:
    levels_dir = _level_dir(path)
    levels_dir.mkdir(parents=True, exist_ok=True)
    for old_file in _iter_level_files(levels_dir):
        old_file.unlink()
    for i, level in enumerate(levels, start=1):
        out = levels_dir / f"level_{i:03d}.pkl"
        with out.open("wb") as f:
            pickle.dump(level, f)


def export_builtin_levels(path: str | Path) -> list[Level]:
    levels = make_basic_levels()
    save_levels(path, levels)
    return levels


def save_level_by_index(path: str | Path, index: int, level: Level) -> bool:
    if index < 0:
        return False
    levels_dir = _level_dir(path)
    files = _iter_level_files(levels_dir)
    if index >= len(files):
        return False
    with files[index].open("wb") as f:
        pickle.dump(level, f)
    return True
