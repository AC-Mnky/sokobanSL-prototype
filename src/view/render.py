from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.types import Coord, State
from src.view.level_select import compute_level_button_rects
from src.view.types import AppCtx

BG = (16, 18, 22)
BG_CLEARED = (22, 24, 30)
GRID = (40, 44, 52)
TXT = (220, 220, 220)
BASE_PALETTE: list[tuple[int, int, int]] = [
    (240, 240, 240),  # 0 white
    (235, 80, 80),    # 1 red
    (80, 140, 245),   # 2 blue
    (90, 210, 120),   # 3 green
    (245, 200, 80),   # 4 yellow
    (210, 90, 230),   # 5 magenta
    (80, 220, 220),   # 6 cyan
    (245, 150, 70),   # 7 orange
    (145, 100, 240),  # 8 purple
    (160, 235, 70),   # 9 lime
]


@dataclass(slots=True)
class Viewport:
    rect: pygame.Rect
    min_x: int
    min_y: int
    cell: int
    padding: int


def _base_color_by_index(idx: int) -> tuple[int, int, int]:
    i = int(idx)
    if i < 0:
        i = -i
    if i < len(BASE_PALETTE):
        return BASE_PALETTE[i]
    hue = (i * 137) % 360
    c = pygame.Color(0, 0, 0)
    c.hsva = (hue, 100, 100, 100)
    return (c.r, c.g, c.b)


