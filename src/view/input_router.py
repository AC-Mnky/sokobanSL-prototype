from __future__ import annotations

import pygame

from src.core_step import apply_action
from src.goals import is_goal
from src.level_io import save_level_by_index
from src.state_utils import air_mono, clone_mono, clone_state, clone_static_state, sub_coord
from src.types import Action, ButtonData, Level, MonoData, TargetData
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


def _reset_level(ctx: AppCtx) -> None:
    if ctx.runtime_state is None or ctx.initial_state is None or ctx.static_state is None:
        return
    _clear_level_saved(ctx)
    ctx.history_stack.append((clone_state(ctx.runtime_state) or {}, clone_static_state(ctx.static_state) or ctx.static_state))
    ctx.runtime_state = clone_state(ctx.initial_state) or {}
    clear_preview(ctx)
    stop_solver(ctx)
    _refresh_level_cleared(ctx)


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


def _return_to_select_level(ctx: AppCtx) -> None:
    ctx.mode = "select_level"
    ctx.preview_stack.clear()
    ctx.level_cleared = False
    ctx.editor_mode = False
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
        if not push_preview_if_data(top_mono, rel, id(layer.state), ctx):
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
    if not push_preview_if_data(runtime_mono, coord, id(ctx.runtime_state), ctx):
        pop_preview(ctx)


def _begin_mouse_session(ctx: AppCtx, pos: tuple[int, int], surface: pygame.Surface) -> None:
    if ctx.runtime_state is None or ctx.static_state is None:
        return
    world_vp = build_viewport(surface, ctx.runtime_state, EDITOR_RIGHT_PANEL if ctx.editor_mode else 0)
    session = DragSession(
        active=True,
        press_pos=pos,
        press_coord=screen_to_world(pos, world_vp),
        moved_far=False,
        payload=None,
        hover_coord=None,
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
        return _toggle_none_in_top_preview(ctx, pos, surface)
    return _editor_delete_at_pos_like_panel(ctx, pos, surface)


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
    if event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
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

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
            _return_to_select_level(ctx)
            return False
        if event.key == pygame.K_l:
            ctx.editor_mode = not ctx.editor_mode
            return False
        if event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
            _save_current_level(ctx)
            return False
        if event.key in KEY_TO_ACTION:
            if ctx.level_cleared:
                return False
            _apply_substantive_action(ctx, KEY_TO_ACTION[event.key])
            return True
        if event.key == pygame.K_r:
            _reset_level(ctx)
            return True
        if event.key == pygame.K_z:
            _undo(ctx)
            return True
        if event.key == pygame.K_h:
            start_or_restart_solver(ctx)
            return False
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        _begin_mouse_session(ctx, event.pos, surface)
        return False
    if event.type == pygame.MOUSEMOTION:
        _update_mouse_session(ctx, event.pos, surface)
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
