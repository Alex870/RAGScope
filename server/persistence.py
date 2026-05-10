from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .state import WorkspaceState, utc_now


SAVED_VIEWS_DIR = Path("saved_views")
AUTOSAVE_PATH = SAVED_VIEWS_DIR / "_autosave.json"


def ensure_saved_views_dir() -> Path:
    SAVED_VIEWS_DIR.mkdir(parents=True, exist_ok=True)
    return SAVED_VIEWS_DIR


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return cleaned or "view"


def view_path(state: WorkspaceState) -> Path:
    return ensure_saved_views_dir() / f"{safe_filename(state.name)}.{state.id}.json"


def save_view(state: WorkspaceState, path: Path | None = None) -> Path:
    ensure_saved_views_dir()
    state.touch()
    target = path or view_path(state)
    target.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def autosave(state: WorkspaceState) -> None:
    save_view(state, AUTOSAVE_PATH)


def load_view(path: Path) -> WorkspaceState:
    return WorkspaceState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_views() -> list[Path]:
    ensure_saved_views_dir()
    return sorted(
        [path for path in SAVED_VIEWS_DIR.glob("*.json") if path.name != AUTOSAVE_PATH.name],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_autosave() -> WorkspaceState | None:
    if not AUTOSAVE_PATH.exists():
        return None
    return load_view(AUTOSAVE_PATH)


def delete_view(path: Path) -> None:
    if path.exists() and path.resolve().parent == ensure_saved_views_dir().resolve():
        path.unlink()


def duplicate_view(path: Path) -> Path:
    state = load_view(path)
    state.id = ""
    state.id = WorkspaceState().id
    state.name = f"{state.name} Copy"
    state.timestamp = utc_now()
    return save_view(state)


def rename_view(path: Path, new_name: str) -> Path:
    state = load_view(path)
    old_path = path
    state.name = new_name
    new_path = save_view(state)
    if old_path.exists() and old_path != new_path:
        old_path.unlink()
    return new_path


def export_view(path: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def import_view(source: Path) -> Path:
    state = load_view(source)
    return save_view(state)

