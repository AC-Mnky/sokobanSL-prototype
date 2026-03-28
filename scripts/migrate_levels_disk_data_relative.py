"""One-shot migration: disk MonoData.data keys from world coords to relative offsets.

Run once from repo root:  python scripts/migrate_levels_disk_data_relative.py
Do not re-run after levels already use relative keys (would corrupt data).
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.disk_migration import migrate_level_disk_data_to_relative  # noqa: E402


def main() -> None:
    levels_dir = ROOT / "data" / "levels"
    if not levels_dir.is_dir():
        print(f"Missing directory: {levels_dir}", file=sys.stderr)
        sys.exit(1)
    files = sorted(levels_dir.glob("*.pkl"), key=lambda fp: fp.name.lower())
    for fp in files:
        with fp.open("rb") as f:
            level = pickle.load(f)
        migrate_level_disk_data_to_relative(level)
        with fp.open("wb") as f:
            pickle.dump(level, f)
        print(f"migrated {fp.name}")


if __name__ == "__main__":
    main()