def _scale_color(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (
        max(0, min(255, int(rgb[0] * factor))),
        max(0, min(255, int(rgb[1] * factor))),
        max(0, min(255, int(rgb[2] * factor))),
    )


def _draw_hollow_eyes(surface: pygame.Surface, rect: pygame.Rect) -> None:
    eye_w = max(1, rect.width // 6)
    eye_h = max(2, rect.height // 3)
    eye_y = rect.y + rect.height // 4
    left_x = rect.x + rect.width // 4 - eye_w // 2
    right_x = rect.x + (rect.width * 3) // 4 - eye_w // 2
    pygame.draw.rect(surface, BG, pygame.Rect(left_x, eye_y, eye_w, eye_h))
    pygame.draw.rect(surface, BG, pygame.Rect(right_x, eye_y, eye_w, eye_h))


def _draw_solid_eyes(surface: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int]) -> None:
    eye_w = max(1, rect.width // 6)
    eye_h = max(2, rect.height // 3)
    eye_y = rect.y + rect.height // 4
    left_x = rect.x + rect.width // 4 - eye_w // 2
    right_x = rect.x + (rect.width * 3) // 4 - eye_w // 2
    pygame.draw.rect(surface, color, pygame.Rect(left_x, eye_y, eye_w, eye_h))
    pygame.draw.rect(surface, color, pygame.Rect(right_x, eye_y, eye_w, eye_h))


def _state_bounds(state: State) -> tuple[int, int, int, int]:
    if not state:
        return (0, 0, 1, 1)
    xs = [c[0] for c in state.keys()]
    ys = [c[1] for c in state.keys()]
    return (min(xs), min(ys), max(xs), max(ys))


def build_viewport(surface: pygame.Surface, state: State, right_panel: int = 260) -> Viewport:
    w, h = surface.get_size()
    rect = pygame.Rect(8, 8, max(100, w - right_panel - 16), h - 16)
    min_x, min_y, max_x, max_y = _state_bounds(state)
    padding = 2
    world_w = max(1, (max_x - min_x + 1) + padding * 2)
    world_h = max(1, (max_y - min_y + 1) + padding * 2)
    cell = max(6, min(rect.width // world_w, rect.height // world_h))
    return Viewport(rect=rect, min_x=min_x, min_y=min_y, cell=cell, padding=padding)


def world_to_screen(coord: Coord, vp: Viewport) -> pygame.Rect:
    x = vp.rect.x + (coord[0] - vp.min_x + vp.padding) * vp.cell
    y = vp.rect.y + (coord[1] - vp.min_y + vp.padding) * vp.cell
    return pygame.Rect(x, y, vp.cell, vp.cell)


def screen_to_world(pos: tuple[int, int], vp: Viewport) -> Coord | None:
    if not vp.rect.collidepoint(pos):
        return None
    gx = (pos[0] - vp.rect.x) // vp.cell + vp.min_x - vp.padding
    gy = (pos[1] - vp.rect.y) // vp.cell + vp.min_y - vp.padding
    return (int(gx), int(gy))


def _draw_world(surface: pygame.Surface, state: State, vp: Viewport) -> None:
    pygame.draw.rect(surface, GRID, vp.rect, 1)
    for coord, mono in state.items():
        rect = world_to_screen(coord, vp)
        if mono is None:
            pygame.draw.rect(surface, (28, 32, 38), rect, 1)
            continue
        if mono.is_empty:
            pygame.draw.rect(surface, (28, 32, 38), rect, 1)
            continue
        base = _base_color_by_index(mono.color)
        if mono.is_wall:
            color = _scale_color(base, 0.45)
        elif mono.is_controllable:
            color = _scale_color(base, 1.00)
        elif mono.data is not None:
            color = _scale_color(base, 0.92)
        else:
            color = _scale_color(base, 0.78)
        pygame.draw.rect(surface, color, rect)
        if mono.is_controllable:
            _draw_hollow_eyes(surface, rect)


def _draw_disk_region_overlay(surface: pygame.Surface, state: State, vp: Viewport) -> None:
    alpha_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for mono in state.values():
        if mono is None or mono.is_empty or mono.is_wall or mono.data is None:
            continue
        if len(mono.data) == 0:
            continue
        base = _base_color_by_index(mono.color)
        rgba = (base[0], base[1], base[2], 64)  # 25% opacity
        for coord in mono.data.keys():
            pygame.draw.rect(alpha_surface, rgba, world_to_screen(coord, vp))
    surface.blit(alpha_surface, (0, 0))


def _draw_overlay(surface: pygame.Surface, ctx: AppCtx, vp: Viewport, font: pygame.font.Font) -> None:
    if ctx.static_state is None:
        return
    for coord, target in ctx.static_state.targets.items():
        rect = world_to_screen(coord, vp)
        t_color = _scale_color(_base_color_by_index(target.required_color), 1.05)
        pygame.draw.rect(surface, t_color, rect, 2)
        if target.required_is_controllable:
            _draw_solid_eyes(surface, rect, t_color)
    for coord, buttons in ctx.static_state.buttons.items():
        rect = world_to_screen(coord, vp)
        if not buttons:
            continue
        n = len(buttons)
        slot_w = max(1, rect.width // n)
        total_w = slot_w * n
        start_x = rect.x + (rect.width - total_w) // 2
        for i, b in enumerate(buttons):
            slot = pygame.Rect(start_x + i * slot_w, rect.y, slot_w, rect.height)
            color = _scale_color(_base_color_by_index(b.color), 1.05)
            _draw_button_glyph(surface, slot, b.button_type.upper(), color)


def _draw_button_glyph(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    color: tuple[int, int, int],
) -> None:
    # Geometry-based glyphs to guarantee visual centering.
    margin_x = max(2, rect.width // 4)
    margin_y = max(2, rect.height // 4)
    x0 = rect.x + margin_x
    x1 = rect.right - margin_x
    y0 = rect.y + margin_y
    y1 = rect.bottom - margin_y
    ym = (y0 + y1) // 2
    stroke = max(1, min(rect.width, rect.height) // 10)

    if label == "L":
        pygame.draw.line(surface, color, (x0, y0), (x0, y1), stroke)
        pygame.draw.line(surface, color, (x0, y1), (x1, y1), stroke)
        return

    # Default "S"
    pygame.draw.line(surface, color, (x1, y0), (x0, y0), stroke)
    pygame.draw.line(surface, color, (x0, y0), (x0, ym), stroke)
    pygame.draw.line(surface, color, (x0, ym), (x1, ym), stroke)
    pygame.draw.line(surface, color, (x1, ym), (x1, y1), stroke)
    pygame.draw.line(surface, color, (x1, y1), (x0, y1), stroke)


def preview_panel_rect(surface: pygame.Surface) -> pygame.Rect:
    w, h = surface.get_size()
    return pygame.Rect(w - 244, 8, 236, h - 16)


def _draw_preview(surface: pygame.Surface, preview_stack: list[State]) -> None:
    panel = preview_panel_rect(surface)
    pygame.draw.rect(surface, (24, 26, 34), panel)
    pygame.draw.rect(surface, GRID, panel, 1)
    if not preview_stack:
        return
    top = preview_stack[-1]
    sub = surface.subsurface(panel)
    vp = build_viewport(sub, top, right_panel=0)
    _draw_world(sub, top, vp)


def preview_screen_to_world(pos: tuple[int, int], surface: pygame.Surface, preview_stack: list[State]) -> Coord | None:
    panel = preview_panel_rect(surface)
    if not panel.collidepoint(pos):
        return None
    if not preview_stack:
        return None
    local = (pos[0] - panel.x, pos[1] - panel.y)
    fake = pygame.Surface((panel.width, panel.height))
    vp = build_viewport(fake, preview_stack[-1], right_panel=0)
    return screen_to_world(local, vp)


def render_frame(surface: pygame.Surface, ctx: AppCtx, font: pygame.font.Font) -> None:
    surface.fill(BG_CLEARED if (ctx.mode == "playing" and ctx.level_cleared) else BG)
    if ctx.mode == "select_level":
        rects = compute_level_button_rects(len(ctx.levels), surface)
        ctx.last_level_button_rects = rects
        for i, rect in enumerate(rects):
            pygame.draw.rect(surface, (56, 62, 74), rect)
            pygame.draw.rect(surface, GRID, rect, 1)
            txt = font.render(f"Level {i}", True, TXT)
            surface.blit(txt, (rect.x + 8, rect.y + 8))
        info = font.render("Select level | N: export builtin", True, TXT)
        surface.blit(info, (12, 8))
        return

    if ctx.runtime_state is None:
        return
    vp = build_viewport(surface, ctx.runtime_state)
    _draw_world(surface, ctx.runtime_state, vp)
    _draw_disk_region_overlay(surface, ctx.runtime_state, vp)
    _draw_overlay(surface, ctx, vp, font)
    _draw_preview(surface, ctx.preview_stack)

    y = 10
    for text in (
        "Q:back WASD/Arrows:move R:reset Z:undo H:solver",
        f"solver={ctx.solver_session.status} steps={ctx.solver_session.steps} searched={ctx.solver_session.searched_state_count}",
        f"preview_depth={len(ctx.preview_stack)} history={len(ctx.history_stack)}",
    ):
        surface.blit(font.render(text, True, TXT), (12, y))
        y += 20
