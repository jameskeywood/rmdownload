"""Stage 3: copy the visible tree and render notebooks to PDF.

data/files_pdf mirrors data/files exactly, with a PDF added next to each
notebook bundle.  Each notebook's pages are read with rmscene, converted to
SVG with rmc's exporter (patched in render.py for svglib compatibility), and
drawn into a single PDF with svglib/reportlab.
"""

import io
import json
import shutil
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from rmscene import read_tree
from svglib.svglib import svg2rlg

from .paths import FILES, FILES_PDF
from .render import tree_to_svg


def render_notebook(bundle: Path) -> None:
    uuid = next(bundle.glob("*.metadata")).stem
    content = json.loads((bundle / f"{uuid}.content").read_text())
    page_ids = [page["id"] for page in content.get("cPages", {}).get("pages", [])]

    pdf = canvas.Canvas(str(bundle.with_suffix(".pdf")))
    for page_id in page_ids:
        page = bundle / uuid / f"{page_id}.rm"
        if not page.exists():
            continue
        with page.open("rb") as f:
            tree = read_tree(f)
        svg = io.StringIO()
        tree_to_svg(tree, svg)
        drawing = svg2rlg(io.BytesIO(svg.getvalue().encode()))
        pdf.setPageSize((drawing.width, drawing.height))
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.showPage()
    pdf.save()


def convert() -> None:
    if FILES_PDF.exists():
        shutil.rmtree(FILES_PDF)
    shutil.copytree(FILES, FILES_PDF)

    for bundle in sorted(FILES_PDF.rglob("*.rmdoc")):
        print(f"  {bundle.with_suffix('.pdf').relative_to(FILES_PDF)}")
        render_notebook(bundle)
