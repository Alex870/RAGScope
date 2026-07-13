from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import chromadb


def resolve_chroma_path(path: Path) -> tuple[Path, dict[str, Any]]:
    """Accept either a Chroma root or a parent folder containing a `chroma/` child."""
    if path.is_file() and path.name.casefold() == "chroma.sqlite3":
        parent = path.parent
        validation = validate_chroma_path(parent)
        return parent, {**validation, "requested_path": str(path), "message": "SQLite file selected; using its containing Chroma folder."}
    validation = validate_chroma_path(path)
    if validation["valid"]:
        return path, validation
    child = path / "chroma"
    child_validation = validate_chroma_path(child)
    if child_validation["valid"]:
        return child, {
            **child_validation,
            "message": "Valid ChromaDB folder found in the chroma subfolder.",
            "requested_path": str(path),
        }
    return path, validation


def validate_chroma_path(path: Path) -> dict[str, Any]:
    """Return a UI-friendly validation record for a candidate Chroma directory."""
    if not path.exists():
        return {"valid": False, "message": "The folder does not exist."}
    if not path.is_dir():
        return {"valid": False, "message": "The path is not a folder."}
    try:
        has_contents = any(path.iterdir())
    except OSError as exc:
        return {"valid": False, "message": f"The folder could not be read: {exc}"}
    if not has_contents:
        return {"valid": False, "message": "The folder exists but is empty."}
    if not (path / "chroma.sqlite3").exists():
        return {"valid": False, "message": "No chroma.sqlite3 file was found in this folder."}
    return {"valid": True, "message": "Valid ChromaDB folder."}


def read_collection_names_from_sqlite(path: Path) -> list[str]:
    """Fallback collection discovery when the Chroma client cannot inspect the database."""
    sqlite_path = path / "chroma.sqlite3"
    if not sqlite_path.exists():
        return []
    try:
        with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as connection:
            cursor = connection.execute("SELECT name FROM collections ORDER BY name")
            return [str(row[0]) for row in cursor.fetchall() if row and row[0]]
    except Exception:
        return []


def collection_signature(path: Path, collection_name: str) -> dict[str, Any]:
    """Fingerprint the loaded collection so projection and dataset caches stay coherent."""
    sqlite_path = path / "chroma.sqlite3"
    try:
        count = chromadb.PersistentClient(path=str(path)).get_collection(collection_name).count()
    except Exception:
        count = None
    sqlite_stat = sqlite_path.stat()
    return {
        "path": str(path.resolve()),
        "sqlite_size": sqlite_stat.st_size,
        "collection": collection_name,
        "count": count,
    }
