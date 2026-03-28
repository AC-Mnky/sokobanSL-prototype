from __future__ import annotations

from src.state_utils import add_coord, clone_state, sub_coord
from src.types import Coord, MonoData, State
from src.view.types import AppCtx, PreviewLayer


def clear_preview(ctx: AppCtx) -> None:
    ctx.preview_stack.clear()


def pop_preview(ctx: AppCtx) -> None:
    if ctx.preview_stack:
        ctx.preview_stack.pop()


def remove_preview_by_source(ctx: AppCtx, coord: Coord, source_container_id: int) -> bool:
    for i in range(len(ctx.preview_stack) - 1, -1, -1):
        layer = ctx.preview_stack[i]
        if layer.source_coord == coord and layer.source_container_id == source_container_id:
            ctx.preview_stack.pop(i)
            return True
    return False


def resolve_visible_mono(ctx: AppCtx, coord: Coord) -> MonoData | None:
    for layer in reversed(ctx.preview_stack):
        rel = sub_coord(coord, layer.anchor_world)
        mono = layer.state.get(rel)
        if mono is not None and (not mono.is_empty):
            return mono
    if ctx.runtime_state is None:
        return None
    mono = ctx.runtime_state.get(coord)
    if mono is None or mono.is_empty:
        return None
    return mono


def push_preview_if_data(mono: MonoData | None, coord: Coord, source_container_id: int, ctx: AppCtx) -> bool:
    if remove_preview_by_source(ctx, coord, source_container_id):
        return True
    if mono is None or mono.is_empty:
        return False
    if mono.data is None or len(mono.data) == 0:
        return False
    if ctx.runtime_state is not None and source_container_id == id(ctx.runtime_state):
        anchor_world = coord
    else:
        anchor_world = coord
        for parent in ctx.preview_stack:
            if id(parent.state) == source_container_id:
                anchor_world = add_coord(parent.anchor_world, coord)
                break
    ctx.preview_stack.append(
        PreviewLayer(
            state=clone_state(mono.data) or {},
            color=mono.color,
            source_coord=coord,
            anchor_world=anchor_world,
            source_container_id=source_container_id,
        )
    )
    return True
