from src.goals import is_goal
from src.sample_levels import make_basic_levels
from src.solver_bfs import solve
from src.solver_link_overlay import build_solver_link_segments, controllable_coords_sorted
from src.types import MonoData, StaticState


def test_controllable_sorted_order():
    st = {(1, 0): None, (0, 0): MonoData(is_empty=False, is_wall=False, is_controllable=True, color=0, data=None)}
    assert controllable_coords_sorted(st) == ((0, 0),)


def test_single_player_overlay_edge_count_equals_solution_steps():
    lvl = make_basic_levels()[0]
    _, _, solution, *_ = list(solve(lvl.initial_state, lvl.static_state, is_goal))[-1]
    segs = build_solver_link_segments(lvl.initial_state, lvl.static_state, solution)
    assert len(segs) == len(solution)


def test_zero_length_solution_yields_empty_segments():
    static_state = StaticState(targets={}, buttons={})
    state = {(0, 0): MonoData(is_empty=False, is_wall=False, is_controllable=True, color=0, data=None)}
    assert build_solver_link_segments(state, static_state, tuple()) == []
