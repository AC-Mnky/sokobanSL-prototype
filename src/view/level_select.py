from __future__ import annotations

import math

import pygame

from src.goals import is_goal
from src.level_io import export_builtin_levels, load_levels_with_names_and_sections
from src.state_utils import clone_state, clone_static_state
from src.view.types import AppCtx

SELECT_LEVEL_SCROLL_STEP = 40


def refresh_levels(ctx: AppCtx, *, reset_scroll: bool | None = None) -> None:
    prev_names = tuple(ctx.level_names)
    entries, sections, hard = load_levels_with_names_and_sections(ctx.levels_path)
    ctx.level_names = [name for name, _ in entries]
    ctx.levels = [level for _, level in entries]
    n = len(ctx.levels)
    total = sum(c for _, c in sections)
    ctx.level_select_sections = sections if n > 0 and total == n else ([(None, n)] if n else [])
    ctx.level_select_hard = hard if n > 0 and len(hard) == n else ([False] * n if n else [])
    if reset_scroll is True:
        ctx.level_select_scroll_y = 0
    elif reset_scroll is False:
        pass
    else:
        if tuple(ctx.level_names) != prev_names:
            ctx.level_select_scroll_y = 0


def export_builtin_and_refresh(ctx: AppCtx) -> None:
    export_builtin_levels(ctx.levels_path)
    refresh_levels(ctx, reset_scroll=True)


def compute_level_select_layout(
    count: int,
    sections: list[tuple[str | None, int]],
    surface: pygame.Surface,
    *,
    top_y: int = 32,
    margin: int = 24,
    gap: int = 12,
    section_gap: int = 16,
    title_h: int = 20,
    title_gap_below: int = 6,
) -> tuple[list[pygame.Rect], list[tuple[str, int]], int]:
    """Button rects, chapter titles (text, y), and content bottom y (for scroll range)."""
    w, _h = surface.get_size()
    if count <= 0:
        return [], [], top_y
    cols = max(1, min(6, int(math.sqrt(count)) + 1))
    btn_rows = sum(math.ceil(c / cols) if c > 0 else 0 for _, c in sections)
    btn_rows = max(1, btn_rows)
    button_w = max(80, (w - margin * 2 - gap * (cols - 1)) // cols)
    button_h = max(50, min(80, (_h - margin * 2 - gap * (btn_rows - 1)) // max(1, btn_rows)))
    rects: list[pygame.Rect] = []
    titles: list[tuple[str, int]] = []
    y = float(top_y)
    for si, (title, sec_count) in enumerate(sections):
        if title:
            titles.append((title, int(y)))
            y += title_h + title_gap_below
        if sec_count <= 0:
            y += section_gap * 0.5
            continue
        col = 0
        row = 0
        for _ in range(sec_count):
            x = margin + col * (button_w + gap)
            yy = int(y + row * (button_h + gap))
            rects.append(pygame.Rect(x, yy, button_w, button_h))
            col += 1
            if col >= cols:
                col = 0
                row += 1
        rows_used = math.ceil(sec_count / cols)
        y += rows_used * (button_h + gap)
        if si < len(sections) - 1:
            y += section_gap
    bottom = int(y)
    if rects:
        bottom = max(bottom, max(r.bottom for r in rects))
    if titles:
        bottom = max(bottom, max(ty + title_h for _, ty in titles))
    return rects, titles, bottom


def level_select_scroll_max_y(ctx: AppCtx, surface: pygame.Surface) -> int:
    *_, content_bottom = compute_level_select_layout(
        len(ctx.levels),
        ctx.level_select_sections,
        surface,
    )
    return max(0, content_bottom - surface.get_height() + 24)


def apply_level_select_wheel(ctx: AppCtx, surface: pygame.Surface, wheel_y: int) -> None:
    mx = level_select_scroll_max_y(ctx, surface)
    ctx.level_select_scroll_y = max(
        0,
        min(mx, ctx.level_select_scroll_y - wheel_y * SELECT_LEVEL_SCROLL_STEP),
    )


def try_enter_level_by_click(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    rects, _titles, _bottom = compute_level_select_layout(
        len(ctx.levels),
        ctx.level_select_sections,
        surface,
    )
    sy = ctx.level_select_scroll_y
    ctx.last_level_button_rects = [r.move(0, -sy) for r in rects]
    for i, rect in enumerate(rects):
        if ctx.last_level_button_rects[i].collidepoint(pos):
            lvl = ctx.levels[i]
            ctx.current_level_idx = i
            ctx.level_saved = False
            ctx.static_state = clone_static_state(lvl.static_state)
            ctx.initial_state = clone_state(lvl.initial_state) or {}
            ctx.runtime_state = clone_state(lvl.initial_state) or {}
            ctx.history_stack.clear()
            ctx.preview_stack.clear()
            ctx.editor_mode = False
            ctx.level_cleared = is_goal(ctx.runtime_state, ctx.static_state)
            ctx.solver_session = type(ctx.solver_session)()
            ctx.solver_link_segments = None
            ctx.mode = "playing"
            return True
    return False
