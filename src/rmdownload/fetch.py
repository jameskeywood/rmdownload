"""Stage 1: mirror the device's xochitl folder into data/raw/xochitl."""

import os
import subprocess

from .paths import RAW

HOST = os.environ.get("RM_HOST", "10.11.99.1")
REMOTE = f"root@{HOST}:/home/root/.local/share/remarkable/xochitl/"
EXCLUDES = ("*.thumbnails", "*.cache", "*.highlights")


def fetch() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "rsync",
            "-az",
            "--delete",
            *(f"--exclude={pattern}" for pattern in EXCLUDES),
            REMOTE,
            f"{RAW}/",
        ],
        check=True,
    )
