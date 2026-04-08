from __future__ import annotations

import pickle
from pathlib import Path

from src.sample_levels import make_basic_levels
from src.state_utils import normalize_level_monos
from src.types import Level

SEQUENCE_FILENAME = "sequence.md"


def normalize_level_key(s: str) -> str:
    """Remove all Unicode whitespace-like characters for sequence / stem matching."""
    return "".join(c for c in s if not c.isspace())


def read_sequence_stems(sequence_path: Path) -> list[str]:
    if not sequence_path.is_file():
        return []
    text = sequence_path.read_text(encoding="utf-8")
    out: list[str] = []
    for line in text.splitlines():
        key = normalize_level_key(line)
        if key and not key.startswith("#"):
            out.append(key)
    return out


def parse_sequence_sections(sequence_path: Path) -> list[tuple[str | None, list[str]]]:
    """Parse sequence.md into (chapter_title, level_keys). Chapter lines: after removing all
    whitespace, the line starts with '#'; title is the rest after stripping leading '#' chars.
    If the file has no such line, returns a single section (None, [all keys in file order])."""
    if not sequence_path.is_file():
        return []
    lines = sequence_path.read_text(encoding="utf-8").splitlines()
    normalized_nonempty: list[str] = []
    has_chapter_line = False
    for line in lines:
        nk = normalize_level_key(line)
        if not nk:
            continue
        normalized_nonempty.append(nk)
        if nk.startswith("#"):
            has_chapter_line = True
    if not normalized_nonempty:
        return []
    if not has_chapter_line:
        return [(None, normalized_nonempty)]

    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_keys: list[str] = []

    def flush_section() -> None:
        nonlocal current_title, current_keys
        if current_title is not None or current_keys:
            sections.append((current_title, list(current_keys)))
        current_keys = []

    for line in lines:
        nk = normalize_level_key(line)
        if not nk:
            continue
        if nk.startswith("#"):
            flush_section()
            current_title = nk.lstrip("#") or None
        else:
            current_keys.append(nk)
    flush_section()
    return sections


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
    entries, _sections = load_levels_with_names_and_sections(path)
    return entries


def load_levels_with_names_and_sections(
    path: str | Path,
) -> tuple[list[tuple[str, Level]], list[tuple[str | None, int]]]:
    """Load levels ordered by sequence.md. Returns (entries, ui_sections) where each UI section is
    (chapter_title_or_None, button_count). Title None means no heading row."""
    levels_dir = _level_dir(path)
    by_key: dict[str, tuple[str, Level]] = {}
    for fp in _iter_level_files(levels_dir):
        with fp.open("rb") as f:
            level = pickle.load(f)
        normalize_level_monos(level)
        key = normalize_level_key(fp.stem)
        if key not in by_key:
            by_key[key] = (fp.stem, level)

    sequence_path = levels_dir.parent / SEQUENCE_FILENAME
    parsed = parse_sequence_sections(sequence_path)
    if not parsed:
        default = [by_key[k] for k in sorted(by_key, key=lambda x: x.lower())]
        if not default:
            return [], []
        return default, [(None, len(default))]

    merged: list[tuple[str, Level]] = []
    used: set[str] = set()
    ui_sections: list[tuple[str | None, int]] = []

    for title, keys in parsed:
        n_here = 0
        for sk in keys:
            if sk in used:
                continue
            pair = by_key.get(sk)
            if pair is not None:
                merged.append(pair)
                used.add(sk)
                n_here += 1
        if title is not None:
            ui_sections.append((title, n_here))
        elif n_here > 0:
            ui_sections.append((None, n_here))

    default_keys = sorted(by_key.keys(), key=lambda x: x.lower())
    rest_pairs = [by_key[k] for k in default_keys if k not in used]
    if rest_pairs:
        merged.extend(rest_pairs)
        ui_sections.append(("其他", len(rest_pairs)))

    total_ui = sum(c for _, c in ui_sections)
    if total_ui != len(merged):
        ui_sections = [(None, len(merged))]
    return merged, ui_sections


def load_levels_with_names_and_split(path: str | Path) -> tuple[list[tuple[str, Level]], int | None]:
    """Backward-compatible: returns (entries, split_after) when exactly two UI groups: sequenced + 其他."""
    entries, sections = load_levels_with_names_and_sections(path)
    if len(sections) == 2 and sections[1][0] == "其他":
        return entries, sections[0][1]
    if len(sections) == 1:
        return entries, None
    return entries, None


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


def save_level_by_stem(path: str | Path, stem: str, level: Level) -> bool:
    levels_dir = _level_dir(path)
    fp = levels_dir / f"{stem}.pkl"
    if not fp.is_file():
        return False
    with fp.open("wb") as f:
        pickle.dump(level, f)
    return True
