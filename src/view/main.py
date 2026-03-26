from __future__ import annotations

from pathlib import Path

from src.view.runtime import run_app
from src.view.types import AppCtx


def main() -> None:
    ctx = AppCtx(levels_path=Path("data/levels.pkl"))
    run_app(ctx)


if __name__ == "__main__":
    main()
