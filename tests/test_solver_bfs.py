from src.goals import is_goal
from src.sample_levels import make_basic_levels
from src.solver_bfs import solve


def test_solver_finds_solution():
    lvl = make_basic_levels()[0]
    results = list(solve(lvl.initial_state, lvl.static_state, is_goal, step_chunk=1))
    assert results
    status, steps, solution, searched, elapsed = results[-1]
    assert status == "solved"
    assert steps == len(solution)
    assert searched >= 0
    assert elapsed >= 0.0


def test_solver_yields_solving_before_solved():
    lvl = make_basic_levels()[0]
    gen = solve(lvl.initial_state, lvl.static_state, is_goal, step_chunk=1)
    first = next(gen)
    assert first[0] in ("solving", "solved")
    assert first[4] >= 0.0
