"""Default data directory rules."""

from collections.abc import Mapping
from pathlib import Path

APP_DIR_NAME = "todo-qt"


def default_data_dir(environ: Mapping[str, str], home: Path, platform: str) -> Path:
    """Return the platform default data directory (ADR-0005)."""
    if platform == "darwin":
        return home / "Library" / "Application Support" / APP_DIR_NAME
    xdg = environ.get("XDG_DATA_HOME", "")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / APP_DIR_NAME
    return home / ".local" / "share" / APP_DIR_NAME
