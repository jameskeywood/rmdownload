# rmdownload

Download files from reMarkable 2 paper tablet.

## Usage

```bash
nix develop
uv sync
uv run rmdownload
```

With the tablet connected over USB, this runs all three stages:

1. `data/raw/xochitl/` — verbatim mirror of the device, via rsync
2. `data/files/` — visible folder tree: PDFs, EPUBs, and notebooks
3. `data/files_pdf/` — same tree with a PDF rendered next to each notebook

Set `RM_HOST` to use a different address (default `10.11.99.1`, the USB address).
