from __future__ import annotations

import pygame

from src.core_step import apply_action
from src.goals import is_goal
from src.level_io import save_level_by_index
from src.state_utils import (
    air_mono,
    clone_mono,
    clone_state,
    clone_static_state,
    is_solid_value,
    mono_deep_equal,
    sub_coord,
)
from src.types import Action, ButtonData, Level, MonoData, StaticState, TargetData
from src.view.level_select import export_builtin_and_refresh, refresh_levels, try_enter_level_by_click
from src.view.preview import clear_preview, pop_preview, push_preview_if_data, resolve_visible_mono
from src.view.render import EDITOR_RIGHT_PANEL, build_viewport, screen_to_world, world_to_screen
from src.view.solver_session import start_or_restart_solver, stop_solver
from src.view.types import AppCtx, DragPayload, DragSession


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
EDITOR_SCROLL_STEP = 36
KEY_REPEAT_DELAY_MS = 200
KEY_REPEAT_INTERVAL_MS = 100
UNDO_Z_REPEAT_DELAY_MS = KEY_REPEAT_DELAY_MS
UNDO_Z_REPEAT_INTERVAL_MS = KEY_REPEAT_INTERVAL_MS
MOVE_REPEAT_DELAY_MS = KEY_REPEAT_DELAY_MS
MOVE_REPEAT_INTERVAL_MS = KEY_REPEAT_INTERVAL_MS


def _cancel_middle_selection(ctx: AppCtx) -> None:
    ctx.middle_select_dragging = False
    ctx.middle_select_press_coord = None
    ctx.middle_select_hover_coord = None
    ctx.middle_select_anchor = None
    ctx.middle_select_size = None


def _get_committed_selection_bounds(ctx: AppCtx) -> tuple[int, int, int, int] | None:
    if ctx.middle_select_anchor is None or ctx.middle_select_size is None:
        return None
    x0 = ctx.middle_select_anchor[0]
    y0 = ctx.middle_select_anchor[1]
    x1 = x0 + ctx.middle_select_size[0] - 1
    y1 = y0 + ctx.middle_select_size[1] - 1
    return x0, y0, x1, y1


def _iter_rect_coords(x0: int, y0: int, x1: int, y1: int):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield (x, y)


