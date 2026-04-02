import pygame

from src.level_io import save_levels
from src.types import ButtonData, Level, MonoData, StaticState, TargetData
from src.view.input_router import _apply_editor_drop, _begin_mouse_session, handle_event
from src.view.preview import push_preview_if_data
from src.view.render import _collect_editor_colors, build_viewport, world_to_screen
from src.view.types import AppCtx, DragPayload, PreviewLayer


def player(color: int = 0) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=True, color=color, data=None)


def box(color: int = 0) -> MonoData:
    return MonoData(is_empty=False, is_wall=False, is_controllable=False, color=color, data=None)


def make_ctx() -> AppCtx:
    return AppCtx(
        mode="playing",
        static_state=StaticState(targets={}, buttons={}),
        runtime_state={(0, 0): player(), (1, 0): box()},
        initial_state={(0, 0): player(), (1, 0): box()},
    )


def ensure_pygame():
    if not pygame.get_init():
        pygame.init()


def test_drag_state_swaps_cells():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    src_rect = world_to_screen((0, 0), vp)
    dst_rect = world_to_screen((1, 0), vp)
    _begin_mouse_session(ctx, src_rect.center, surface)
    ctx.drag_session.payload = DragPayload(kind="state", source_coord=(0, 0), state_mono=player())
    changed = _apply_editor_drop(ctx, dst_rect.center, surface)
    assert changed
    assert ctx.runtime_state[(1, 0)] is not None and ctx.runtime_state[(1, 0)].is_controllable
    assert len(ctx.history_stack) == 1


def test_drag_buttons_delete_only_buttons():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.static_state.buttons[(0, 0)] = [ButtonData(button_type="s", color=1)]
    ctx.static_state.targets[(0, 0)] = TargetData(required_is_controllable=False, required_color=0)
    ctx.drag_session.active = True
    ctx.drag_session.payload = DragPayload(kind="buttons", source_coord=(0, 0), buttons=[ButtonData(button_type="s", color=1)])
    changed = _apply_editor_drop(ctx, (639, 10), pygame.Surface((640, 480)))
    assert changed
    assert (0, 0) not in ctx.static_state.buttons
    assert (0, 0) in ctx.static_state.targets


def test_pick_priority_buttons_before_target():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = None
    ctx.static_state.buttons[(0, 0)] = [ButtonData(button_type="l", color=2)]
    ctx.static_state.targets[(0, 0)] = TargetData(required_is_controllable=True, required_color=0)
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    src_rect = world_to_screen((0, 0), vp)
    _begin_mouse_session(ctx, src_rect.center, surface)
    assert ctx.drag_session.payload is not None
    assert ctx.drag_session.payload.kind == "buttons"


def test_collect_editor_colors_adds_new_color():
    ctx = make_ctx()
    ctx.runtime_state[(2, 0)] = box(2)
    ctx.static_state.buttons[(3, 0)] = [ButtonData(button_type="s", color=3)]
    colors = _collect_editor_colors(ctx)
    assert 2 in colors and 3 in colors
    assert 1 in colors or 4 in colors
    assert len(colors) >= 3


def test_air_cell_is_draggable_as_state():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    src_rect = world_to_screen((0, 0), vp)
    _begin_mouse_session(ctx, src_rect.center, surface)
    assert ctx.drag_session.payload is not None
    assert ctx.drag_session.payload.kind == "state"


def test_air_priority_is_lower_than_buttons_and_target():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)
    ctx.static_state.buttons[(0, 0)] = [ButtonData(button_type="s", color=1)]
    ctx.static_state.targets[(0, 0)] = TargetData(required_is_controllable=False, required_color=0)
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    src_rect = world_to_screen((0, 0), vp)
    _begin_mouse_session(ctx, src_rect.center, surface)
    assert ctx.drag_session.payload is not None
    assert ctx.drag_session.payload.kind == "buttons"


