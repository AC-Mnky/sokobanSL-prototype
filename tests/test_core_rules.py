from src.core_events import build_event_writes, collect_edge_events
from src.core_step import apply_action
from src.core_write_commit import commit_writes
from src.types import ButtonData, MonoData, StaticState, TargetData


def player(color: int = 1) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=True, color=color, data=None)


def box(color: int = 0) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=False, color=color, data=None)


def wall() -> MonoData:
    return MonoData(is_empty=False, is_wall=True, is_controllable=False, color=0, data=None)


def test_movement_generates_none_outside_map():
    static_state = StaticState(targets={}, buttons={})
    state = {(0, 0): player()}
    next_state = apply_action(state, (1, 0), static_state)
    assert next_state[(1, 0)] is not None
    assert next_state[(0, 0)] is not None
    assert next_state[(0, 0)].is_empty


def test_edge_event_uses_is_empty_only():
    static_state = StaticState(targets={}, buttons={(0, 0): [ButtonData("s", 1)]})
    prev_state = {(0, 0): None}
    next_state = {(0, 0): box(2)}
    events = collect_edge_events(prev_state, next_state, static_state)
    assert len(events) == 1
    assert events[0].button_type == "s"


def test_write_conflict_majority_and_tie():
    state = {(0, 0): box(9)}
    a = {(0, 0): box(1)}
    b = {(0, 0): box(1)}
    c = {(0, 0): box(2)}
    out = commit_writes(state, [a, b, c])
    assert out[(0, 0)] is not None and out[(0, 0)].color == 1

    d = {(0, 0): box(3)}
    out2 = commit_writes(state, [a, d])
    assert out2[(0, 0)] is not None and out2[(0, 0)].color == 9


def test_s_disk_snapshot_keeps_old_when_world_is_none():
    old = box(7)
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(1, 1): old})
    state = {(0, 0): disk}
    events = [ButtonData("s", 1)]
    writes = build_event_writes(state, events, StaticState(targets={}, buttons={}))
    assert len(writes) == 1
    new_disk = writes[0].get((0, 0))
    assert new_disk is not None and new_disk.data is not None
    assert new_disk.data.get((1, 1)) is not None
    assert new_disk.data[(1, 1)].color == 7


def test_s_disk_snapshot_resolves_region_relative_to_disk_cell():
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(1, 0): None})
    state = {(2, 1): disk, (3, 1): box(5)}
    events = [ButtonData("s", 1)]
    writes = build_event_writes(state, events, StaticState(targets={}, buttons={}))
    assert len(writes) == 1
    new_disk = writes[0].get((2, 1))
    assert new_disk is not None and new_disk.data is not None
    assert new_disk.data.get((1, 0)) is not None
    assert new_disk.data[(1, 0)].color == 5


def test_s_disk_snapshot_skips_reject_save_cell():
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(1, 0): box(5)})
    no_save = box(9)
    no_save.reject_save = True
    state = {(2, 1): disk, (3, 1): no_save}
    writes = build_event_writes(state, [ButtonData("s", 1)], StaticState(targets={}, buttons={}))
    new_disk = writes[0].get((2, 1))
    assert new_disk is not None and new_disk.data is not None
    assert new_disk.data[(1, 0)].color == 5


def test_l_write_skips_reject_load_cell():
    protected = box(3)
    protected.reject_load = True
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(1, 0): box(8)})
    state = {(0, 0): disk, (1, 0): protected}
    writes = build_event_writes(state, [ButtonData("l", 1)], StaticState(targets={}, buttons={}))
    assert writes == []
    out = commit_writes(state, writes)
    assert out[(1, 0)] is not None and out[(1, 0)].color == 3
