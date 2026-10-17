"""Shared paths for the pipeline stages."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # <repo>/src/rmdownload/paths.py -> <repo>
DATA = ROOT / "data"
RAW = DATA / "raw" / "xochitl"
FILES = DATA / "files"
FILES_PDF = DATA / "files_pdf"
