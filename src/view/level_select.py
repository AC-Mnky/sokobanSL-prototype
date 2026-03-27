from __future__ import annotations

import math

import pygame

from src.goals import is_goal
from src.level_io import export_builtin_levels, load_levels
from src.state_utils import clone_state, clone_static_state
from src.view.types import AppCtx


def refresh_levels(ctx: AppCtx) -> None:
    ctx.levels = load_levels(ctx.levels_path)


def export_builtin_and_refresh(ctx: AppCtx) -> None:
    export_builtin_levels(ctx.levels_path)
    refresh_levels(ctx)


def compute_level_button_rects(count: int, surface: pygame.Surface) -> list[pygame.Rect]:
    w, h = surface.get_size()
    if count <= 0:
        return []
    cols = max(1, min(6, int(math.sqrt(count)) + 1))
    rows = math.ceil(count / cols)
    margin = 24
    gap = 12
    button_w = max(80, (w - margin * 2 - gap * (cols - 1)) // cols)
    button_h = max(50, min(80, (h - margin * 2 - gap * (rows - 1)) // max(1, rows)))
    rects: list[pygame.Rect] = []
    for idx in range(count):
        r = idx // cols
        c = idx % cols
        x = margin + c * (button_w + gap)
        y = margin + r * (button_h + gap)
        rects.append(pygame.Rect(x, y, button_w, button_h))
    return rects


def try_enter_level_by_click(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    rects = compute_level_button_rects(len(ctx.levels), surface)
    ctx.last_level_button_rects = rects
    for i, rect in enumerate(rects):
        if rect.collidepoint(pos):
            lvl = ctx.levels[i]
            ctx.current_level_idx = i
            ctx.static_state = clone_static_state(lvl.static_state)
            ctx.initial_state = clone_state(lvl.initial_state) or {}
            ctx.runtime_state = clone_state(lvl.initial_state) or {}
            ctx.history_stack.clear()
            ctx.preview_stack.clear()
            ctx.editor_mode = False
            ctx.level_cleared = is_goal(ctx.runtime_state, ctx.static_state)
            ctx.solver_session = type(ctx.solver_session)()
            ctx.mode = "playing"
            return True
    return False
