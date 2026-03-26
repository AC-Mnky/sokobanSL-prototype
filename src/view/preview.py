from __future__ import annotations

from src.state_utils import clone_state
from src.types import Coord, State
from src.view.types import AppCtx


def clear_preview(ctx: AppCtx) -> None:
    ctx.preview_stack.clear()


def pop_preview(ctx: AppCtx) -> None:
    if ctx.preview_stack:
        ctx.preview_stack.pop()


def push_preview_if_data(state: State, coord: Coord, ctx: AppCtx) -> bool:
    mono = state.get(coord)
    if mono is None or mono.is_empty:
        return False
    if mono.data is None or len(mono.data) == 0:
        return False
    ctx.preview_stack.append(clone_state(mono.data) or {})
    return True
