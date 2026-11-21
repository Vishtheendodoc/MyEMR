"""Copy a SQLite clinic file. PostgreSQL backups use the database host's own tools."""

from __future__ import annotations

import shutil
from pathlib import Path


def backup_sqlite(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def restore_sqlite(backup: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, destination)
    return destination
