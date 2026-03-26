from __future__ import annotations

from src.state_utils import clone_state
from src.types import Coord, MonoData, State
from src.view.types import AppCtx, PreviewLayer


def clear_preview(ctx: AppCtx) -> None:
    ctx.preview_stack.clear()


def pop_preview(ctx: AppCtx) -> None:
    if ctx.preview_stack:
        ctx.preview_stack.pop()


def remove_preview_by_source(ctx: AppCtx, coord: Coord) -> bool:
    for i in range(len(ctx.preview_stack) - 1, -1, -1):
        if ctx.preview_stack[i].source_coord == coord:
            ctx.preview_stack.pop(i)
            return True
    return False


def resolve_visible_mono(ctx: AppCtx, coord: Coord) -> MonoData | None:
    for layer in reversed(ctx.preview_stack):
        mono = layer.state.get(coord)
        if mono is not None and (not mono.is_empty):
            return mono
    if ctx.runtime_state is None:
        return None
    mono = ctx.runtime_state.get(coord)
    if mono is None or mono.is_empty:
        return None
    return mono


def push_preview_if_data(state: State, coord: Coord, ctx: AppCtx) -> bool:
    mono = state.get(coord)
    if mono is None or mono.is_empty:
        return False
    if mono.data is None or len(mono.data) == 0:
        return False
    ctx.preview_stack.append(
        PreviewLayer(
            state=clone_state(mono.data) or {},
            color=mono.color,
            source_coord=coord,
        )
    )
    return True