def test_ctrl_s_overwrites_current_level(tmp_path):
    ensure_pygame()
    levels_path = tmp_path / "levels"
    levels = [
        Level(static_state=StaticState(targets={}, buttons={}), initial_state={(0, 0): player()}),
        Level(static_state=StaticState(targets={}, buttons={}), initial_state={(1, 0): box()}),
    ]
    save_levels(levels_path, levels)
    ctx = AppCtx(
        mode="playing",
        levels_path=levels_path,
        levels=levels,
        current_level_idx=1,
        editor_mode=True,
        static_state=StaticState(targets={(5, 5): TargetData(required_is_controllable=False, required_color=0)}, buttons={}),
        runtime_state={(9, 9): box(7)},
        initial_state={(9, 9): box(7)},
    )
    e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, mod=pygame.KMOD_CTRL)
    changed = handle_event(ctx, e, pygame.Surface((640, 480)))
    assert not changed
    from src.level_io import load_levels

    loaded = load_levels(levels_path)
    assert (9, 9) in loaded[1].initial_state
    assert (5, 5) in loaded[1].static_state.targets


def test_mouse_wheel_scrolls_editor_panel():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.editor_panel_scroll_max = 200
    ctx.editor_panel_scroll = 100
    e_down = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
    changed = handle_event(ctx, e_down, pygame.Surface((640, 480)))
    assert not changed
    assert ctx.editor_panel_scroll > 100


def test_palette_disk_places_colored_disk_with_default_data():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    dst_rect = world_to_screen((2, 0), vp)
    ctx.drag_session.active = True
    ctx.drag_session.payload = DragPayload(kind="palette", palette_kind="disk", palette_color=3)
    changed = _apply_editor_drop(ctx, dst_rect.center, surface)
    assert changed
    mono = ctx.runtime_state[(2, 0)]
    assert mono is not None and (not mono.is_empty) and (not mono.is_wall) and (not mono.is_controllable)
    assert mono.color == 3
    assert mono.data == {(1, 0): None}


def test_air_drag_to_none_keeps_source_as_none():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)
    ctx.runtime_state[(2, 0)] = None
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    dst_rect = world_to_screen((2, 0), vp)
    ctx.drag_session.active = True
    ctx.drag_session.payload = DragPayload(
        kind="state",
        source_coord=(0, 0),
        state_mono=MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None),
    )
    changed = _apply_editor_drop(ctx, dst_rect.center, surface)
    assert changed
    assert (0, 0) in ctx.runtime_state
    assert ctx.runtime_state[(0, 0)] is None


def test_air_drag_to_missing_key_removes_source_key():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    dst_rect = world_to_screen((3, 0), vp)
    ctx.drag_session.active = True
    ctx.drag_session.payload = DragPayload(
        kind="state",
        source_coord=(0, 0),
        state_mono=MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None),
    )
    changed = _apply_editor_drop(ctx, dst_rect.center, surface)
    assert changed
    assert (0, 0) not in ctx.runtime_state


def test_air_drag_to_panel_removes_source_key():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    ctx.runtime_state[(0, 0)] = MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None)
    changed = _apply_editor_drop(ctx, (639, 10), pygame.Surface((640, 480)))
    assert not changed
    ctx.drag_session.active = True
    ctx.drag_session.payload = DragPayload(
        kind="state",
        source_coord=(0, 0),
        state_mono=MonoData(is_empty=True, is_wall=False, is_controllable=False, color=0, data=None),
    )
    changed = _apply_editor_drop(ctx, (639, 10), pygame.Surface((640, 480)))
    assert changed
    assert (0, 0) not in ctx.runtime_state


def test_editor_right_click_deletes_like_panel_when_no_preview():
    ensure_pygame()
    ctx = make_ctx()
    ctx.editor_mode = True
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    pos = world_to_screen((1, 0), vp).center
    e = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=pos)
    changed = handle_event(ctx, e, surface)
    assert changed
    assert ctx.runtime_state[(1, 0)] is not None
    assert ctx.runtime_state[(1, 0)].is_empty
    assert len(ctx.history_stack) == 1


