from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Literal

import pygame

from src.types import Action, ButtonData, Coord, Level, MonoData, State, StaticState, TargetData

Mode = Literal["select_level", "playing"]
SolverStatus = Literal["idle", "running", "solved", "no_solution"]


@dataclass(slots=True)
class SolverSession:
    status: SolverStatus = "idle"
    generator: Generator | None = None
    steps: int = 0
    solution: tuple[Action, ...] = field(default_factory=tuple)
    searched_state_count: int = 0
    elapsed_seconds: float = 0.0


@dataclass(slots=True)
class PreviewLayer:
    state: State
    color: int
    source_coord: Coord
    anchor_world: Coord
    source_container_id: int = 0


@dataclass(slots=True)
class DragPayload:
    kind: Literal["state", "buttons", "target", "palette", "selection"]
    source_coord: Coord | None = None
    state_mono: MonoData | None = None
    buttons: list[ButtonData] = field(default_factory=list)
    target: TargetData | None = None
    palette_kind: Literal["air", "wall", "player", "box", "disk", "s_button", "l_button", "player_target", "box_target"] | None = None
    palette_color: int = 0

    # Selection drag (mouse left) payload.
    # All coords are relative to the selection's top-left.
    selection_size: tuple[int, int] | None = None  # (x_len, y_len)
    selection_press_rel: Coord | None = None  # press cell offset relative to selection top-left
    selection_state: State | None = None  # relative runtime sub-state snapshot
    selection_static: StaticState | None = None  # relative static sub-state snapshot


@dataclass(slots=True)
class DragSession:
    active: bool = False
    press_pos: tuple[int, int] = (0, 0)
    press_coord: Coord | None = None
    moved_far: bool = False
    payload: DragPayload | None = None
    hover_coord: Coord | None = None
    drag_offset: tuple[int, int] = (0, 0)


@dataclass(slots=True)
class EditorPaletteItem:
    key: str
    label: str
    kind: Literal["air", "wall", "player", "box", "disk", "s_button", "l_button", "player_target", "box_target", "trash"]
    color: int = 0
    rect: pygame.Rect | None = None


@dataclass(slots=True)
class AppCtx:
    mode: Mode = "select_level"
    levels_path: Path = Path("data/levels")
    levels: list[Level] = field(default_factory=list)
    level_names: list[str] = field(default_factory=list)
    # Level select: (chapter heading or None, number of buttons). Sum of counts == len(levels).
    level_select_sections: list[tuple[str | None, int]] = field(default_factory=list)
    level_select_scroll_y: int = 0
    current_level_idx: int | None = None
    static_state: StaticState | None = None
    runtime_state: State | None = None
    initial_state: State | None = None
    history_stack: list[tuple[State, StaticState]] = field(default_factory=list)
    preview_stack: list[PreviewLayer] = field(default_factory=list)
    level_cleared: bool = False
    level_saved: bool = False
    solver_session: SolverSession = field(default_factory=SolverSession)
    editor_mode: bool = False
    drag_session: DragSession = field(default_factory=DragSession)
    editor_palette_items: list[EditorPaletteItem] = field(default_factory=list)
    editor_panel_scroll: int = 0
    editor_panel_scroll_max: int = 0
    # Middle (mouse button 2) rectangle selection in editor_mode.
    # Committed selection uses `middle_select_anchor` + `middle_select_size`,
    # while dragging uses `middle_select_press_coord` + `middle_select_hover_coord`.
    middle_select_dragging: bool = False
    middle_select_press_coord: Coord | None = None
    middle_select_hover_coord: Coord | None = None
    middle_select_anchor: Coord | None = None
    middle_select_size: tuple[int, int] | None = None  # (x_len, y_len)
    # Clipboard lifetime == program runtime.
    # key: (x_len, y_len) in cells
    # value: (relative state sub-dict, relative static state sub-dict)
    clipboard: dict[tuple[int, int], tuple[State, StaticState]] = field(default_factory=dict)
    clipboard_last_key: tuple[int, int] | None = None
    running: bool = True
    # Z 长按连续撤回：按下后首次自动撤回的目标时刻（ms，pygame.get_ticks）；None 表示未在长按序列中
    undo_z_next_repeat_at: int | None = None
    # 长按移动键连发：当前被“锁定”的移动键，以及下一次触发移动的目标时刻（ms）
    move_hold_key: int | None = None
    move_next_repeat_at: int | None = None
    # cached per frame
    last_level_button_rects: list[pygame.Rect] = field(default_factory=list)
