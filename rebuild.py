"""
Rebuild the visible reMarkable folder tree from a flat xochitl directory.

The reMarkable stores everything as UUID-named files in a single flat folder.
Folder hierarchy lives inside each item's .metadata file (visibleName + parent).
This script reads that metadata, rebuilds the folder tree, and copies only the
file types listed in KEEP_EXTENSIONS, renamed to their visibleName.
"""

import argparse
import json
import re
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Only files with these extensions will be copied. Everything else (metadata,
# pagedata, the raw page directory, thumbnails, …) is skipped.
# ---------------------------------------------------------------------------
KEEP_EXTENSIONS = (".pdf", ".epub")


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


def visible_path(uuid: str, items: dict[str, dict]) -> Path:
    """Return the visible folder path for a UUID by walking parent links."""
    parts: list[str] = []
    seen: set[str] = set()
    while uuid and uuid not in seen:
        seen.add(uuid)
        meta = items.get(uuid)
        if meta is None:
            break
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


def copy_item_files(
    source: Path, dest: Path, uuid: str, visible_name: str, used: set[str]
) -> None:
    """Copy the kept files belonging to a UUID, renamed to visibleName.<ext>."""
    dest.mkdir(parents=True, exist_ok=True)
    for path in source.glob(f"{uuid}*"):
        if path.name != uuid and not path.name.startswith(f"{uuid}."):
            continue
        if path.suffix not in KEEP_EXTENSIONS:
            continue
        suffix = path.name[len(uuid):]
        new_name = unique_name(f"{visible_name}{suffix}", used)
        shutil.copy2(path, dest / new_name)


def reconstruct(source: Path, output: Path) -> None:
    items = load_metadata(source)
    if not items:
        raise SystemExit(
            f"No .metadata files found in {source.resolve()}\n"
            f"Did you mean to pass the xochitl folder? e.g.  rebuild.py xochitl"
        )

    # Track names per destination folder to detect sibling collisions.
    used_by_folder: dict[Path, set[str]] = {}

    def used_in(folder: Path) -> set[str]:
        return used_by_folder.setdefault(folder, set())

    # 1. Create the real folders (CollectionType).
    for uuid, meta in items.items():
        if meta.get("type") != "CollectionType":
            continue
        parent_uuid = meta.get("parent") or ""
        parent_path = visible_path(parent_uuid, items) if parent_uuid else Path()
        name = unique_name(
            sanitize(meta.get("visibleName") or uuid),
            used_in(parent_path),
        )
        (output / parent_path / name).mkdir(parents=True, exist_ok=True)

    # 2. Copy each document's kept files into its parent folder, renamed.
    for uuid, meta in items.items():
        if meta.get("type") != "DocumentType":
            continue
        parent_uuid = meta.get("parent") or ""
        parent_path = visible_path(parent_uuid, items) if parent_uuid else Path()
        visible_name = sanitize(meta.get("visibleName") or uuid)
        copy_item_files(
            source,
            output / parent_path,
            uuid,
            visible_name,
            used_in(parent_path),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Folder containing the xochitl files (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("remarkable"),
        help="Destination folder, relative to cwd (default: ./remarkable)",
    )
    args = parser.parse_args()

    source = args.source
    if source == Path(".") and not any(source.glob("*.metadata")):
        candidate = source / "xochitl"
        if candidate.is_dir() and any(candidate.glob("*.metadata")):
            source = candidate

    if not source.is_dir():
        parser.error(f"Source is not a directory: {source}")

    reconstruct(source, args.output)
    print(f"Done → {args.output.resolve()}")


if __name__ == "__main__":
    main()
