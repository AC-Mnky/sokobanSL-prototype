from __future__ import annotations

import os
import sys
import pygame

from src.view.input_router import handle_event, tick_cleared_auto_advance, tick_move_repeat, tick_undo_z_repeat
from src.view.level_select import refresh_levels
from src.view.render import render_frame
from src.view.solver_session import advance_solver_once
from src.view.types import AppCtx

SELECT_LEVEL_REFRESH_MS = 1000
FONT_SIZE = 16


def _build_ui_font() -> pygame.font.Font:
    # Prefer CJK-capable fonts so level names can display Chinese.
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, FONT_SIZE)
    return pygame.font.Font(None, FONT_SIZE)


def _windows_detach_ime_from_window() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        info = pygame.display.get_wm_info()
        hwnd = info.get("window")
        if not hwnd:
            return
        imm32 = ctypes.WinDLL("imm32", use_last_error=True)
        ImmAssociateContext = imm32.ImmAssociateContext
        ImmAssociateContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        ImmAssociateContext.restype = wintypes.HANDLE
        ImmAssociateContext(hwnd, None)
    except Exception:
        pass


def run_app(ctx: AppCtx) -> None:
    # Reduces IME capturing keys before SDL inits (pygame-ce / SDL2).
    os.environ.setdefault("SDL_IME_INTERNAL_EDITING", "0")
    pygame.init()
    pygame.font.init()
    surface = pygame.display.set_mode((1280, 720))
    pygame.key.stop_text_input()
    _windows_detach_ime_from_window()
    pygame.display.set_caption("NOSL Sokoban")
    clock = pygame.time.Clock()
    font = _build_ui_font()

    refresh_levels(ctx)
    next_select_refresh_at = pygame.time.get_ticks() + SELECT_LEVEL_REFRESH_MS

    while ctx.running:
        moved_this_frame = False
        for event in pygame.event.get():
            moved_this_frame = handle_event(ctx, event, surface) or moved_this_frame
        if ctx.mode == "playing":
            tick_cleared_auto_advance(ctx)
            moved_this_frame = tick_undo_z_repeat(ctx) or moved_this_frame
            moved_this_frame = tick_move_repeat(ctx) or moved_this_frame

        now = pygame.time.get_ticks()
        if ctx.mode == "select_level" and now >= next_select_refresh_at:
            refresh_levels(ctx)
            next_select_refresh_at = now + SELECT_LEVEL_REFRESH_MS
        elif ctx.mode != "select_level":
            next_select_refresh_at = now + SELECT_LEVEL_REFRESH_MS

        if ctx.mode == "playing" and not moved_this_frame:
            advance_solver_once(ctx)

        render_frame(surface, ctx, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
