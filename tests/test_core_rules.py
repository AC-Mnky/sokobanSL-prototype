from src.core_events import collect_edge_events
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
    assert next_state[(0, 0)] is None


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
