import pickle
from pathlib import Path

from src.level_io import dump_level_to_pickle, load_level_from_pickle, save_level_by_stem
from src.state_utils import air_mono, get_buttons, prepare_level_after_load
from src.types import ButtonData, Level, MonoData, StaticState, TargetData


def test_migrate_level_buttons_no_key():
    level = Level(
        static_state=StaticState(targets={}, buttons={(1, 0): [ButtonData("s", 2)]}),
        initial_state={},
    )
    prepare_level_after_load(level)
    assert get_buttons(level.initial_state[(1, 0)]) == [ButtonData("s", 2)]
    assert level.static_state.buttons == {}


def test_migrate_level_buttons_none_value():
    level = Level(
        static_state=StaticState(targets={}, buttons={(0, 0): [ButtonData("l", 1)]}),
        initial_state={(0, 0): None},
    )
    prepare_level_after_load(level)
    mono = level.initial_state[(0, 0)]
    assert mono is not None and mono.is_empty
    assert get_buttons(mono) == [ButtonData("l", 1)]


def test_migrate_level_buttons_merges_with_entity():
    entity = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=3, data=None)
    level = Level(
        static_state=StaticState(targets={}, buttons={(0, 0): [ButtonData("s", 1)]}),
        initial_state={(0, 0): entity},
    )
    prepare_level_after_load(level)
    assert get_buttons(level.initial_state[(0, 0)]) == [ButtonData("s", 1)]
    assert level.static_state.buttons == {}


def test_load_legacy_level_migrates_in_memory_only(tmp_path: Path):
    legacy = Level(
        static_state=StaticState(
            targets={(2, 0): TargetData(required_is_controllable=True, required_color=1)},
            buttons={(1, 0): [ButtonData("s", 1), ButtonData("l", 1)]},
        ),
        initial_state={(0, 0): MonoData(is_empty=False, is_controllable=True, color=1, data=None)},
        format_version=1,
    )
    fp = tmp_path / "legacy.pkl"
    with fp.open("wb") as f:
        pickle.dump(legacy, f)

    with fp.open("rb") as f:
        loaded = load_level_from_pickle(pickle.load(f))
    assert get_buttons(loaded.initial_state[(1, 0)])
    assert loaded.static_state.buttons == {}
    assert getattr(loaded, "format_version", 1) == 1

    with fp.open("rb") as f:
        on_disk = pickle.load(f)
    assert on_disk.static_state.buttons
    assert on_disk.static_state.buttons
    assert getattr(on_disk, "format_version", 1) < 2


def test_save_writes_format_version_2(tmp_path: Path):
    level = Level(
        static_state=StaticState(
            targets={},
            buttons={(0, 0): [ButtonData("s", 1)]},
        ),
        initial_state={(0, 0): air_mono([ButtonData("s", 1)])},
    )
    prepare_level_after_load(level)
    fp = tmp_path / "saved.pkl"
    with fp.open("wb") as f:
        pickle.dump(dump_level_to_pickle(level), f)

    with fp.open("rb") as f:
        reloaded = load_level_from_pickle(pickle.load(f))
    assert reloaded.format_version == 2
    assert reloaded.static_state.buttons == {}
    assert get_buttons(reloaded.initial_state[(0, 0)])

    save_level_by_stem(tmp_path, "saved", level)
    with fp.open("rb") as f:
        again = load_level_from_pickle(pickle.load(f))
    assert again.format_version == 2
