from __future__ import annotations

import pygame

from src.view.input_router import handle_event
from src.view.level_select import refresh_levels
from src.view.render import render_frame
from src.view.solver_session import advance_solver_once
from src.view.types import AppCtx


def run_app(ctx: AppCtx) -> None:
    pygame.init()
    pygame.font.init()
    surface = pygame.display.set_mode((1280, 720))
    pygame.display.set_caption("NOSL Sokoban")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 16)

    refresh_levels(ctx)

    while ctx.running:
        moved_this_frame = False
        for event in pygame.event.get():
            moved_this_frame = handle_event(ctx, event, surface) or moved_this_frame

        if ctx.mode == "playing" and not moved_this_frame:
            advance_solver_once(ctx)

        render_frame(surface, ctx, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
