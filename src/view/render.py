from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.state_utils import add_coord
from src.types import Coord, MonoData, State
from src.view.level_select import compute_level_select_layout, level_select_scroll_max_y
from src.view.types import AppCtx, EditorPaletteItem, PreviewLayer

BG = (16, 18, 22)
BG_CLEARED = (22, 24, 30)
GRID = (40, 44, 52)
TXT = (220, 220, 220)
TXT_SOLVED = (90, 210, 120)
TXT_NO_SOLUTION = (235, 80, 80)
PANEL_BG = (26, 30, 38)
PANEL_LINE = (65, 70, 82)
EDITOR_RIGHT_PANEL = 280
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
            _draw_editor_icon(surface, rect, "wall", mono.color)
            _draw_reject_save_load_overlay(surface, rect, mono)
            continue
        if mono.is_controllable:
            _draw_editor_icon(surface, rect, "player", mono.color)
            _draw_reject_save_load_overlay(surface, rect, mono)
            continue
        if mono.data is not None:
            _draw_editor_icon(surface, rect, "disk", mono.color)
            _draw_reject_save_load_overlay(surface, rect, mono)
            continue
        _draw_editor_icon(surface, rect, "box", mono.color)
        _draw_reject_save_load_overlay(surface, rect, mono)


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
    # NOTE: pygame.draw.* on a SRCALPHA surface writes pixels (overwrites),
    # so drawing multiple semi-transparent rects onto the same surface will NOT
    # accumulate opacity as expected. To make overlapping disk regions stack,
    # we draw each disk into its own temporary surface, then alpha-blit it.
    alpha_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for disk_world, mono in state.items():
        if mono is None or mono.is_empty or mono.is_wall or mono.data is None:
            continue
        if len(mono.data) == 0:
            continue
        base = _base_color_by_index(mono.color)
        rgba = (base[0], base[1], base[2], 64)  # 25% opacity
        disk_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for rel in mono.data.keys():
            pygame.draw.rect(disk_surface, rgba, world_to_screen(add_coord(disk_world, rel), vp))
        alpha_surface.blit(disk_surface, (0, 0))
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


