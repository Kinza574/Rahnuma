"""Build docs/code_explanation.pdf live from the code.

Contents: title page, components, file tree, every module's docstring and functions
(read with ast), the full rule table, thresholds with sources, and sample results
produced by running the engine.

Usage: python tools/make_pdf.py
"""

import ast
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.conditions import count_leaves  # noqa: E402
from engine.consult import complete_answers, load_samples, run_consultation  # noqa: E402
from knowledge_base.kb_loader import load_kb  # noqa: E402

ACCENT = colors.HexColor("#7A2E3A")
LINE = colors.HexColor("#E4DED6")
SOFT = colors.HexColor("#F3E9E8")
OUT = ROOT / "docs" / "code_explanation.pdf"

styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Times-Bold", textColor=ACCENT, fontSize=18, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Times-Bold", fontSize=13, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.5, leading=9.5)
CODE = ParagraphStyle("code", parent=BODY, fontName="Courier", fontSize=7.5, leading=9.5)
TITLE = ParagraphStyle("title", parent=H1, fontSize=30, leading=36, spaceAfter=14)

# characters the built-in PDF fonts cannot draw
REPLACE = {"→": "->", "≥": ">=", "≤": "<=", "×": "x", "✓": "v", "–": "-"}


def clean(text):
    text = str(text)
    for a, b in REPLACE.items():
        text = text.replace(a, b)
    return escape(text)


def p(text, style=BODY):
    return Paragraph(clean(text), style)


def table(rows, widths, header=True, font=SMALL):
    data = [[p(c, font) for c in r] for r in rows]
    t = LongTable(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SOFT)]
    t.setStyle(TableStyle(style))
    return t


def file_tree():
    lines = []
    for folder in ["", "knowledge_base", "engine", "ui", "views", "samples", "tests", "tools"]:
        base = ROOT / folder if folder else ROOT
        files = sorted(f.name for f in base.iterdir() if f.is_file() and f.suffix in (".py", ".json", ".md", ".txt", ".toml", ".ini"))
        lines.append(f"{folder + '/' if folder else './'}")
        lines += [f"    {f}" for f in files]
    return "<br/>".join(clean(x).replace(" ", "&nbsp;") for x in lines)


def module_info(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree) or ""
    funcs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            first = (ast.get_docstring(node) or "").split("\n")[0]
            funcs.append((f"{kind} {node.name}", first))
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        funcs.append((f"    {node.name}.{sub.name}", (ast.get_docstring(sub) or "").split("\n")[0]))
    return doc, funcs


def build():
    kb = load_kb()
    counts = kb.counts()
    story = []
    W = landscape(A4)[0] - 30 * mm

    story += [Spacer(1, 40 * mm), p("Rahnuma", TITLE), p("University Field Advisor — code explanation", H2),
              Spacer(1, 6 * mm),
              p(f"A rule-based expert system with its own forward-chaining engine and MYCIN certainty factors. "
                f"{counts['total']} rules ({counts['compute']} compute, {counts['decision']} decision), "
                f"{counts['leaf_conditions']} leaf conditions."),
              p(f"Generated from the code on {date.today().isoformat()}. Data as of {kb.universities['as_of']}."),
              PageBreak()]

    story.append(p("1. Expert-system components", H1))
    comps = [["Component", "Files", "What it does"],
             ["Knowledge base", "knowledge_base/*.json, kb_loader.py", "Rules, thresholds, questions, fields, universities and market data as data."],
             ["Working memory", "engine/working_memory.py", "Facts (name, value, CF, source rules) for one consultation."],
             ["Inference engine", "engine/inference.py, conditions.py, actions.py", "Forward chaining: match, conflict resolution (priority, specificity, ID), refraction, cycle cap."],
             ["Explanation facility", "engine/explanation.py", "Why-asking text, plain-English trace, reasons, summary."],
             ["Knowledge acquisition", "views/knowledge_acquisition.py", "Edit and check thresholds and data; download / upload JSON."],
             ["User interface", "app.py, views/, ui/", "Streamlit pages; they only call run_consultation()."]]
    story.append(table(comps, [0.18 * W, 0.3 * W, 0.52 * W], font=BODY))
    story.append(p("2. File tree", H1))
    story.append(Paragraph(file_tree(), CODE))
    story.append(PageBreak())

    story.append(p("3. Modules and functions", H1))
    for folder in ["knowledge_base", "engine", "ui", "views", "tools"]:
        for path in sorted((ROOT / folder).glob("*.py")):
            if path.name == "__init__.py":
                continue
            doc, funcs = module_info(path)
            story.append(p(f"{folder}/{path.name}", H2))
            if doc:
                story.append(p(doc.split("\n\n")[0].replace("\n", " ")))
            if funcs:
                story.append(table([["Function / class", "First line of its docstring"]] + [[a, b or "-"] for a, b in funcs],
                                   [0.3 * W, 0.7 * W]))
    story.append(PageBreak())

    story.append(p("4. All rules (from rules.json)", H1))
    rows = [["ID", "Group", "Type", "Prio", "CF", "Cond.", "Rule"]]
    for r in kb.rules:
        rows.append([r["id"] + (" (schema)" if r.get("for_each") else ""), f"{r['group']} {r['group_name']}", r["type"],
                     str(r["priority"]), str(r["cf"]), str(count_leaves(r["if"])), r["text"]])
    story.append(table(rows, [0.08 * W, 0.13 * W, 0.07 * W, 0.04 * W, 0.08 * W, 0.04 * W, 0.56 * W]))
    story.append(PageBreak())

    story.append(p("5. Thresholds and sources (thresholds.json)", H1))
    rows = [["Key", "Value", "Unit", "Source", "Note"]]
    for k, v in kb.thresholds.items():
        rows.append([k, str(v["value"]), v.get("unit", ""), v.get("source", ""), v.get("note", "")])
    story.append(table(rows, [0.13 * W, 0.12 * W, 0.07 * W, 0.38 * W, 0.30 * W]))
    story.append(PageBreak())

    story.append(p("6. Sample results (produced by running the engine)", H1))
    for s in load_samples():
        r = run_consultation(complete_answers(s["answers"], kb), kb)
        story.append(p(f"{s['name']} — {s['blurb']}", H2))
        story.append(p("Expected: " + s["expected"], SMALL))
        story.append(p("Summary: " + r.summary))
        rows = [["#", "Field", "Status", "CF", "Word", "Universities listed"]]
        for i, t in enumerate(r.top, 1):
            n = len(r.universities.get(t["id"], {}).get("items", []))
            rows.append([str(i), t["name"], t["status"], f"{t['cf']:.3f}", t["label"], str(n)])
        story.append(table(rows, [0.04 * W, 0.3 * W, 0.14 * W, 0.08 * W, 0.12 * W, 0.16 * W]))
        if r.warnings:
            story.append(p("Warnings: " + "; ".join(r.warnings), SMALL))
        story.append(p(f"Engine cycles: {len(r.trace)}", SMALL))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6B645C"))
        canvas.drawString(15 * mm, 8 * mm, "Rahnuma — code explanation. For guidance only — always confirm admission criteria with the university.")
        canvas.drawRightString(landscape(A4)[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    OUT.parent.mkdir(exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm, title="Rahnuma code explanation")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    print(f"Wrote {build()}")
