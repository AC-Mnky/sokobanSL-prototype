from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Literal

import pygame

from src.types import Action, Coord, Level, State, StaticState

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


@dataclass(slots=True)
class AppCtx:
    mode: Mode = "select_level"
    levels_path: Path = Path("data/levels.pkl")
    levels: list[Level] = field(default_factory=list)
    current_level_idx: int | None = None
    static_state: StaticState | None = None
    runtime_state: State | None = None
    initial_state: State | None = None
    history_stack: list[State] = field(default_factory=list)
    preview_stack: list[PreviewLayer] = field(default_factory=list)
    level_cleared: bool = False
    solver_session: SolverSession = field(default_factory=SolverSession)
    running: bool = True
    # cached per frame
    last_level_button_rects: list[pygame.Rect] = field(default_factory=list)
