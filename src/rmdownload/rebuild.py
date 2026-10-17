"""Stage 2: rebuild the visible folder tree from the flat xochitl mirror.

The reMarkable stores everything as UUID-named files in one flat folder.
The folder hierarchy lives in each item's .metadata file, so this stage
walks those parent links and recreates the tree under data/files using
visible names.

PDF and EPUB documents keep their original format, renamed to the visible
name.  Notebooks are copied as <visibleName>.rmdoc/ bundles with the raw
UUID filenames preserved, so the convert stage can render them later.
"""

import json
import re
import shutil
from pathlib import Path

from .paths import FILES, RAW

ORIGINAL_EXTENSIONS = (".pdf", ".epub")


def sanitize(name: str) -> str:
    """Make a visibleName safe for use as a filesystem name."""
    cleaned = re.sub(r'[/\\\x00-\x1f]', "_", name).strip()
    return cleaned or "untitled"


def load_metadata(source: Path) -> dict[str, dict]:
    """Read every *.metadata file into a {uuid: metadata} mapping."""
    items: dict[str, dict] = {}
    for meta_file in source.glob("*.metadata"):
        try:
            data = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("deleted"):
            continue
        items[meta_file.stem] = data
    return items


def visible_path(uuid: str, items: dict[str, dict]) -> Path | None:
    """Return the visible folder path for a UUID by walking parent links.

    Returns None for items that are unreachable from the tablet's root:
    anything in the trash (parent == "trash") or with a broken parent chain.
    """
    parts: list[str] = []
    seen: set[str] = set()
    while uuid:
        if uuid == "trash" or uuid in seen:
            return None
        seen.add(uuid)
        meta = items.get(uuid)
        if meta is None:
            return None
        parts.append(sanitize(meta.get("visibleName") or uuid))
        uuid = meta.get("parent") or ""
    return Path(*reversed(parts))


def unique_name(name: str, used: set[str]) -> str:
    """Return a name that isn't already in `used`, adding a numeric suffix."""
    if name not in used:
        used.add(name)
        return name
    stem, dot, ext = name.partition(".")
    counter = 1
    while True:
        candidate = f"{stem} ({counter}){dot}{ext}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


def copy_original(
    source: Path, dest: Path, uuid: str, visible_name: str, used: set[str]
) -> bool:
    """Copy a PDF or EPUB, renamed to its visible name."""
    originals = [
        path
        for path in source.glob(f"{uuid}.*")
        if path.is_file() and path.suffix in ORIGINAL_EXTENSIONS
    ]
    for path in originals:
        suffix = path.name[len(uuid):]
        shutil.copy2(path, dest / unique_name(f"{visible_name}{suffix}", used))
    return bool(originals)


def copy_notebook(
    source: Path, dest: Path, uuid: str, visible_name: str, used: set[str]
) -> None:
    """Copy a notebook into <visibleName>.rmdoc/ preserving raw filenames."""
    bundle = dest / unique_name(f"{visible_name}.rmdoc", used)
    bundle.mkdir()
    for path in source.glob(f"{uuid}.*"):
        if path.is_file():
            shutil.copy2(path, bundle / path.name)
    pages = source / uuid
    if pages.is_dir():
        shutil.copytree(pages, bundle / uuid)


def reconstruct(source: Path, output: Path) -> None:
    items = load_metadata(source)
    if not items:
        raise SystemExit(
            f"No .metadata files found in {source}\n"
            f"Did the fetch stage run?  Is the device connected?"
        )

    used_by_folder: dict[Path, set[str]] = {}

    def used_in(folder: Path) -> set[str]:
        return used_by_folder.setdefault(folder, set())

    for uuid, meta in items.items():
        if meta.get("type") != "CollectionType":
            continue
        parent_path = visible_path(meta.get("parent") or "", items)
        if parent_path is None:
            continue
        name = unique_name(
            sanitize(meta.get("visibleName") or uuid),
            used_in(parent_path),
        )
        (output / parent_path / name).mkdir(parents=True, exist_ok=True)

    for uuid, meta in items.items():
        if meta.get("type") != "DocumentType":
            continue
        parent_path = visible_path(meta.get("parent") or "", items)
        if parent_path is None:
            continue
        dest = output / parent_path
        dest.mkdir(parents=True, exist_ok=True)
        visible_name = sanitize(meta.get("visibleName") or uuid)
        used = used_in(parent_path)
        if not copy_original(source, dest, uuid, visible_name, used):
            copy_notebook(source, dest, uuid, visible_name, used)


def rebuild() -> None:
    if FILES.exists():
        shutil.rmtree(FILES)
    reconstruct(RAW, FILES)
