from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.types import Coord, State
from src.view.level_select import compute_level_button_rects
from src.view.types import AppCtx, PreviewLayer

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
    offset_x: int = 0
    offset_y: int = 0


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


def build_viewport(surface: pygame.Surface, state: State, right_panel: int = 0) -> Viewport:
    w, h = surface.get_size()
    rect = pygame.Rect(8, 8, max(100, w - right_panel - 16), h - 16)
    min_x, min_y, max_x, max_y = _state_bounds(state)
    padding = 2
    world_w = max(1, (max_x - min_x + 1) + padding * 2)
    world_h = max(1, (max_y - min_y + 1) + padding * 2)
    cell = max(6, min(rect.width // world_w, rect.height // world_h))
    world_px_w = world_w * cell
    world_px_h = world_h * cell
    leftover_x = max(0, rect.width - world_px_w)
    leftover_y = max(0, rect.height - world_px_h)
    offset_x = leftover_x // 2
    offset_y = leftover_y // 2
    return Viewport(
        rect=rect,
        min_x=min_x,
        min_y=min_y,
        cell=cell,
        padding=padding,
        offset_x=offset_x,
        offset_y=offset_y,
    )


def world_to_screen(coord: Coord, vp: Viewport) -> pygame.Rect:
    x = vp.rect.x + vp.offset_x + (coord[0] - vp.min_x + vp.padding) * vp.cell
    y = vp.rect.y + vp.offset_y + (coord[1] - vp.min_y + vp.padding) * vp.cell
    return pygame.Rect(x, y, vp.cell, vp.cell)


def screen_to_world(pos: tuple[int, int], vp: Viewport) -> Coord | None:
    if not vp.rect.collidepoint(pos):
        return None
    gx = (pos[0] - (vp.rect.x + vp.offset_x)) // vp.cell + vp.min_x - vp.padding
    gy = (pos[1] - (vp.rect.y + vp.offset_y)) // vp.cell + vp.min_y - vp.padding
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


def _draw_buttons_under_objects(surface: pygame.Surface, ctx: AppCtx, vp: Viewport) -> None:
    if ctx.static_state is None:
        return
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


def _draw_preview_over_map(surface: pygame.Surface, preview_stack: list[PreviewLayer], vp: Viewport) -> None:
    for layer in preview_stack:
        mat_color = _scale_color(_base_color_by_index(layer.color), 0.35)
        expand = max(1, int(round(vp.cell * 0.2)))  # 0.1 grid per side
        for coord in layer.state.keys():
            base_rect = world_to_screen(coord, vp)
            material = base_rect.inflate(expand, expand)
            pygame.draw.rect(surface, mat_color, material)
        _draw_world(surface, layer.state, vp)
        # Explicit None in preview state should be rendered as '?'.
        q_color = _scale_color(_base_color_by_index(layer.color), 1.0)
        for coord, mono in layer.state.items():
            if mono is not None:
                continue
            rect = world_to_screen(coord, vp)
            _draw_question(surface, rect, q_color)


def _draw_question(surface: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int]) -> None:
    # Draw '?' as a tiny 7x9 bitmap.
    # Matches the requested shape:
    # 0000000
    # 0111110
    # 0100010
    # 0000010
    # 0001110
    # 0001000
    # 0000000
    # 0001000
    # 0000000
    rows = [
        "0000000",
        "0111110",
        "0100010",
        "0000010",
        "0001110",
        "0001000",
        "0000000",
        "0001000",
        "0000000",
    ]
    h = len(rows)
    w = len(rows[0]) if h else 0
    if w == 0 or h == 0:
        return

    px = max(1, rect.width // w)
    py = max(1, rect.height // h)
    total_w = w * px
    total_h = h * py
    ox = rect.x + (rect.width - total_w) // 2
    oy = rect.y + (rect.height - total_h) // 2
    pad_x = max(0, px // 5)
    pad_y = max(0, py // 5)
    cell_w = max(1, px - pad_x * 2)
    cell_h = max(1, py - pad_y * 2)

    for r in range(h):
        for c in range(w):
            if rows[r][c] != "1":
                continue
            x = ox + c * px + pad_x
            y = oy + r * py + pad_y
            pygame.draw.rect(surface, color, pygame.Rect(x, y, cell_w, cell_h))


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
    # 1) grid
    _draw_world(surface, {}, vp)
    # 2) SL buttons under objects
    _draw_buttons_under_objects(surface, ctx, vp)
    # 3) objects on top
    _draw_world(surface, ctx.runtime_state, vp)
    _draw_disk_region_overlay(surface, ctx.runtime_state, vp)
    _draw_preview_over_map(surface, ctx.preview_stack, vp)
    # 4) targets/eyes above objects
    _draw_overlay(surface, ctx, vp, font)

    y = 10
    for text in (
        "Q:back WASD/Arrows:move R:reset Z:undo H:solver",
        f"solver={ctx.solver_session.status} steps={ctx.solver_session.steps} searched={ctx.solver_session.searched_state_count} time={ctx.solver_session.elapsed_seconds:.3f}s",
        f"preview_depth={len(ctx.preview_stack)} history={len(ctx.history_stack)}",
    ):
        surface.blit(font.render(text, True, TXT), (12, y))
        y += 20
