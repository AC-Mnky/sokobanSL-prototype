from __future__ import annotations

import pickle
from pathlib import Path

from src.level_io import (
    load_levels_with_names_and_sections,
    load_levels_with_names_and_split,
    normalize_level_key,
    parse_sequence_sections,
    read_sequence_stems,
    save_level_by_stem,
)
from src.types import Level, StaticState


def _minimal_level() -> Level:
    return Level(static_state=StaticState(targets={}, buttons={}), initial_state={})


def test_normalize_level_key_strips_space_like() -> None:
    assert normalize_level_key("  a\tb\u3000c\n") == "abc"


def test_read_sequence_stems_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text("  foo \n\nbar\t\n", encoding="utf-8")
    assert read_sequence_stems(p) == ["foo", "bar"]


def test_read_sequence_stems_skips_hash_lines(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text("#head\n  foo \n", encoding="utf-8")
    assert read_sequence_stems(p) == ["foo"]


def test_read_sequence_stems_strips_star_prefix(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text("*  hard \nfoo\n", encoding="utf-8")
    assert read_sequence_stems(p) == ["hard", "foo"]


def test_parse_sequence_sections_chapter_lines(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text(
        "  ##  chapter 1  \n  a \n b\n#  two\nb\n",
        encoding="utf-8",
    )
    assert parse_sequence_sections(p) == [
        ("chapter1", [("a", False), ("b", False)]),
        ("two", [("b", False)]),
    ]


def test_parse_sequence_flat_when_no_chapter(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text("c\na\n", encoding="utf-8")
    assert parse_sequence_sections(p) == [(None, [("c", False), ("a", False)])]


def test_parse_sequence_hard_star(tmp_path: Path) -> None:
    p = tmp_path / "sequence.md"
    p.write_text("#X\n*a\nb\n", encoding="utf-8")
    assert parse_sequence_sections(p) == [("X", [("a", True), ("b", False)])]


def test_load_levels_order_and_split(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    for name in ("b", "a", "c"):
        with (levels / f"{name}.pkl").open("wb") as f:
            pickle.dump(_minimal_level(), f)
    seq = tmp_path / "sequence.md"
    seq.write_text("c\na\n", encoding="utf-8")

    entries, split = load_levels_with_names_and_split(levels)
    assert [n for n, _ in entries] == ["c", "a", "b"]
    assert split == 2


def test_load_levels_no_sequence_uses_default_sort(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    for name in ("B", "a", "c"):
        with (levels / f"{name}.pkl").open("wb") as f:
            pickle.dump(_minimal_level(), f)
    entries, split = load_levels_with_names_and_split(levels)
    assert [n for n, _ in entries] == ["a", "B", "c"]
    assert split is None


def test_load_levels_hard_flag_from_star(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    for name in ("a", "b"):
        with (levels / f"{name}.pkl").open("wb") as f:
            pickle.dump(_minimal_level(), f)
    (tmp_path / "sequence.md").write_text("*b\na\n", encoding="utf-8")
    entries, _ui, hard = load_levels_with_names_and_sections(levels)
    assert [n for n, _ in entries] == ["b", "a"]
    assert hard == [True, False]


def test_load_levels_with_chapters_ui_sections(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    for name in ("a", "b", "c"):
        with (levels / f"{name}.pkl").open("wb") as f:
            pickle.dump(_minimal_level(), f)
    (tmp_path / "sequence.md").write_text("#X\nb\na\n#Y\nc\n", encoding="utf-8")
    entries, ui, hard = load_levels_with_names_and_sections(levels)
    assert [n for n, _ in entries] == ["b", "a", "c"]
    assert ui == [("X", 2), ("Y", 1)]
    assert hard == [False, False, False]


def test_load_levels_sequence_only_matches_no_split(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    with (levels / "x.pkl").open("wb") as f:
        pickle.dump(_minimal_level(), f)
    (tmp_path / "sequence.md").write_text("x\n", encoding="utf-8")
    entries, split = load_levels_with_names_and_split(levels)
    assert [n for n, _ in entries] == ["x"]
    assert split is None


def test_save_level_by_stem(tmp_path: Path) -> None:
    levels = tmp_path / "levels"
    levels.mkdir()
    with (levels / "mine.pkl").open("wb") as f:
        pickle.dump(_minimal_level(), f)
    lv = _minimal_level()
    assert save_level_by_stem(levels, "mine", lv)
    with (levels / "mine.pkl").open("rb") as f:
        assert isinstance(pickle.load(f), Level)
