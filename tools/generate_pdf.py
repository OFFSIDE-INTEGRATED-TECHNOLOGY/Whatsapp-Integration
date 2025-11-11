"""
generate_pdf.py
Generates a PDF that contains the repository files and contents. Use this script after you
create the files on disk in the repository root.

Usage:
    pip install reportlab
    python tools/generate_pdf.py

Output:
    whatsapp_integration_repo.pdf
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "whatsapp_integration_repo.pdf"
EXCLUDE = {"venv", ".git", "node_modules", "__pycache__", "dist", "build"}

def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if any(part in EXCLUDE for part in p.parts):
            continue
        if p.is_file():
            yield p.relative_to(root)

def draw_file(c, filepath, y_pos, max_width, root):
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.5*inch, y_pos, str(filepath))
    y_pos -= 12
    c.setFont("Helvetica", 8)
    fullpath = root / filepath
    try:
        text = fullpath.read_text(encoding="utf-8")
    except Exception as e:
        text = f"<could not read file: {e}>"
    wrapped = []
    for line in text.splitlines():
        wrapped.extend(textwrap.wrap(line, width=120) or [""])
    for line in wrapped:
        if y_pos < 0.75*inch:
            c.showPage()
            y_pos = 10*inch
            c.setFont("Helvetica", 8)
        c.drawString(0.5*inch, y_pos, line)
        y_pos -= 10
    y_pos -= 6
    return y_pos

def main():
    c = canvas.Canvas(str(OUT), pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.5*inch, height - 0.5*inch, "whatsapp_integration repository snapshot")
    y = height - 0.75*inch
    for fp in iter_files(ROOT):
        # skip the generated PDF if already exists
        if str(fp).endswith("whatsapp_integration_repo.pdf"):
            continue
        y -= 6
        y = draw_file(c, fp, y, width - inch, ROOT)
    c.save()
    print("PDF generated at:", OUT)

if __name__ == "__main__":
    main()
