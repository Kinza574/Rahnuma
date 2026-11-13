"""Dev tool: extract text from an admission PDF so it can be checked by hand.

Usage: python tools/pdf_text.py input.pdf output.txt  (needs requirements-dev.txt)
"""
import sys
from pypdf import PdfReader
src, out = sys.argv[1], sys.argv[2]
r = PdfReader(src)
with open(out, "w", encoding="utf-8") as f:
    for i, p in enumerate(r.pages):
        f.write(f"\n=== page {i+1} ===\n")
        f.write(p.extract_text() or "")
print(len(r.pages), "pages")
