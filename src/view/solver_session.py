from __future__ import annotations

from src.goals import is_goal
from src.solver_bfs import solve
from src.state_utils import clone_state
from src.view.types import AppCtx


def stop_solver(ctx: AppCtx) -> None:
    ctx.solver_session.status = "idle"
    ctx.solver_session.generator = None
    ctx.solver_session.elapsed_seconds = 0.0


def start_or_restart_solver(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    ctx.solver_session.generator = solve(
        clone_state(ctx.runtime_state) or {},
        ctx.static_state,
        is_goal,
        step_chunk=256,
    )
    ctx.solver_session.status = "running"
    ctx.solver_session.steps = 0
    ctx.solver_session.solution = tuple()
    ctx.solver_session.searched_state_count = 0
    ctx.solver_session.elapsed_seconds = 0.0


def advance_solver_once(ctx: AppCtx) -> None:
    if ctx.solver_session.status != "running" or ctx.solver_session.generator is None:
        return
    try:
        status, steps, solution, searched, elapsed = next(ctx.solver_session.generator)
    except StopIteration:
        ctx.solver_session.status = "idle"
        ctx.solver_session.generator = None
        return
    ctx.solver_session.steps = steps
    ctx.solver_session.solution = solution
    ctx.solver_session.searched_state_count = searched
    ctx.solver_session.elapsed_seconds = elapsed
    if status in ("solved", "no solution"):
        normalized = "no_solution" if status == "no solution" else status
        ctx.solver_session.status = normalized
        ctx.solver_session.generator = None
