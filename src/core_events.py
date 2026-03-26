from __future__ import annotations

from src.core_write_commit import commit_writes
from src.state_utils import clone_mono, clone_state, is_empty_value
from src.types import ButtonData, Event, MonoData, State, StaticState


def _is_pressed(state: State, coord: tuple[int, int]) -> bool:
    return not is_empty_value(state.get(coord))


def collect_edge_events(prev_state: State, next_state: State, static_state: StaticState) -> list[Event]:
    events: list[Event] = []
    for coord, buttons in static_state.buttons.items():
        if (not _is_pressed(prev_state, coord)) and _is_pressed(next_state, coord):
            events.extend(buttons)
    return events


def _disk_coords_by_color(state: State, color: int) -> list[tuple[int, int]]:
    coords: list[tuple[int, int]] = []
    for coord, mono in state.items():
        if mono is None or mono.is_empty or mono.is_wall:
            continue
        if mono.color == color and mono.data is not None:
            coords.append(coord)
    return coords


def _snapshot_from_disk_region(world: State, disk_data: State) -> State:
    snapshot: State = {}
    for coord in disk_data.keys():
        snapshot[coord] = clone_mono(world.get(coord))
    return snapshot


def build_event_writes(state: State, events: list[Event], static_state: StaticState) -> list[State]:
    del static_state
    writes: list[State] = []
    for event in events:
        for disk_coord in _disk_coords_by_color(state, event.color):
            disk_mono = state.get(disk_coord)
            if disk_mono is None:
                continue
            if event.button_type == "s":
                disk_data = disk_mono.data or {}
                new_data = _snapshot_from_disk_region(state, disk_data)
                new_disk = clone_mono(disk_mono)
                assert new_disk is not None
                new_disk.data = new_data
                writes.append({disk_coord: new_disk})
            else:
                payload = disk_mono.data
                if payload is None or len(payload) == 0:
                    continue
                write: State = {}
                for coord, value in payload.items():
                    if value is None:
                        continue
                    write[coord] = clone_mono(value)
                if write:
                    writes.append(write)
    return writes


def run_event_cycle(prev_state: State, curr_state: State, static_state: StaticState) -> State:
    old_state = clone_state(prev_state) or {}
    now_state = clone_state(curr_state) or {}
    pending = collect_edge_events(old_state, now_state, static_state)
    while pending:
        writes = build_event_writes(now_state, pending, static_state)
        next_state = commit_writes(now_state, writes)
        pending = collect_edge_events(now_state, next_state, static_state)
        now_state = next_state
    return now_state