def _draw_reject_save_load_overlay(surface: pygame.Surface, rect: pygame.Rect, mono: MonoData) -> None:
    if mono.is_empty or (not mono.reject_save and not mono.reject_load):
        return
    pad = max(2, min(rect.w, rect.h) // 10)
    side = max(6, min(rect.w, rect.h) - 2 * pad)
    sq = pygame.Rect(0, 0, side, side)
    sq.centerx = rect.centerx
    sq.centery = rect.centery
    color = (248, 252, 255)
    stroke = max(1, min(sq.w, sq.h) // 8)
    if mono.reject_save and mono.reject_load:
        mid_x = sq.x + sq.w // 2
        left = pygame.Rect(sq.x, sq.y, mid_x - sq.x, sq.h)
        right = pygame.Rect(mid_x, sq.y, sq.right - mid_x, sq.h)
        _draw_button_glyph(surface, left, "S", color)
        _draw_button_glyph(surface, right, "L", color)
    elif mono.reject_save:
        _draw_button_glyph(surface, sq, "S", color)
    else:
        _draw_button_glyph(surface, sq, "L", color)
    # Slash: top-right to bottom-left (\)
    inset = max(1, stroke // 2)
    pygame.draw.line(
        surface,
        color,
        (sq.right - inset, sq.top + inset),
        (sq.left + inset, sq.bottom - inset),
        stroke,
    )


def _draw_preview_over_map(surface: pygame.Surface, preview_stack: list[PreviewLayer], vp: Viewport) -> None:
    for layer in preview_stack:
        mat_color = _scale_color(_base_color_by_index(layer.color), 0.35)
        expand = max(1, int(round(vp.cell * 0.2)))  # 0.1 grid per side
        for rel in layer.state.keys():
            base_rect = world_to_screen(add_coord(layer.anchor_world, rel), vp)
            material = base_rect.inflate(expand, expand)
            pygame.draw.rect(surface, mat_color, material)
        display_state = {add_coord(layer.anchor_world, rel): m for rel, m in layer.state.items()}
        _draw_world(surface, display_state, vp)
        # Explicit None in preview state should be rendered as '?'.
        q_color = _scale_color(_base_color_by_index(layer.color), 1.0)
        for rel, mono in layer.state.items():
            if mono is not None:
                continue
            rect = world_to_screen(add_coord(layer.anchor_world, rel), vp)
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


def _collect_editor_colors(ctx: AppCtx) -> list[int]:
    colors: set[int] = set()
    if ctx.runtime_state is not None:
        for mono in ctx.runtime_state.values():
            if mono is None or mono.is_empty:
                continue
            colors.add(max(1, mono.color))
    if ctx.static_state is not None:
        for target in ctx.static_state.targets.values():
            colors.add(max(1, target.required_color))
        for buttons in ctx.static_state.buttons.values():
            for b in buttons:
                colors.add(max(1, b.color))
    ordered = sorted(c for c in colors if c > 0)
    nxt = 1
    while nxt in colors:
        nxt += 1
    ordered.append(nxt)
    return ordered or [1]


def _draw_palette_item(surface: pygame.Surface, item: EditorPaletteItem, font: pygame.font.Font) -> None:
    if item.rect is None:
        return
    rect = item.rect
    pygame.draw.rect(surface, (44, 50, 62), rect)
    pygame.draw.rect(surface, PANEL_LINE, rect, 1)
    icon_size = max(14, min(rect.width - 10, rect.height - 24))
    icon = pygame.Rect(0, 0, icon_size, icon_size)
    icon.centerx = rect.centerx
    icon.top = rect.top + 5
    _draw_editor_icon(surface, icon, item.kind, item.color)
    label = font.render(item.label, True, TXT)
    label_x = rect.centerx - label.get_width() // 2
    surface.blit(label, (label_x, rect.bottom - 17))


def _build_editor_palette(ctx: AppCtx) -> list[EditorPaletteItem]:
    colors = _collect_editor_colors(ctx)
    items: list[EditorPaletteItem] = [
        EditorPaletteItem(key="air", label="Air", kind="air", color=0),
        EditorPaletteItem(key="wall", label="Wall", kind="wall", color=0),
        EditorPaletteItem(key="player", label="Player", kind="player", color=0),
        EditorPaletteItem(key="box", label="Box", kind="box", color=0),
    ]
    for c in colors:
        items.append(EditorPaletteItem(key=f"d_{c}", label=f"D c{c}", kind="disk", color=c))
        items.append(EditorPaletteItem(key=f"bt_{c}", label=f"BT c{c}", kind="box_target", color=c))
        items.append(EditorPaletteItem(key=f"s_{c}", label=f"S c{c}", kind="s_button", color=c))
        items.append(EditorPaletteItem(key=f"l_{c}", label=f"L c{c}", kind="l_button", color=c))
    items.append(EditorPaletteItem(key="target_player", label="PTarget", kind="player_target", color=0))
    items.append(EditorPaletteItem(key="target_box", label="BTarget", kind="box_target", color=0))
    return items


def _draw_editor_icon(
    surface: pygame.Surface,
    rect: pygame.Rect,
    kind: str,
    color_idx: int,
) -> None:
    color = _base_color_by_index(color_idx)
    if kind == "air":
        pygame.draw.rect(surface, (90, 95, 108), rect, 1)
    elif kind == "wall":
        pygame.draw.rect(surface, _scale_color(color, 0.45), rect)
    elif kind == "player":
        pygame.draw.rect(surface, color, rect)
        _draw_hollow_eyes(surface, rect)
    elif kind == "box":
        pygame.draw.rect(surface, _scale_color(color, 0.78), rect)
        pygame.draw.rect(surface, _scale_color(color, 0.58), rect, max(1, rect.width // 12))
    elif kind == "disk":
        pygame.draw.rect(surface, _scale_color(color, 0.92), rect)
        pygame.draw.rect(surface, _scale_color(color, 0.60), rect, max(1, rect.width // 10))
    elif kind == "s_button":
        _draw_button_glyph(surface, rect, "S", color)
    elif kind == "l_button":
        _draw_button_glyph(surface, rect, "L", color)
    elif kind == "player_target":
        pygame.draw.rect(surface, color, rect, 2)
        _draw_solid_eyes(surface, rect, color)
    elif kind == "box_target":
        pygame.draw.rect(surface, color, rect, 2)


def _draw_editor_panel(surface: pygame.Surface, ctx: AppCtx, font: pygame.font.Font, right_panel: int) -> None:
    panel = pygame.Rect(surface.get_width() - right_panel, 0, right_panel, surface.get_height())
    pygame.draw.rect(surface, PANEL_BG, panel)
    pygame.draw.line(surface, PANEL_LINE, (panel.left, panel.top), (panel.left, panel.bottom), 1)
    items = _build_editor_palette(ctx)
    margin = 10
    top = 40
    gap = 6
    cols = 2
    width = panel.width - margin * 2
    cell_w = (width - gap * (cols - 1)) // cols
    cell_h = 56
    rows = (len(items) + cols - 1) // cols
    content_h = top + max(0, rows * (cell_h + gap) - gap) + 10
    ctx.editor_panel_scroll_max = max(0, content_h - panel.height)
    ctx.editor_panel_scroll = max(0, min(ctx.editor_panel_scroll, ctx.editor_panel_scroll_max))
    for idx, item in enumerate(items):
        row = idx // cols
        col = idx % cols
        x = panel.left + margin + col * (cell_w + gap)
        y = top + row * (cell_h + gap) - ctx.editor_panel_scroll
        item.rect = pygame.Rect(x, y, cell_w, cell_h)
        if item.rect.bottom >= panel.top and item.rect.top <= panel.bottom:
            _draw_palette_item(surface, item, font)
    ctx.editor_palette_items = items
    title = font.render("Editor Palette", True, TXT)
    surface.blit(title, (panel.left + 10, 12))


def _draw_drag_preview(surface: pygame.Surface, ctx: AppCtx) -> None:
    payload = ctx.drag_session.payload
    if not ctx.editor_mode or payload is None:
        return
    if ctx.runtime_state is None:
        return
    vp = build_viewport(surface, ctx.runtime_state, right_panel=EDITOR_RIGHT_PANEL)
    mx, my = pygame.mouse.get_pos()
    center_x = mx + ctx.drag_session.drag_offset[0]
    center_y = my + ctx.drag_session.drag_offset[1]
    cell_px = max(6, vp.cell)

    if payload.kind == "selection":
        if payload.selection_size is None or payload.selection_press_rel is None:
            return
        if payload.selection_state is None or payload.selection_static is None:
            return

        x_len, y_len = payload.selection_size
        press_rel_x, press_rel_y = payload.selection_press_rel
        sel_w = x_len * cell_px
        sel_h = y_len * cell_px
        # Align the press cell center to the mouse-aligned center point.
        blit_x = int(center_x - (press_rel_x * cell_px + cell_px // 2))
        blit_y = int(center_y - (press_rel_y * cell_px + cell_px // 2))
        rect = pygame.Rect(blit_x, blit_y, sel_w, sel_h)

        preview = pygame.Surface((sel_w, sel_h), pygame.SRCALPHA)

        # 1) buttons under objects
        for rel, buttons in payload.selection_static.buttons.items():
            rx, ry = rel
            cell_rect = pygame.Rect(rx * cell_px, ry * cell_px, cell_px, cell_px)
            if not buttons:
                continue
            n = len(buttons)
            slot_w = max(1, cell_rect.width // n)
            total_w = slot_w * n
            start_x = cell_rect.x + (cell_rect.width - total_w) // 2
            for i, b in enumerate(buttons):
                slot = pygame.Rect(start_x + i * slot_w, cell_rect.y, slot_w, cell_rect.height)
                color = _scale_color(_base_color_by_index(b.color), 1.05)
                _draw_button_glyph(preview, slot, b.button_type.upper(), color)

        # 2) runtime icons
        for rx in range(x_len):
            for ry in range(y_len):
                local_rect = pygame.Rect(rx * cell_px, ry * cell_px, cell_px, cell_px)
                mono = payload.selection_state.get((rx, ry))
                if mono is None or mono.is_empty:
                    _draw_editor_icon(preview, local_rect, "air", 0)
                elif mono.is_wall:
                    _draw_editor_icon(preview, local_rect, "wall", mono.color)
                elif mono.is_controllable:
                    _draw_editor_icon(preview, local_rect, "player", mono.color)
                elif mono.data is not None:
                    _draw_editor_icon(preview, local_rect, "disk", mono.color)
                else:
                    _draw_editor_icon(preview, local_rect, "box", mono.color)
                if mono is not None and not mono.is_empty:
                    _draw_reject_save_load_overlay(preview, local_rect, mono)

        # 3) target overlays
        for rel, target in payload.selection_static.targets.items():
            rx, ry = rel
            cell_rect = pygame.Rect(rx * cell_px, ry * cell_px, cell_px, cell_px)
            t_color = _scale_color(_base_color_by_index(target.required_color), 1.05)
            pygame.draw.rect(preview, t_color, cell_rect, 2)
            if target.required_is_controllable:
                _draw_solid_eyes(preview, cell_rect, t_color)

        preview.set_alpha(128)
        surface.blit(preview, rect.topleft)
        return

    size = cell_px
    rect = pygame.Rect(center_x - size // 2, center_y - size // 2, size, size)
    preview = pygame.Surface((size, size), pygame.SRCALPHA)
    local_rect = pygame.Rect(0, 0, size, size)
    if payload.kind == "state" and payload.state_mono is not None:
        mono: MonoData = payload.state_mono
        if mono.is_empty:
            _draw_editor_icon(preview, local_rect, "air", mono.color)
        elif mono.is_wall:
            _draw_editor_icon(preview, local_rect, "wall", mono.color)
        elif mono.is_controllable:
            _draw_editor_icon(preview, local_rect, "player", mono.color)
        elif mono.data is not None:
            _draw_editor_icon(preview, local_rect, "disk", mono.color)
        else:
            _draw_editor_icon(preview, local_rect, "box", mono.color)
        if not mono.is_empty:
            _draw_reject_save_load_overlay(preview, local_rect, mono)
    elif payload.kind == "buttons" and payload.buttons:
        first = payload.buttons[0]
        _draw_editor_icon(preview, local_rect, "s_button" if first.button_type == "s" else "l_button", first.color)
    elif payload.kind == "target" and payload.target is not None:
        kind = "player_target" if payload.target.required_is_controllable else "box_target"
        _draw_editor_icon(preview, local_rect, kind, payload.target.required_color)
    elif payload.kind == "palette" and payload.palette_kind is not None:
        _draw_editor_icon(preview, local_rect, payload.palette_kind, payload.palette_color)
    preview.set_alpha(128)
    surface.blit(preview, rect.topleft)


def _draw_middle_selection(surface: pygame.Surface, ctx: AppCtx, vp: Viewport) -> None:
    if ctx.runtime_state is None:
        return

    # When dragging a whole selection (mouse left on selection),
    # show the hint box at the destination anchor and keep following.
    if (
        ctx.drag_session.active
        and ctx.drag_session.payload is not None
        and ctx.drag_session.payload.kind == "selection"
        and ctx.drag_session.payload.selection_size is not None
        and ctx.drag_session.payload.selection_press_rel is not None
    ):
        # Selection-drag hint should be continuous and exactly cover the drag preview.
        # The preview position uses mouse pixel coordinates + drag_offset (continuous),
        # while hover_coord is grid-snapped (discrete), so we must not base the hint on hover_coord.
        cell_px = max(6, vp.cell)
        x_len, y_len = ctx.drag_session.payload.selection_size
        press_rel_x, press_rel_y = ctx.drag_session.payload.selection_press_rel
        mx, my = pygame.mouse.get_pos()
        center_x = mx + ctx.drag_session.drag_offset[0]
        center_y = my + ctx.drag_session.drag_offset[1]

        sel_w = x_len * cell_px
        sel_h = y_len * cell_px
        blit_x = int(center_x - (press_rel_x * cell_px + cell_px // 2))
        blit_y = int(center_y - (press_rel_y * cell_px + cell_px // 2))
        if sel_w <= 0 or sel_h <= 0:
            return

        alpha = 64  # 25% opacity (=不透明度)
        box = pygame.Surface((sel_w, sel_h), pygame.SRCALPHA)
        box.fill((255, 255, 255, alpha))
        surface.blit(box, (blit_x, blit_y))
        return

    if ctx.middle_select_dragging and ctx.middle_select_press_coord is not None:
        p = ctx.middle_select_press_coord
        h = ctx.middle_select_hover_coord or p
        x0 = min(p[0], h[0])
        y0 = min(p[1], h[1])
        x1 = max(p[0], h[0])
        y1 = max(p[1], h[1])
    elif ctx.middle_select_anchor is not None and ctx.middle_select_size is not None:
        x0 = ctx.middle_select_anchor[0]
        y0 = ctx.middle_select_anchor[1]
        x1 = x0 + ctx.middle_select_size[0] - 1
        y1 = y0 + ctx.middle_select_size[1] - 1
    else:
        return

    rect0 = world_to_screen((x0, y0), vp)
    rect1 = world_to_screen((x1, y1), vp)
    screen_rect = pygame.Rect(rect0.x, rect0.y, rect1.right - rect0.x, rect1.bottom - rect0.y)
    if screen_rect.width <= 0 or screen_rect.height <= 0:
        return

    # 25% opacity white fill (=不透明度)
    alpha = 64  # 255 * 0.25
    box = pygame.Surface((screen_rect.width, screen_rect.height), pygame.SRCALPHA)
    box.fill((255, 255, 255, alpha))
    surface.blit(box, screen_rect.topleft)


def render_frame(surface: pygame.Surface, ctx: AppCtx, font: pygame.font.Font) -> None:
    surface.fill(BG_CLEARED if (ctx.mode == "playing" and ctx.level_cleared) else BG)
    if ctx.mode == "select_level":
        rects, chapter_titles, _bottom = compute_level_select_layout(
            len(ctx.levels),
            ctx.level_select_sections,
            surface,
        )
        mx = level_select_scroll_max_y(ctx, surface)
        ctx.level_select_scroll_y = min(ctx.level_select_scroll_y, mx)
        sy = ctx.level_select_scroll_y
        ctx.last_level_button_rects = [r.move(0, -sy) for r in rects]
        for title, ty in chapter_titles:
            surface.blit(font.render(title, True, TXT), (24, ty - sy))
        for i, rect in enumerate(rects):
            dr = rect.move(0, -sy)
            pygame.draw.rect(surface, (56, 62, 74), dr)
            pygame.draw.rect(surface, GRID, dr, 1)
            level_name = f"level_{i + 1:03d}"
            if i < len(ctx.level_names):
                level_name = ctx.level_names[i]
            txt = font.render(level_name, True, TXT)
            surface.blit(txt, (dr.x + 8, dr.y + 8))
        info = font.render("Select level | N: export builtin", True, TXT)
        surface.blit(info, (12, 8))
        return

    if ctx.runtime_state is None:
        return
    right_panel = EDITOR_RIGHT_PANEL if ctx.editor_mode else 0
    vp = build_viewport(surface, ctx.runtime_state, right_panel=right_panel)
    # 1) grid
    _draw_world(surface, {}, vp)
    # 2) SL buttons under objects
    _draw_buttons_under_objects(surface, ctx, vp)
    # 3) objects on top
    _draw_world(surface, ctx.runtime_state, vp)
    _draw_disk_region_overlay(surface, ctx.runtime_state, vp)
    # 4) targets/eyes above objects
    _draw_overlay(surface, ctx, vp, font)
    # 5) preview is above targets and blocks interaction below.
    _draw_preview_over_map(surface, ctx.preview_stack, vp)
    if ctx.editor_mode:
        _draw_editor_panel(surface, ctx, font, right_panel)
        _draw_drag_preview(surface, ctx)
        _draw_middle_selection(surface, ctx, vp)
    else:
        ctx.editor_palette_items = []

    solver_color = TXT
    if ctx.solver_session.status == "solved":
        solver_color = TXT_SOLVED
    elif ctx.solver_session.status == "no_solution":
        solver_color = TXT_NO_SOLUTION

    lines = [
        (
            "Esc/Q:back WASD:move(hold) R:reset Z:undo(hold) H:solver L:editor Ctrl+S(save) [/]:rejS/L(editor)",
            TXT,
        ),
        (
            f"solver={ctx.solver_session.status} steps={ctx.solver_session.steps} searched={ctx.solver_session.searched_state_count} time={ctx.solver_session.elapsed_seconds:.3f}s",
            solver_color,
        ),
        (f"editor={'on' if ctx.editor_mode else 'off'} preview_depth={len(ctx.preview_stack)} history={len(ctx.history_stack)}", TXT),
    ]
    y = 10
    for text, color in lines:
        surface.blit(font.render(text, True, color), (12, y))
        y += 20
    if ctx.level_saved:
        surface.blit(font.render("Level Saved", True, TXT), (12, y))