def _save_committed_selection_to_clipboard(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    if ctx.middle_select_anchor is None or ctx.middle_select_size is None:
        return
    x0, y0 = ctx.middle_select_anchor
    x_len, y_len = ctx.middle_select_size
    state_sub = {}
    for coord in _iter_rect_coords(x0, y0, x0 + x_len - 1, y0 + y_len - 1):
        # Must distinguish "missing key" vs "key exists with None".
        if coord not in ctx.runtime_state:
            continue
        rel = (coord[0] - x0, coord[1] - y0)
        state_sub[rel] = clone_mono(ctx.runtime_state.get(coord))
    targets_sub = {}
    buttons_sub = {}
    for coord in _iter_rect_coords(x0, y0, x0 + x_len - 1, y0 + y_len - 1):
        rel = (coord[0] - x0, coord[1] - y0)
        if coord in ctx.static_state.targets:
            t = ctx.static_state.targets[coord]
            targets_sub[rel] = TargetData(required_is_controllable=t.required_is_controllable, required_color=t.required_color)
        if coord in ctx.static_state.buttons:
            moved = ctx.static_state.buttons[coord]
            buttons_sub[rel] = [ButtonData(button_type=b.button_type, color=b.color) for b in moved]

    key = (x_len, y_len)
    ctx.clipboard[key] = (state_sub, StaticState(targets=targets_sub, buttons=buttons_sub))
    ctx.clipboard_last_key = key


def _apply_clipboard_to_selection(ctx: AppCtx, key: tuple[int, int]) -> bool:
    if ctx.runtime_state is None or ctx.static_state is None:
        return False
    if ctx.middle_select_anchor is None or ctx.middle_select_size is None:
        return False
    if key not in ctx.clipboard:
        return False
    if key != ctx.middle_select_size:
        return False

    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state

    x0, y0 = ctx.middle_select_anchor
    x_len, y_len = key
    clip_state, clip_static = ctx.clipboard[key]

    changed = False

    # Ctrl+V runtime state: only cover coords where clipboard `state` has key
    # AND clipboard value is not None. Missing keys / explicit None => no-op.
    for coord in _iter_rect_coords(x0, y0, x0 + x_len - 1, y0 + y_len - 1):
        rel = (coord[0] - x0, coord[1] - y0)
        if rel not in clip_state:
            continue
        clip_mono = clip_state[rel]
        if clip_mono is None:
            continue
        cur_mono = ctx.runtime_state.get(coord)
        if not mono_deep_equal(cur_mono, clip_mono):
            ctx.runtime_state[coord] = clone_mono(clip_mono)
            changed = True

    # Ctrl+V static state: overwrite selection area (clear then apply clipboard).
    # Note: The new "skip None/missing" rule only applies to runtime `state`.
    for coord in _iter_rect_coords(x0, y0, x0 + x_len - 1, y0 + y_len - 1):
        if coord in ctx.static_state.buttons:
            del ctx.static_state.buttons[coord]
            changed = True
        if coord in ctx.static_state.targets:
            del ctx.static_state.targets[coord]
            changed = True

    for rel, target in clip_static.targets.items():
        abs_coord = (rel[0] + x0, rel[1] + y0)
        ctx.static_state.targets[abs_coord] = TargetData(
            required_is_controllable=target.required_is_controllable,
            required_color=target.required_color,
        )
        changed = True
    for rel, buttons in clip_static.buttons.items():
        abs_coord = (rel[0] + x0, rel[1] + y0)
        ctx.static_state.buttons[abs_coord] = [ButtonData(button_type=b.button_type, color=b.color) for b in buttons]
        changed = True

    if not changed:
        return False

    _clear_level_saved(ctx)
    ctx.history_stack.append((old_state, old_static))
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    return True


def _clear_committed_selection(ctx: AppCtx) -> bool:
    """
    Delete semantics (runtime):
    - If selection contains no solid cells => remove all state entries in the selection.
    - Else => convert all solid cells to air_mono(); keep others (None/empty) unchanged.
    Static state: always clear within selection.
    """
    if ctx.runtime_state is None or ctx.static_state is None:
        return False
    if ctx.middle_select_anchor is None or ctx.middle_select_size is None:
        return False

    bounds = _get_committed_selection_bounds(ctx)
    if bounds is None:
        return False
    x0, y0, x1, y1 = bounds
    x_len = x1 - x0 + 1
    y_len = y1 - y0 + 1
    _ = (x_len, y_len)

    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state

    has_solid = False
    for coord in _iter_rect_coords(x0, y0, x1, y1):
        if coord not in ctx.runtime_state:
            continue
        mono = ctx.runtime_state.get(coord)
        if mono is not None and not mono.is_empty:
            has_solid = True
            break

    changed = False

    if not has_solid:
        for coord in _iter_rect_coords(x0, y0, x1, y1):
            if coord in ctx.runtime_state:
                ctx.runtime_state.pop(coord, None)
                changed = True
    else:
        for coord in _iter_rect_coords(x0, y0, x1, y1):
            if coord not in ctx.runtime_state:
                continue
            mono = ctx.runtime_state.get(coord)
            if mono is not None and not mono.is_empty:
                if not mono_deep_equal(mono, air_mono()):
                    ctx.runtime_state[coord] = air_mono()
                    changed = True

    for coord in _iter_rect_coords(x0, y0, x1, y1):
        if coord in ctx.static_state.buttons:
            del ctx.static_state.buttons[coord]
            changed = True
        if coord in ctx.static_state.targets:
            del ctx.static_state.targets[coord]
            changed = True

    if not changed:
        return False

    _clear_level_saved(ctx)
    ctx.history_stack.append((old_state, old_static))
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    return True


def _refresh_level_cleared(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        ctx.level_cleared = False
        return
    ctx.level_cleared = is_goal(ctx.runtime_state, ctx.static_state)


def _clear_level_saved(ctx: AppCtx) -> None:
    ctx.level_saved = False


def _apply_substantive_action(ctx: AppCtx, action: Action) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    _clear_level_saved(ctx)
    ctx.history_stack.append((clone_state(ctx.runtime_state) or {}, clone_static_state(ctx.static_state) or ctx.static_state))
    ctx.runtime_state = apply_action(ctx.runtime_state, action, ctx.static_state)
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    _cancel_middle_selection(ctx)


def _reset_level(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.initial_state is None or ctx.static_state is None:
        return
    _clear_level_saved(ctx)
    ctx.history_stack.append((clone_state(ctx.runtime_state) or {}, clone_static_state(ctx.static_state) or ctx.static_state))
    ctx.runtime_state = clone_state(ctx.initial_state) or {}
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    _cancel_middle_selection(ctx)


def _undo(ctx: AppCtx) -> None:
    if not ctx.history_stack:
        return
    _clear_level_saved(ctx)
    state, static_state = ctx.history_stack.pop()
    ctx.runtime_state = state
    ctx.static_state = static_state
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    _cancel_middle_selection(ctx)


def _tick_key_repeat(
    next_repeat_at: int | None,
    *,
    is_pressed: callable,
    interval_ms: int,
    step: callable,
) -> tuple[bool, int | None]:
    """
    Generic "key hold repeat" helper.

    Returns (moved, next_repeat_at). When key is released or step signals stop, next_repeat_at becomes None.
    """
    if next_repeat_at is None:
        return False, None
    if not is_pressed():
        return False, None
    now = pygame.time.get_ticks()
    moved = False
    while now >= next_repeat_at:
        if not step():
            return moved, None
        next_repeat_at += interval_ms
        moved = True
    return moved, next_repeat_at


def tick_undo_z_repeat(ctx: AppCtx) -> bool:
    """After Z held for UNDO_Z_REPEAT_DELAY_MS, undo every UNDO_Z_REPEAT_INTERVAL_MS until release."""
    if ctx.mode != "playing" or ctx.undo_z_next_repeat_at is None:
        return False

    moved, next_at = _tick_key_repeat(
        ctx.undo_z_next_repeat_at,
        is_pressed=lambda: pygame.key.get_pressed()[pygame.K_z],
        interval_ms=UNDO_Z_REPEAT_INTERVAL_MS,
        step=lambda: (False if not ctx.history_stack else (_undo(ctx) or True)),
    )
    ctx.undo_z_next_repeat_at = next_at
    return moved


def tick_move_repeat(ctx: AppCtx) -> bool:
    """After move key held for MOVE_REPEAT_DELAY_MS, apply movement every MOVE_REPEAT_INTERVAL_MS until release."""
    if ctx.mode != "playing" or ctx.level_cleared:
        ctx.move_hold_key = None
        ctx.move_next_repeat_at = None
        return False
    if ctx.move_hold_key is None or ctx.move_next_repeat_at is None:
        return False

    action = KEY_TO_ACTION.get(ctx.move_hold_key)
    if action is None:
        ctx.move_hold_key = None
        ctx.move_next_repeat_at = None
        return False

    key = ctx.move_hold_key
    moved, next_at = _tick_key_repeat(
        ctx.move_next_repeat_at,
        is_pressed=lambda: pygame.key.get_pressed()[key],
        interval_ms=MOVE_REPEAT_INTERVAL_MS,
        step=lambda: (_apply_substantive_action(ctx, action) or (not ctx.level_cleared)),
    )
    ctx.move_next_repeat_at = next_at
    if next_at is None:
        ctx.move_hold_key = None
    return moved


def _return_to_select_level(ctx: AppCtx) -> None:
    ctx.mode = "select_level"
    ctx.preview_stack.clear()
    ctx.level_cleared = False
    ctx.editor_mode = False
    ctx.undo_z_next_repeat_at = None
    ctx.move_hold_key = None
    ctx.move_next_repeat_at = None
    _cancel_middle_selection(ctx)
    stop_solver(ctx)
    refresh_levels(ctx)


def _handle_play_click(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> None:
    if ctx.runtime_state is None:
        return
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL if ctx.editor_mode else 0)
    coord = screen_to_world(pos, world_vp)
    if coord is None:
        pop_preview(ctx)
        return

    # Preview layers occlude lower world objects at the same coord.
    for layer in reversed(ctx.preview_stack):
        rel = sub_coord(coord, layer.anchor_world)
        if rel not in layer.state:
            continue
        top_mono = layer.state.get(rel)
        if top_mono is None or top_mono.is_empty:
            return
        before_depth = len(ctx.preview_stack)
        ok = push_preview_if_data(top_mono, rel, id(layer.state), ctx)
        after_depth = len(ctx.preview_stack)
        if ok and after_depth > before_depth:
            _cancel_middle_selection(ctx)
        if not ok:
            pop_preview(ctx)
        return

    # Clicking top preview source closes that preview only when no preview
    # layer (including the top one itself) occupies this coord.
    if ctx.preview_stack and ctx.preview_stack[-1].anchor_world == coord:
        ctx.preview_stack.pop()
        return

    mono = resolve_visible_mono(ctx, coord)
    if mono is None:
        pop_preview(ctx)
        return
    runtime_mono = ctx.runtime_state.get(coord)
    if runtime_mono is None or runtime_mono.is_empty:
        pop_preview(ctx)
        return
    before_depth = len(ctx.preview_stack)
    ok = push_preview_if_data(runtime_mono, coord, id(ctx.runtime_state), ctx)
    after_depth = len(ctx.preview_stack)
    if ok and after_depth > before_depth:
        _cancel_middle_selection(ctx)
    if not ok:
        pop_preview(ctx)


def _begin_mouse_session(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL if ctx.editor_mode else 0)
    press_coord = screen_to_world(pos, world_vp)
    session = DragSession(
        active=True,
        press_pos=pos,
        press_coord=press_coord,
        moved_far=False,
        payload=None,
        hover_coord=press_coord,
        drag_offset=(0, 0),
    )
    if not ctx.editor_mode:
        ctx.drag_session = session
        return
    for item in ctx.editor_palette_items:
        if item.rect is None or not item.rect.collidepoint(pos):
            continue
        if item.kind == "trash":
            break
        session.payload = DragPayload(
            kind="palette",
            source_coord=None,
            palette_kind=item.kind,
            palette_color=item.color,
        )
        session.drag_offset = (0, 0)
        ctx.drag_session = session
        return
    coord = session.press_coord
    if coord is not None:
        # If there's a committed middle-button selection and the press is inside it,
        # dragging should move the whole region (not a single cell object).
        if ctx.middle_select_anchor is not None and ctx.middle_select_size is not None:
            x0, y0 = ctx.middle_select_anchor
            x_len, y_len = ctx.middle_select_size
            if x0 <= coord[0] < x0 + x_len and y0 <= coord[1] < y0 + y_len:
                cell_rect = world_to_screen(coord, world_vp)
                session.drag_offset = (cell_rect.centerx - pos[0], cell_rect.centery - pos[1])

                press_rel = (coord[0] - x0, coord[1] - y0)
                state_sub = {}
                targets_sub: dict[tuple[int, int], TargetData] = {}
                buttons_sub: dict[tuple[int, int], list[ButtonData]] = {}

                for rx in range(x_len):
                    for ry in range(y_len):
                        abs_coord = (x0 + rx, y0 + ry)
                        if abs_coord in ctx.runtime_state:
                            state_sub[(rx, ry)] = clone_mono(ctx.runtime_state.get(abs_coord))
                        if abs_coord in ctx.static_state.targets:
                            t = ctx.static_state.targets[abs_coord]
                            targets_sub[(rx, ry)] = TargetData(required_is_controllable=t.required_is_controllable, required_color=t.required_color)
                        if abs_coord in ctx.static_state.buttons:
                            moved = ctx.static_state.buttons[abs_coord]
                            buttons_sub[(rx, ry)] = [ButtonData(button_type=b.button_type, color=b.color) for b in moved]

                session.payload = DragPayload(
                    kind="selection",
                    selection_size=(x_len, y_len),
                    selection_press_rel=press_rel,
                    selection_state=state_sub,
                    selection_static=StaticState(targets=targets_sub, buttons=buttons_sub),
                )
                ctx.drag_session = session
                return

        mono = ctx.runtime_state.get(coord)
        cell_rect = world_to_screen(coord, world_vp)
        session.drag_offset = (cell_rect.centerx - pos[0], cell_rect.centery - pos[1])
        if mono is not None and not mono.is_empty:
            session.payload = DragPayload(kind="state", source_coord=coord, state_mono=clone_mono(mono))
        else:
            buttons = ctx.static_state.buttons.get(coord, [])
            if buttons:
                session.payload = DragPayload(
                    kind="buttons",
                    source_coord=coord,
                    buttons=[ButtonData(button_type=b.button_type, color=b.color) for b in buttons],
                )
            elif coord in ctx.static_state.targets:
                target = ctx.static_state.targets[coord]
                session.payload = DragPayload(
                    kind="target",
                    source_coord=coord,
                    target=TargetData(
                        required_is_controllable=target.required_is_controllable,
                        required_color=target.required_color,
                    ),
                )
            elif mono is not None and mono.is_empty:
                session.payload = DragPayload(kind="state", source_coord=coord, state_mono=clone_mono(mono))
    ctx.drag_session = session


def _update_mouse_session(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> None:
    if not ctx.drag_session.active or ctx.runtime_state is None:
        return
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL if ctx.editor_mode else 0)
    dx = abs(pos[0] - ctx.drag_session.press_pos[0])
    dy = abs(pos[1] - ctx.drag_session.press_pos[1])
    half_cell = max(1, world_vp.cell // 2)
    if dx > half_cell or dy > half_cell:
        ctx.drag_session.moved_far = True
    anchor_pos = (pos[0] + ctx.drag_session.drag_offset[0], pos[1] + ctx.drag_session.drag_offset[1])
    ctx.drag_session.hover_coord = screen_to_world(anchor_pos, world_vp)


def _is_delete_drop(ctx: AppCtx, anchor_pos: tuple[int, int], surface: pygame.Surface) -> bool:
    if not ctx.editor_mode:
        return False
    panel_rect = pygame.Rect(surface.get_width() - EDITOR_RIGHT_PANEL, 0, EDITOR_RIGHT_PANEL, surface.get_height())
    return panel_rect.collidepoint(anchor_pos)


def _editor_toggle_reject_flags(ctx: AppCtx, surface: pygame.Surface, *, toggle_save: bool) -> bool:
    if not ctx.editor_mode or ctx.runtime_state is None or ctx.static_state is None:
        return False
    bounds = _get_committed_selection_bounds(ctx)
    if bounds is not None:
        x0, y0, x1, y1 = bounds
        coords = list(_iter_rect_coords(x0, y0, x1, y1))
    else:
        world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
        c = screen_to_world(pygame.mouse.get_pos(), world_vp)
        if c is None:
            return False
        coords = [c]

    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state
    changed = False
    for coord in coords:
        mono = ctx.runtime_state.get(coord)
        if not is_solid_value(mono):
            continue
        assert mono is not None
        if toggle_save:
            mono.reject_save = not mono.reject_save
        else:
            mono.reject_load = not mono.reject_load
        changed = True

    if changed:
        _clear_level_saved(ctx)
        ctx.history_stack.append((old_state, old_static))
        stop_solver(ctx)
        _refresh_level_cleared(ctx)
    return changed


def _apply_palette_to_coord(ctx: AppCtx, payload: DragPayload, coord: tuple[int, int]) -> None:
    if ctx.runtime_state is None or ctx.static_state is None or payload.palette_kind is None:
        return
    if payload.palette_kind == "air":
        ctx.runtime_state[coord] = air_mono()
        return
    if payload.palette_kind == "wall":
        ctx.runtime_state[coord] = MonoData(is_empty=False, is_wall=True, is_controllable=False, color=0, data=None)
        return
    if payload.palette_kind == "player":
        ctx.runtime_state[coord] = MonoData(is_empty=False, is_wall=False, is_controllable=True, color=0, data=None)
        return
    if payload.palette_kind == "box":
        ctx.runtime_state[coord] = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=0, data=None)
        return
    if payload.palette_kind == "disk":
        ctx.runtime_state[coord] = MonoData(
            is_empty=False,
            is_wall=False,
            is_controllable=False,
            color=payload.palette_color,
            data={(1, 0): None},
        )
        return
    if payload.palette_kind == "s_button":
        ctx.static_state.buttons.setdefault(coord, []).append(ButtonData(button_type="s", color=payload.palette_color))
        return
    if payload.palette_kind == "l_button":
        ctx.static_state.buttons.setdefault(coord, []).append(ButtonData(button_type="l", color=payload.palette_color))
        return
    if payload.palette_kind == "player_target":
        ctx.static_state.targets[coord] = TargetData(required_is_controllable=True, required_color=0)
        return
    if payload.palette_kind == "box_target":
        ctx.static_state.targets[coord] = TargetData(
            required_is_controllable=False,
            required_color=payload.palette_color,
        )


def _commit_preview_chain(ctx: AppCtx) -> None:
    if ctx.runtime_state is None:
        return
    for i in range(len(ctx.preview_stack) - 1, -1, -1):
        layer = ctx.preview_stack[i]
        holder = ctx.runtime_state if i == 0 else ctx.preview_stack[i - 1].state
        source = holder.get(layer.source_coord)
        if source is None or source.is_empty:
            continue
        source.data = clone_state(layer.state) or {}


def _editor_delete_at_pos_like_panel(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    """Same outcome as dragging the object at coord to the right trash panel."""
    if ctx.runtime_state is None or ctx.static_state is None:
        return False
    panel_rect = pygame.Rect(surface.get_width() - EDITOR_RIGHT_PANEL, 0, EDITOR_RIGHT_PANEL, surface.get_height())
    if panel_rect.collidepoint(pos):
        return False
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
    coord = screen_to_world(pos, world_vp)
    if coord is None:
        return False
    mono = ctx.runtime_state.get(coord)
    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state
    changed = False
    if mono is not None and not mono.is_empty:
        ctx.runtime_state[coord] = air_mono()
        changed = True
    elif ctx.static_state.buttons.get(coord):
        del ctx.static_state.buttons[coord]
        changed = True
    elif coord in ctx.static_state.targets:
        del ctx.static_state.targets[coord]
        changed = True
    elif mono is not None and mono.is_empty:
        ctx.runtime_state.pop(coord, None)
        changed = True
    if changed:
        _clear_level_saved(ctx)
        ctx.history_stack.append((old_state, old_static))
        clear_preview(ctx)
        stop_solver(ctx)
        _refresh_level_cleared(ctx)
    return changed


def _handle_editor_right_click(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    if not ctx.editor_mode:
        return False
    if ctx.preview_stack:
        changed = _toggle_none_in_top_preview(ctx, pos, surface)
        if changed:
            _cancel_middle_selection(ctx)
        return changed
    changed = _editor_delete_at_pos_like_panel(ctx, pos, surface)
    if changed:
        _cancel_middle_selection(ctx)
    return changed


def _toggle_none_in_top_preview(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    if not ctx.editor_mode or not ctx.preview_stack:
        return False
    if ctx.runtime_state is None or ctx.static_state is None:
        return False
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL if ctx.editor_mode else 0)
    coord = screen_to_world(pos, world_vp)
    if coord is None:
        return False
    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state
    top = ctx.preview_stack[-1]
    rel = sub_coord(coord, top.anchor_world)
    if rel in top.state:
        del top.state[rel]
    else:
        top.state[rel] = None
    _commit_preview_chain(ctx)
    _clear_level_saved(ctx)
    ctx.history_stack.append((old_state, old_static))
    stop_solver(ctx)
    _refresh_level_cleared(ctx)
    return True


def _apply_editor_drop(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> bool:
    if not ctx.editor_mode or not ctx.drag_session.active or ctx.drag_session.payload is None:
        return False
    if ctx.runtime_state is None or ctx.static_state is None:
        return False
    payload = ctx.drag_session.payload
    anchor_pos = (pos[0] + ctx.drag_session.drag_offset[0], pos[1] + ctx.drag_session.drag_offset[1])
    is_delete = _is_delete_drop(ctx, anchor_pos, surface)
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
    dst = screen_to_world(anchor_pos, world_vp)
    if not is_delete and dst is None:
        return False
    old_state = clone_state(ctx.runtime_state) or {}
    old_static = clone_static_state(ctx.static_state) or ctx.static_state
    changed = False

    if payload.kind == "selection":
        if payload.selection_press_rel is None or payload.selection_size is None:
            return False
        if ctx.middle_select_anchor is None or ctx.middle_select_size is None:
            return False

        # Ctrl+X on the committed selection region first (save to clipboard + clear region).
        _save_committed_selection_to_clipboard(ctx)
        cut_changed = _clear_committed_selection(ctx)

        if is_delete:
            _cancel_middle_selection(ctx)
            return cut_changed

        assert dst is not None

        # Ctrl+V onto the new selection region.
        press_rel_x, press_rel_y = payload.selection_press_rel
        new_anchor = (dst[0] - press_rel_x, dst[1] - press_rel_y)

        ctx.middle_select_anchor = new_anchor
        ctx.middle_select_size = payload.selection_size

        paste_changed = _apply_clipboard_to_selection(ctx, payload.selection_size)
        _cancel_middle_selection(ctx)
        return cut_changed or paste_changed

    if payload.kind == "state" and payload.source_coord is not None:
        src = payload.source_coord
        if is_delete:
            src_mono = ctx.runtime_state.get(src)
            if src_mono is not None:
                if src_mono.is_empty:
                    ctx.runtime_state.pop(src, None)
                else:
                    ctx.runtime_state[src] = air_mono()
                changed = True
        elif dst is not None:
            src_mono = clone_mono(ctx.runtime_state.get(src))
            if src_mono is not None:
                dst_exists = dst in ctx.runtime_state
                dst_raw = ctx.runtime_state.get(dst)
                dst_mono = clone_mono(dst_raw)
                ctx.runtime_state[dst] = src_mono
                if src_mono.is_empty:
                    if not dst_exists:
                        ctx.runtime_state.pop(src, None)
                    elif dst_raw is None:
                        ctx.runtime_state[src] = None
                    elif dst_mono is not None:
                        ctx.runtime_state[src] = dst_mono
                    else:
                        ctx.runtime_state[src] = None
                else:
                    if dst_mono is None:
                        dst_mono = air_mono()
                    ctx.runtime_state[src] = dst_mono
                changed = src != dst
    elif payload.kind == "buttons" and payload.source_coord is not None:
        src = payload.source_coord
        if is_delete:
            if ctx.static_state.buttons.get(src):
                del ctx.static_state.buttons[src]
                changed = True
        elif dst is not None:
            src_buttons = ctx.static_state.buttons.get(src, [])
            if src_buttons:
                moved = [ButtonData(button_type=b.button_type, color=b.color) for b in src_buttons]
                del ctx.static_state.buttons[src]
                ctx.static_state.buttons.setdefault(dst, []).extend(moved)
                changed = True
    elif payload.kind == "target" and payload.source_coord is not None and payload.target is not None:
        src = payload.source_coord
        if is_delete:
            if src in ctx.static_state.targets:
                del ctx.static_state.targets[src]
                changed = True
        elif dst is not None and src in ctx.static_state.targets:
            moved = ctx.static_state.targets[src]
            del ctx.static_state.targets[src]
            ctx.static_state.targets[dst] = moved
            changed = True
    elif payload.kind == "palette" and dst is not None:
        _apply_palette_to_coord(ctx, payload, dst)
        changed = True

    if changed:
        _clear_level_saved(ctx)
        ctx.history_stack.append((old_state, old_static))
        clear_preview(ctx)
        stop_solver(ctx)
        _refresh_level_cleared(ctx)
        _cancel_middle_selection(ctx)
    return changed


def _save_current_level(ctx: AppCtx) -> None:
    if ctx.current_level_idx is None or ctx.runtime_state is None or ctx.static_state is None:
        return
    # Persist current runtime_state as the new initial_state.
    ctx.initial_state = clone_state(ctx.runtime_state) or {}
    level = Level(
        static_state=clone_static_state(ctx.static_state) or ctx.static_state,
        initial_state=clone_state(ctx.runtime_state) or {},
    )
    if save_level_by_index(ctx.levels_path, ctx.current_level_idx, level):
        if 0 <= ctx.current_level_idx < len(ctx.levels):
            ctx.levels[ctx.current_level_idx] = level
        ctx.level_saved = True


def handle_event(ctx: AppCtx, event: pygame.event.Event, surface: pygame.Surface) -> bool:
    if event.type == pygame.QUIT:
        ctx.running = False
        return False
    if event.type not in (
        pygame.KEYDOWN,
        pygame.KEYUP,
        pygame.MOUSEBUTTONDOWN,
        pygame.MOUSEBUTTONUP,
        pygame.MOUSEMOTION,
        pygame.MOUSEWHEEL,
    ):
        return False
    
    if ctx.mode == "select_level":
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                ctx.running = False
                return False
            if event.key == pygame.K_n:
                export_builtin_and_refresh(ctx)
                return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            refresh_levels(ctx)
            try_enter_level_by_click(ctx, event.pos, surface)
        return False

    # playing
    if event.type == pygame.KEYUP and event.key == pygame.K_z:
        ctx.undo_z_next_repeat_at = None
        return False
    if event.type == pygame.KEYUP and event.key in KEY_TO_ACTION:
        if ctx.move_hold_key == event.key:
            # Try seamless fallback to another held movement key.
            pressed = pygame.key.get_pressed()
            for k in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN, pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT):
                if pressed[k]:
                    ctx.move_hold_key = k
                    ctx.move_next_repeat_at = pygame.time.get_ticks() + MOVE_REPEAT_INTERVAL_MS
                    break
            else:
                ctx.move_hold_key = None
                ctx.move_next_repeat_at = None
        return False

    if event.type == pygame.MOUSEWHEEL and ctx.editor_mode:
        ctx.editor_panel_scroll = max(
            0,
            min(
                ctx.editor_panel_scroll_max,
                ctx.editor_panel_scroll - event.y * EDITOR_SCROLL_STEP,
            ),
        )
        return False
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
        return _handle_editor_right_click(ctx, event.pos, surface)

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
        if not ctx.editor_mode:
            return False
        # Middle-button selection must not conflict with disk previews.
        clear_preview(ctx)
        _cancel_middle_selection(ctx)
        if ctx.runtime_state is None:
            return False
        world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
        coord = screen_to_world(event.pos, world_vp)
        if coord is None:
            return False
        ctx.middle_select_dragging = True
        ctx.middle_select_press_coord = coord
        ctx.middle_select_hover_coord = coord
        return False

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
            _return_to_select_level(ctx)
            return False
        if event.key == pygame.K_l:
            ctx.editor_mode = not ctx.editor_mode
            _cancel_middle_selection(ctx)
            return False
        if event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
            if ctx.editor_mode:
                _save_current_level(ctx)
            return False

        if ctx.editor_mode:
            if event.key == pygame.K_LEFTBRACKET:
                _editor_toggle_reject_flags(ctx, surface, toggle_save=True)
                return False
            if event.key == pygame.K_RIGHTBRACKET:
                _editor_toggle_reject_flags(ctx, surface, toggle_save=False)
                return False

        if ctx.editor_mode:
            bounds = _get_committed_selection_bounds(ctx)
            if bounds is not None:
                x0, y0, x1, y1 = bounds
                _ = (x0, y0, x1, y1)
                x_len = ctx.middle_select_size[0] if ctx.middle_select_size is not None else 0
                y_len = ctx.middle_select_size[1] if ctx.middle_select_size is not None else 0
                key = (x_len, y_len)

                if event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                    _save_committed_selection_to_clipboard(ctx)
                    _cancel_middle_selection(ctx)
                    return False
                if event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                    changed = _apply_clipboard_to_selection(ctx, key)
                    _cancel_middle_selection(ctx)
                    return changed
                if event.key == pygame.K_x and (event.mod & pygame.KMOD_CTRL):
                    _save_committed_selection_to_clipboard(ctx)
                    changed = _clear_committed_selection(ctx)
                    _cancel_middle_selection(ctx)
                    return changed
                if event.key == pygame.K_DELETE:
                    changed = _clear_committed_selection(ctx)
                    _cancel_middle_selection(ctx)
                    return changed

        if event.key in KEY_TO_ACTION:
            if ctx.level_cleared:
                return False
            if getattr(event, "repeat", False):
                return False
            _apply_substantive_action(ctx, KEY_TO_ACTION[event.key])
            ctx.move_hold_key = event.key
            ctx.move_next_repeat_at = pygame.time.get_ticks() + MOVE_REPEAT_DELAY_MS
            return True
        if event.key == pygame.K_r:
            _reset_level(ctx)
            return True
        if event.key == pygame.K_z:
            if getattr(event, "repeat", False):
                return False
            _undo(ctx)
            ctx.undo_z_next_repeat_at = pygame.time.get_ticks() + UNDO_Z_REPEAT_DELAY_MS
            return True
        if event.key == pygame.K_h:
            start_or_restart_solver(ctx)
            return False
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        _begin_mouse_session(ctx, event.pos, surface)
        return False
    if event.type == pygame.MOUSEMOTION:
        if ctx.editor_mode and ctx.middle_select_dragging:
            if ctx.runtime_state is not None:
                world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
                ctx.middle_select_hover_coord = screen_to_world(event.pos, world_vp)
            return False
        _update_mouse_session(ctx, event.pos, surface)
        return False
    if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
        if not ctx.editor_mode:
            return False
        if not ctx.middle_select_dragging or ctx.runtime_state is None or ctx.middle_select_press_coord is None:
            return False
        world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL)
        release_coord = screen_to_world(event.pos, world_vp)
        if release_coord is None:
            release_coord = ctx.middle_select_hover_coord or ctx.middle_select_press_coord
        p = ctx.middle_select_press_coord
        x0 = min(p[0], release_coord[0])
        y0 = min(p[1], release_coord[1])
        x_len = abs(p[0] - release_coord[0]) + 1
        y_len = abs(p[1] - release_coord[1]) + 1
        ctx.middle_select_anchor = (x0, y0)
        ctx.middle_select_size = (x_len, y_len)
        ctx.middle_select_dragging = False
        ctx.middle_select_press_coord = None
        ctx.middle_select_hover_coord = None
        return False
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        changed = _apply_editor_drop(ctx, event.pos, surface)
        is_world_press = ctx.drag_session.press_coord is not None
        should_click = (
            (not changed)
            and (not ctx.drag_session.moved_far)
            and ((not ctx.editor_mode) or is_world_press)
        )
        if should_click:
            _handle_play_click(ctx, event.pos, surface)
        ctx.drag_session = DragSession()
        return changed
    return False