def test_right_click_toggles_none_in_top_preview_and_commits():
    ensure_pygame()
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=2, data={(0, 0): None})
    ctx = AppCtx(
        mode="playing",
        static_state=StaticState(targets={}, buttons={}),
        runtime_state={(0, 0): disk},
        initial_state={(0, 0): disk},
    )
    ctx.editor_mode = True
    ctx.preview_stack = [
        PreviewLayer(state={(0, 0): None}, color=2, source_coord=(0, 0), anchor_world=(0, 0))
    ]
    surface = pygame.Surface((640, 480))
    vp = build_viewport(surface, ctx.runtime_state, right_panel=280)
    c0 = world_to_screen((0, 0), vp).center
    c1 = world_to_screen((1, 0), vp).center
    e_add = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=c1)
    changed_add = handle_event(ctx, e_add, surface)
    assert changed_add
    assert (1, 0) in ctx.preview_stack[-1].state and ctx.preview_stack[-1].state[(1, 0)] is None
    assert ctx.runtime_state[(0, 0)] is not None and ctx.runtime_state[(0, 0)].data is not None
    assert (1, 0) in ctx.runtime_state[(0, 0)].data
    e_remove = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=c0)
    changed_remove = handle_event(ctx, e_remove, surface)
    assert changed_remove
    assert (0, 0) not in ctx.preview_stack[-1].state


def test_clicking_same_disk_preview_removes_existing_layer():
    ctx = AppCtx(
        mode="playing",
        static_state=StaticState(targets={}, buttons={}),
        runtime_state={},
        initial_state={},
    )
    disk = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=3, data={(1, 0): None})
    root_state = {(0, 0): disk}
    pushed = push_preview_if_data(disk, (0, 0), id(root_state), ctx)
    assert pushed
    assert len(ctx.preview_stack) == 1
    # Clicking the same disk again should remove its existing preview layer.
    pushed_again = push_preview_if_data(disk, (0, 0), id(root_state), ctx)
    assert pushed_again
    assert len(ctx.preview_stack) == 0


def test_nested_same_coord_disk_opens_nested_preview_not_remove_parent():
    ctx = AppCtx(
        mode="playing",
        static_state=StaticState(targets={}, buttons={}),
        runtime_state={},
        initial_state={},
    )
    disk_b = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=2, data={(1, 0): None})
    disk_a = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(0, 0): disk_b})
    root_state = {(0, 0): disk_a}

    opened_a = push_preview_if_data(disk_a, (0, 0), id(root_state), ctx)
    assert opened_a
    assert len(ctx.preview_stack) == 1

    opened_b = push_preview_if_data(disk_b, (0, 0), id(ctx.preview_stack[-1].state), ctx)
    assert opened_b
    assert len(ctx.preview_stack) == 2

    # Clicking B again should only close B, keeping A opened.
    toggled_b = push_preview_if_data(disk_b, (0, 0), id(ctx.preview_stack[0].state), ctx)
    assert toggled_b
    assert len(ctx.preview_stack) == 1
    assert ctx.preview_stack[0].source_coord == (0, 0)


def test_push_preview_anchor_world_root_and_nested():
    ctx = AppCtx(
        mode="playing",
        static_state=StaticState(targets={}, buttons={}),
        runtime_state={},
        initial_state={},
    )
    disk_b = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=2, data={(0, 0): None})
    disk_a = MonoData(is_empty=False, is_wall=False, is_controllable=False, color=1, data={(-1, 0): disk_b})
    root = {(2, 0): disk_a}
    ctx.runtime_state = root
    push_preview_if_data(disk_a, (2, 0), id(root), ctx)
    assert ctx.preview_stack[-1].anchor_world == (2, 0)
    push_preview_if_data(disk_b, (-1, 0), id(ctx.preview_stack[0].state), ctx)
    assert ctx.preview_stack[-1].anchor_world == (1, 0)
