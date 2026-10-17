"""Run the full pipeline: fetch, rebuild, convert."""

from .convert import convert
from .fetch import fetch
from .rebuild import rebuild
from .paths import FILES_PDF


def main() -> None:
    print("Fetching xochitl from the reMarkable...")
    fetch()
    print("Rebuilding the visible folder tree...")
    rebuild()
    print("Converting notebooks to PDF...")
    convert()
    print(f"Done. See {FILES_PDF}/")


if __name__ == "__main__":
    main()
