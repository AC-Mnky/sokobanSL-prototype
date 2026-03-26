from __future__ import annotations

import pygame

from src.core_step import apply_action
from src.goals import is_goal
from src.state_utils import clone_state, is_empty_value
from src.types import Action
from src.view.level_select import export_builtin_and_refresh, try_enter_level_by_click
from src.view.preview import clear_preview, pop_preview, push_preview_if_data
from src.view.render import build_viewport, preview_screen_to_world, screen_to_world
from src.view.solver_session import start_or_restart_solver, stop_solver
from src.view.types import AppCtx


KEY_TO_ACTION: dict[int, Action] = {
    pygame.K_w: (0, -1),
    pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1),
    pygame.K_DOWN: (0, 1),
    pygame.K_a: (-1, 0),
    pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0),
    pygame.K_RIGHT: (1, 0),
}


def _refresh_level_cleared(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        ctx.level_cleared = False
        return
    ctx.level_cleared = is_goal(ctx.runtime_state, ctx.static_state)


def _apply_substantive_action(ctx: AppCtx, action: Action) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    ctx.history_stack.append(clone_state(ctx.runtime_state) or {})
    ctx.runtime_state = apply_action(ctx.runtime_state, action, ctx.static_state)
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)


def _reset_level(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.initial_state is None:
        return
    ctx.history_stack.append(clone_state(ctx.runtime_state) or {})
    ctx.runtime_state = clone_state(ctx.initial_state) or {}
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)


def _undo(ctx: AppCtx) -> None:
    if not ctx.history_stack:
        return
    ctx.runtime_state = ctx.history_stack.pop()
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)


def _handle_play_click(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> None:
    if ctx.runtime_state is None:
        return
    p_coord = preview_screen_to_world(pos, surface, ctx.preview_stack)
    if p_coord is not None and ctx.preview_stack:
        top = ctx.preview_stack[-1]
        if not push_preview_if_data(top, p_coord, ctx):
            pop_preview(ctx)
        return

    world_vp = build_viewport(surface, ctx.runtime_state)
    coord = screen_to_world(pos, world_vp)
    if coord is None:
        pop_preview(ctx)
        return
    if not push_preview_if_data(ctx.runtime_state, coord, ctx):
        pop_preview(ctx)


def handle_event(ctx: AppCtx, event: pygame.event.Event, surface: pygame.Surface) -> None:
    if event.type == pygame.QUIT:
        ctx.running = False
        return
    if event.type != pygame.KEYDOWN and event.type != pygame.MOUSEBUTTONDOWN:
        return
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        ctx.running = False
        return

    if ctx.mode == "select_level":
        if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            export_builtin_and_refresh(ctx)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            try_enter_level_by_click(ctx, event.pos, surface)
        return

    # playing
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_q:
            ctx.mode = "select_level"
            ctx.preview_stack.clear()
            ctx.level_cleared = False
            stop_solver(ctx)
            return
        if event.key in KEY_TO_ACTION:
            if ctx.level_cleared:
                return
            _apply_substantive_action(ctx, KEY_TO_ACTION[event.key])
            return
        if event.key == pygame.K_r:
            _reset_level(ctx)
            return
        if event.key == pygame.K_z:
            _undo(ctx)
            return
        if event.key == pygame.K_h:
            start_or_restart_solver(ctx)
            return
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        _handle_play_click(ctx, event.pos, surface)
