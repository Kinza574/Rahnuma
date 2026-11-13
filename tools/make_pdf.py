"""Build the code explanation PDF live from the code.

Usage: python tools/make_pdf.py [output.pdf]   (default: docs/code_explanation.pdf)
"""

import ast
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle, XPreformatted)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.conditions import count_leaves  # noqa: E402
from engine.consult import complete_answers, load_samples, run_consultation  # noqa: E402
from knowledge_base.kb_loader import load_kb  # noqa: E402

MAROON = colors.HexColor("#7A2E3A")
GREY = colors.HexColor("#595959")
LINE = colors.HexColor("#BFBFBF")
CODE_NUM = colors.HexColor("#8C8C8C")


def register_fonts():
    """Use Calibri, Cambria and Consolas when Windows fonts exist; otherwise built-in fonts."""
    fdir = Path("C:/Windows/Fonts")
    try:
        pdfmetrics.registerFont(TTFont("Calibri", str(fdir / "calibri.ttf")))
        pdfmetrics.registerFont(TTFont("Calibri-Bold", str(fdir / "calibrib.ttf")))
        pdfmetrics.registerFont(TTFont("Calibri-Italic", str(fdir / "calibrii.ttf")))
        pdfmetrics.registerFont(TTFont("Calibri-BoldItalic", str(fdir / "calibriz.ttf")))
        pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold",
                                      italic="Calibri-Italic", boldItalic="Calibri-BoldItalic")
        pdfmetrics.registerFont(TTFont("Cambria", str(fdir / "cambria.ttc"), subfontIndex=0))
        pdfmetrics.registerFont(TTFont("Cambria-Bold", str(fdir / "cambriab.ttf")))
        pdfmetrics.registerFontFamily("Cambria", normal="Cambria", bold="Cambria-Bold",
                                      italic="Cambria", boldItalic="Cambria-Bold")
        pdfmetrics.registerFont(TTFont("Consolas", str(fdir / "consola.ttf")))
        return "Calibri", "Cambria-Bold", "Consolas"
    except Exception:
        return "Helvetica", "Times-Bold", "Courier"


BODY_FONT, HEAD_FONT, CODE_FONT = register_fonts()
BODY = ParagraphStyle("body", fontName=BODY_FONT, fontSize=10.5, leading=14, alignment=TA_JUSTIFY, spaceAfter=5)
BODY_L = ParagraphStyle("bodyl", parent=BODY, alignment=TA_LEFT)
BULLET = ParagraphStyle("bullet", parent=BODY_L, leftIndent=14, bulletIndent=4, spaceAfter=2)
SMALL = ParagraphStyle("small", parent=BODY_L, fontSize=9, leading=11.5, spaceAfter=0)
SMALL_W = ParagraphStyle("smallw", parent=SMALL, textColor=colors.white, fontName=BODY_FONT + ("-Bold" if BODY_FONT == "Calibri" else ""))
CAPTION = ParagraphStyle("cap", parent=SMALL, fontName=BODY_FONT + ("-Italic" if BODY_FONT == "Calibri" else ""),
                         textColor=GREY, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8)
H1 = ParagraphStyle("H1", fontName=HEAD_FONT, fontSize=16, leading=20, textColor=MAROON, spaceBefore=14, spaceAfter=8, keepWithNext=1)
H2 = ParagraphStyle("H2", fontName=HEAD_FONT, fontSize=12.5, leading=16, textColor=MAROON, spaceBefore=10, spaceAfter=5, keepWithNext=1)
H3 = ParagraphStyle("H3", fontName=HEAD_FONT, fontSize=11, leading=14, textColor=colors.black, spaceBefore=8, spaceAfter=3, keepWithNext=1)
CODE = ParagraphStyle("code", fontName=CODE_FONT, fontSize=7.8, leading=9.6)

MAX_CODE_CHARS = 92


def curly(text):
    """Straight quotes to curly quotes (not used for code)."""
    t = re.sub(r'"([^"]*)"', "\u201c\\1\u201d", str(text))
    t = re.sub(r"(^|[\s(])'", "\\1\u2018", t)
    return t.replace("'", "\u2019")


def P(text, style=BODY):
    """Paragraph from plain text with **bold** spans."""
    t = escape(curly(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return Paragraph(t, style)


def bullets(items):
    return [Paragraph(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(curly(i))), BULLET, bulletText="\u2022") for i in items]


def table(rows, widths, font=SMALL, keep=True):
    data = [[Paragraph(escape(curly(c)), SMALL_W if i == 0 else font) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MAROON),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return KeepTogether([t, Spacer(1, 6)]) if keep else t


def code_block(lines, first_no, caption=None):
    """Code with real line numbers in a thin grey box; long lines wrap with an indent."""
    out = []
    for i, line in enumerate(lines):
        no = f"{first_no + i:>4}"
        indent = " " * (len(line) - len(line.lstrip()) + 4)
        first, rest = line[:MAX_CODE_CHARS], line[MAX_CODE_CHARS:]
        out.append(f'<font color="#8C8C8C">{no}</font>  {escape(first)}')
        while rest:  # wrap long lines, indented under the original line
            cut = MAX_CODE_CHARS - len(indent)
            part, rest = rest[:cut], rest[cut:]
            out.append("      " + escape(indent + part))
    x = XPreformatted("\n".join(out), CODE)
    t = Table([[x]], colWidths=[W])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    parts = [t]
    if caption:
        parts.append(P(caption, CAPTION))
    else:
        parts.append(Spacer(1, 6))
    return KeepTogether(parts)


def source_of(rel, name, start=None, end=None, max_lines=20):
    """Lines of a function/class from a file, with the real first line number."""
    path = ROOT / rel
    src = path.read_text(encoding="utf-8").split("\n")
    tree = ast.parse("\n".join(src))
    node = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name:
            node = n
            break
    lo, hi = node.lineno, node.end_lineno
    body = src[lo - 1:hi]
    if start:
        i = next(k for k, l in enumerate(body) if start in l)
        body, lo = body[i:], lo + i
    if end:
        j = next(k for k, l in enumerate(body) if end in l)
        body = body[:j + 1]
    return body[:max_lines], lo


def functions_of(rel):
    """(name, first docstring line) for top-level functions/classes and class methods."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    rows = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            if n.name.startswith("_") and not ast.get_docstring(n):
                continue
            rows.append([n.name + ("()" if isinstance(n, ast.FunctionDef) else ""), (ast.get_docstring(n) or "").split("\n")[0] or "Helper."])
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef) and not m.name.startswith("__"):
                        rows.append([f"{n.name}.{m.name}()", (ast.get_docstring(m) or "").split("\n")[0] or "Helper."])
    return rows


def module_doc(rel):
    return (ast.get_docstring(ast.parse((ROOT / rel).read_text(encoding="utf-8"))) or "").split("\n")[0]


def func_table(rel, limit=14):
    rows = functions_of(rel)[:limit]
    return table([["Function / class", "Purpose"]] + rows, [0.32 * W, 0.68 * W])


# ---------------------------------------------------------------- page layout
PAGE_W, PAGE_H = A4
M = 2.54 * cm
W = PAGE_W - 2 * M


class NumberedCanvas(canvas.Canvas):
    """Canvas that knows the total page count, for 'Page X of Y'."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.draw_frame_text(total)
            super().showPage()
        super().save()

    def draw_frame_text(self, total):
        page = self._pageNumber
        self.setFont(BODY_FONT, 8.5)
        self.setFillColor(GREY)
        self.drawCentredString(PAGE_W / 2, 1.3 * cm, f"Page {page} of {total}")
        if page > 1:
            self.drawRightString(PAGE_W - M, PAGE_H - 1.5 * cm, "Rahnuma \u2013 Code Explanation")
            self.setStrokeColor(LINE)
            self.setLineWidth(0.4)
            self.line(M, PAGE_H - 1.65 * cm, PAGE_W - M, PAGE_H - 1.65 * cm)


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                         title="Rahnuma \u2013 Code Explanation", author="Owais")
        frame = Frame(M, M, W, PAGE_H - 2 * M, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="title", frames=[frame]), PageTemplate(id="body", frames=[frame])])

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H2"):
            level = 0 if f.style.name == "H1" else 1
            text = f.getPlainText()
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))


# ---------------------------------------------------------------- facts from the project
def app_url():
    m = re.search(r'APP_URL = "([^"]*)"', (ROOT / "ui" / "theme.py").read_text(encoding="utf-8"))
    return m.group(1) if m and m.group(1) else ""


def test_count():
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], cwd=ROOT,
                         capture_output=True, text=True).stdout
    m = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    return (int(m.group(1)) if m else 0), (int(failed.group(1)) if failed else 0)


ZIP_A_FILES = {
    "app.py": "Entry point: page setup and the top navigation.",
    "requirements.txt": "Pinned packages (Streamlit, pandas, reportlab, pytest).",
    "README.md": "What the project is, how to run it and how to deploy it.",
    ".streamlit/config.toml": "Theme: maroon accent, serif headings, light background.",
    "knowledge_base/rules.json": "The 90 rules as data.",
    "knowledge_base/thresholds.json": "Every number the rules use, with source and as-of date.",
    "knowledge_base/questions.json": "The questions, answer options, steps and ask_if conditions.",
    "knowledge_base/fields.json": "The 18 fields: requirements, tests, alternatives, aptitudes.",
    "knowledge_base/universities.json": "Universities and their programme offerings.",
    "knowledge_base/market_data.json": "Job demand in Pakistan and abroad per field.",
    "samples/sample_students.json": "Five sample students with expected results.",
    "tools/make_pdf.py": "Builds this code explanation PDF from the code.",
}


def tree_rows():
    files = []
    for rel in ["app.py", "requirements.txt", "README.md", ".streamlit/config.toml"]:
        files.append(rel)
    for folder, pat in (("knowledge_base", "*"), ("engine", "*.py"), ("ui", "*.py"), ("views", "*.py"),
                        ("samples", "*.json"), ("tests", "*.py")):
        files += [f"{folder}/{p.name}" for p in sorted((ROOT / folder).glob(pat)) if p.is_file() and p.suffix in (".py", ".json")]
    files.append("tools/make_pdf.py")
    rows = [["File", "What it does"]]
    for f in files:
        desc = ZIP_A_FILES.get(f)
        if desc is None and f.endswith(".py"):
            desc = module_doc(f) or ("Package marker." if f.endswith("__init__.py") else "")
        rows.append(["Rahnuma/" + f, desc or ""])
    return rows


# ---------------------------------------------------------------- build
def build(out_path):
    kb = load_kb()
    counts = kb.counts()
    url = app_url()
    link = url or "https://______.streamlit.app"
    n_tests, n_failed = test_count()
    samples = load_samples()
    results = {s["name"]: run_consultation(complete_answers(s["answers"], kb), kb) for s in samples}
    offs = [o for u in kb.universities["universities"] for o in u["offerings"]]

    s = []
    # ---- title page
    s += [Spacer(1, 5 * cm),
          Paragraph("Rahnuma \u2013 University Field Advisor", ParagraphStyle("t", fontName=HEAD_FONT, fontSize=26, leading=32, textColor=MAROON, alignment=TA_CENTER)),
          Spacer(1, 0.4 * cm),
          Paragraph("Code Explanation", ParagraphStyle("st", fontName=HEAD_FONT.replace("-Bold", ""), fontSize=16, leading=20, alignment=TA_CENTER)),
          Spacer(1, 1.6 * cm)]
    centre = ParagraphStyle("c", parent=BODY, alignment=TA_CENTER, fontSize=12, leading=16)
    s += [Paragraph("Introduction to Artificial Intelligence (IAI) \u2013 CCP", centre),
          Paragraph("NED University of Engineering &amp; Technology", centre), Spacer(1, 2 * cm)]
    info = [["Student name:", "Owais"], ["Roll No:", "________"], ["Submitted to:", "________"],
            ["Date:", date.today().strftime("%d %B %Y")]]
    lbl = ParagraphStyle("l", parent=BODY_L, fontSize=12, leading=16)
    rows = [[Paragraph(f"<b>{a}</b>", lbl), Paragraph(escape(b), lbl)] for a, b in info]
    rows.append([Paragraph("<b>Live app:</b>", lbl), Paragraph(f'<a href="{link}" color="#7A2E3A"><u>{escape(link)}</u></a>', lbl)])
    t = Table(rows, colWidths=[4 * cm, 9 * cm])
    t.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    s += [t, NextPageTemplate("body"), PageBreak()]

    # ---- contents
    s.append(Paragraph("Table of Contents", ParagraphStyle("toch", parent=H1, keepWithNext=0)))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc1", fontName=BODY_FONT, fontSize=10.5, leading=15, leftIndent=0),
                       ParagraphStyle("toc2", fontName=BODY_FONT, fontSize=10, leading=13.5, leftIndent=14)]
    toc.dotsMinLevel = 0
    s += [toc, PageBreak()]

    # ---- 1 overview
    s.append(Paragraph("1 Project Overview", H1))
    s.append(P("After Intermediate, most students in Pakistan choose a university field with little guidance. Each council "
               "(PMDC, PEC, HEC, PCATP) has its own rules, and entry tests such as MDCAT, ECAT, NET and LAT add more conditions. "
               "Rahnuma is a rule-based expert system that asks the student about marks, stream, interests, skills, tests and budget, "
               f"checks the admission rules, recommends up to three of {len(kb.fields)} fields and lists matching universities "
               f"from {len(kb.universities['universities'])} universities."))
    s.append(table([["Requirement", "Where it is in the code"],
                    ["Inferencing", "Own forward-chaining engine with MYCIN certainty factors (engine/inference.py)."],
                    ["Diagnosis", "Rule groups G1\u2013G4: answers \u2192 aptitude profile and eligibility gaps (Diagnosis section of the report)."],
                    ["Decision making", "G8 picks the top 3 fields; DS06 gives \u201cInsufficient data\u201d; G4 gives strict \u201cnot eligible\u201d verdicts."],
                    ["Decision support", "University filters, job outlook, action plan, alternatives and the What-if panel (views/result_view.py)."],
                    ["50+ conditions", f"{counts['total']} rules ({counts['compute']} compute, {counts['decision']} decision) with {counts['leaf_conditions']} leaf conditions."],
                    ["Streamlit UI", "Five pages in views/, top navigation in app.py."],
                    ["Live link", link + ("" if url else " (to be filled in after deployment)")]],
                   [0.25 * W, 0.75 * W]))

    # ---- 2 how to run
    s.append(Paragraph("2 How to Run", H1))
    s.append(Paragraph(f'Live app: <a href="{link}" color="#7A2E3A"><u>{escape(link)}</u></a>', BODY_L))
    s.append(P("To run it on a Windows computer, open PowerShell in the Rahnuma folder (Python 3.12 is needed):"))
    s.append(code_block([r"py -3.12 -m venv .venv", r".\.venv\Scripts\Activate.ps1", "pip install -r requirements.txt",
                         "streamlit run app.py", "pytest -q"], 1))
    s.append(P("If PowerShell blocks the activation script, run Set-ExecutionPolicy -Scope CurrentUser RemoteSigned once. "
               "The app opens at http://localhost:8501."))

    # ---- 3 folder structure
    s.append(Paragraph("3 Folder Structure", H1))
    s.append(P("These are the files in the submitted zip. The engine and the knowledge base do not use Streamlit, so they can be "
               "tested on their own."))
    s.append(table(tree_rows(), [0.42 * W, 0.58 * W], keep=False))

    # ---- 4 code explanation
    s.append(PageBreak())
    s.append(Paragraph("4 Code Explanation", H1))
    s.append(P("This section goes through the code in the order the data flows: knowledge base, working memory, conditions, "
               "inference engine, actions, certainty factors, explanation, the consult module, the user interface and the tests."))

    # 4.1 knowledge base
    s.append(Paragraph("4.1 Knowledge Base Files and kb_loader.py", H2))
    s.append(P("All knowledge is stored as JSON data, not inside Python code. Rules never contain numbers; they refer to keys "
               "such as @eng_min, and the value is read from thresholds.json. kb_loader.py reads the six files into one KB "
               "object and checks them (unique rule IDs, known threshold keys, thresholds in the right order)."))
    s.append(table([["File", "Contents"],
                    ["rules.json", f"{counts['total']} rules in nine groups (G0\u2013G8)."],
                    ["thresholds.json", f"{len(kb.thresholds)} values with unit, source and as-of date ({kb.data['thresholds']['as_of']})."],
                    ["questions.json", f"{len(kb.questions)} questions in {len(kb.steps)} steps, with ask_if conditions."],
                    ["fields.json", f"{len(kb.fields)} fields with requirements, entry test, alternatives and aptitudes."],
                    ["universities.json", f"{len(kb.universities['universities'])} universities, {len(offs)} offerings, {sum(o['verified'] for o in offs)} verified."],
                    ["market_data.json", f"Job demand in Pakistan and abroad for all {len(kb.market['fields'])} fields."]],
                   [0.28 * W, 0.72 * W]))
    s.append(func_table("knowledge_base/kb_loader.py"))
    rule = json.dumps(kb.rule_by_id["EL08"], indent=1, ensure_ascii=False).split("\n")
    rule = [l for l in rule if '"asks"' not in l]
    rule_text = rule[:20]
    s.append(code_block(rule_text, 1, "rules.json \u2013 rule EL08 (first 20 lines)"))
    s.append(P("A rule has an ID, a group, a priority, a CF and a plain-English text. The IF part is a small tree of all / any "
               "conditions; \"@eng_min\" means \u201cread eng_min from thresholds.json\u201d. The THEN part sets the eligibility "
               "of three fields. Because the rule is data, an expert can change it without touching the engine."))
    lines, lo = source_of("knowledge_base/kb_loader.py", "check_threshold_order", max_lines=16)
    s.append(code_block(lines, lo, "knowledge_base/kb_loader.py \u2013 order checks used by Knowledge Acquisition"))
    s.append(P("Before an expert\u2019s change is used, these checks run. If the bands are not in order or a CF is not between 0 "
               "and 1, the change is refused with a plain message."))

    # 4.2 working memory
    s.append(Paragraph("4.2 Working Memory (engine/working_memory.py)", H2))
    s.append(P("Working memory holds every fact known during one consultation. A fact has a name, a value, a certainty factor and "
               "the list of rules that produced it. Warnings, notes and the final decisions are also kept here."))
    s.append(func_table("engine/working_memory.py"))
    lines, lo = source_of("engine/working_memory.py", "add")
    s.append(code_block(lines, lo, "engine/working_memory.py \u2013 adding a fact"))
    s.append(P("If a fact already exists, a second rule is agreeing evidence, so the two CFs are combined with the MYCIN formula "
               "instead of the old value being overwritten."))

    # 4.3 conditions
    s.append(Paragraph("4.3 Conditions (engine/conditions.py)", H2))
    s.append(P("This file checks the IF part of a rule. The condition language is small on purpose: all, any, not, and leaf tests "
               "such as eq, in, gte, lt, between, exists and missing. It returns whether the condition is true, the CFs that go "
               "into min(), and the facts used (for the trace)."))
    s.append(func_table("engine/conditions.py", limit=10))
    lines, lo = source_of("engine/conditions.py", "evaluate", start='if "all" in cond', end="return Match(not m.ok)", max_lines=21)
    s.append(code_block(lines, lo, "engine/conditions.py \u2013 all, any and not"))
    s.append(P("For all, every part must be true and all their CFs are collected. For any, the strongest matching part is used. "
               "not is true when the inner part is false."))

    # 4.4 inference
    s.append(Paragraph("4.4 Inference Engine (engine/inference.py)", H2))
    s.append(P("This is the forward-chaining engine. Each cycle it finds the rules that match and have not fired yet, sorts them "
               "(conflict resolution), fires the first one, and records a trace step. It stops when nothing matches, when a rule "
               "says HALT, or at the max_cycles safety cap."))
    s.append(func_table("engine/inference.py"))
    lines, lo = source_of("engine/inference.py", "run", start="while True", max_lines=20)
    s.append(code_block(lines, lo, "engine/inference.py \u2013 the forward chaining loop"))
    s.append(P("fired holds every rule instance that has already fired; this is refraction, so no rule fires twice. The CF of "
               "the conclusion is the rule CF times the smallest CF of the matched facts."))
    lines, lo = source_of("engine/inference.py", "conflict_set", start="found, level")
    lines2, lo2 = source_of("engine/inference.py", "resolve_conflict", start="order = ")
    s.append(code_block(lines, lo, "engine/inference.py \u2013 matching from the highest priority level down"))
    s.append(code_block(lines2, lo2, "engine/inference.py \u2013 conflict resolution sorting"))
    s.append(P("Rules are checked from the highest priority down, and the search stops after the first level that has a match. "
               "This gives the same result as checking every rule: priority is the first sort key, so a lower rule could never "
               "win this cycle, and checking a condition never changes any fact. Inside the level, more conditions (specificity) "
               "and then the smaller rule ID decide."))

    # 4.5 actions
    s.append(Paragraph("4.5 Actions (engine/actions.py)", H2))
    s.append(P("Actions are the THEN part of rules. Each action is a small dict in rules.json, such as {\"assert\": \"apt_caring\"}, "
               "and a handler function carries it out: adding facts, setting eligibility, filtering universities, or making the "
               "final recommendation."))
    s.append(func_table("engine/actions.py", limit=16))
    halt = json.dumps({k: kb.rule_by_id["DS06"][k] for k in ("id", "group", "type", "priority", "cf", "if", "then")}, indent=1).split("\n")
    s.append(code_block(halt, 1, "rules.json \u2013 rule DS06 (data sufficiency HALT)"))
    lines, lo = source_of("engine/actions.py", "_halt")
    s.append(code_block(lines, lo, "engine/actions.py \u2013 the HALT action"))
    s.append(P("DS01\u2013DS05 have the highest priority (100) and add essential items that are missing. DS06 (priority 99) then "
               "fires if the missing list exists, sets the status to \u201cInsufficient data\u201d and halts the engine, so no "
               "confident result is ever given from empty input."))

    # 4.6 certainty
    s.append(Paragraph("4.6 Certainty Factors (engine/certainty.py)", H2))
    s.append(P("All CF maths is in this small file, so it is easy to test. CFs are between 0 and 1; there is no negative evidence."))
    s.append(func_table("engine/certainty.py"))
    lines, lo = source_of("engine/certainty.py", "combine")
    lines2, lo2 = source_of("engine/certainty.py", "conclude")
    s.append(code_block(lines + [""] + lines2, lo, "engine/certainty.py \u2013 MYCIN combine and rule conclusion"))
    s.append(P("Example: two agreeing pieces of evidence 0.6 and 0.5 give 0.6 + 0.5 \u00d7 (1 \u2212 0.6) = 0.8. "
               f"A \u201cNot sure\u201d answer has CF {kb.t('notsure_cf')}, so a rule still fires on it, at half the strength."))

    # 4.7 explanation
    s.append(Paragraph("4.7 Explanation Facility (engine/explanation.py)", H2))
    s.append(P("This file turns the engine\u2019s work into plain English: the \u201cWhy are you asking?\u201d note for each question, "
               "one sentence per trace step for \u201cHow the system reached this\u201d, the reasons on each recommended field and "
               "the 2\u20133 sentence summary."))
    s.append(func_table("engine/explanation.py"))
    lines, lo = source_of("engine/explanation.py", "why_asking")
    s.append(code_block(lines, lo, "engine/explanation.py \u2013 building \u201cWhy are you asking?\u201d"))
    s.append(P("Every rule lists the questions it uses (its asks list). The text simply names those rules and what their groups are for."))

    # 4.8 consult
    s.append(Paragraph("4.8 consult.py", H2))
    s.append(P("consult.py is the single entry point used by the pages: run_consultation(answers, kb). It turns answers into facts, "
               "runs the engine and packs everything the report needs into a Result object."))
    s.append(func_table("engine/consult.py"))
    lines, lo = source_of("engine/consult.py", "add_input")
    s.append(code_block(lines, lo, "engine/consult.py \u2013 answers become facts"))
    s.append(P("Yes becomes a fact with CF 1, Not sure a fact with CF 0.5, and No adds nothing. A blank box adds nothing (missing), "
               "but 0 is kept as real data."))

    # 4.9 UI
    s.append(Paragraph("4.9 User Interface (app.py, ui/, views/)", H2))
    s.append(P("The interface is Streamlit only. The pages never contain rules; they call run_consultation() and draw the Result. "
               "ui/theme.py holds the colours and small CSS, ui/components.py the reusable pieces (question cards, Yes / No / Not sure "
               "control, confidence bar) and ui/state.py the session state."))
    ui_rows = [["File", "Purpose"]] + [[f, module_doc(f)] for f in ["app.py", "ui/theme.py", "ui/components.py", "ui/state.py",
               "views/consultation.py", "views/quick_diagnosis.py", "views/result_view.py", "views/knowledge_base_view.py",
               "views/knowledge_acquisition.py", "views/about.py"]]
    s.append(table(ui_rows, [0.33 * W, 0.67 * W]))
    s.append(Paragraph("Guided Counselling (views/consultation.py)", H3))
    s.append(P("A six-step wizard. The step list is on the left and the questions are cards on the right. Next only moves on when "
               "every shown question is answered; skipped questions show \u201cSkipped because \u2026\u201d."))
    s.append(func_table("views/consultation.py", limit=10))
    s.append(Paragraph("Counsellor Desk (views/quick_diagnosis.py)", H3))
    s.append(P("All questions on one screen in tabs, with five sample students. Here the data-sufficiency rules decide what is missing."))
    s.append(Paragraph("Counselling report and What-if (views/result_view.py)", H3))
    s.append(func_table("views/result_view.py", limit=14))
    lines, lo = source_of("views/result_view.py", "what_if", start="after = run_consultation", max_lines=6)
    lines2, lo2 = source_of("views/result_view.py", "compare", start="b_top =", max_lines=10)
    s.append(code_block(lines, lo, "views/result_view.py \u2013 the What-if re-run"))
    s.append(code_block(lines2, lo2, "views/result_view.py \u2013 comparing before and after"))
    s.append(P("The What-if panel copies the answers, changes a few (marks, MDCAT, LAT, budget, sector, cities), runs the whole "
               "engine again and compares the fields, CFs and university counts. The saved answers only change if the student "
               "presses \u201cUse these answers\u201d."))
    s.append(Paragraph("Knowledge Base and Knowledge Acquisition pages", H3))
    s.append(P("knowledge_base_view.py shows all rules with counts and a rule inspector. knowledge_acquisition.py lets an expert edit "
               "thresholds, university and market data for the session; the order checks run before any change is applied, and "
               "the JSON can be downloaded and uploaded."))

    # 4.10 tests
    tests_head = Paragraph("4.10 Tests (tests/)", H2)
    rows = [["Test file", "Tests", "What it checks"]]
    desc = {"test_certainty.py": "CF maths and CF words.",
            "test_data_files.py": "University and market data are complete and fee bands match the thresholds.",
            "test_eligibility.py": "Not sure handling, conditional status and a 150-run random check that eligibility is never broken.",
            "test_engine.py": "Conflict resolution, refraction, cycle cap, HALT, blank vs 0, sanity rules.",
            "test_rules.py": "Rule format, counts, no numbers in conditions, threshold order checks.",
            "test_samples.py": "The five sample students and the What-if cases.",
            "test_ui.py": "A full run through the wizard and the required-answer check."}
    for p in sorted((ROOT / "tests").glob("test_*.py")):
        n = len(re.findall(r"^def test_", p.read_text(encoding="utf-8"), re.M))
        rows.append([p.name, str(n), desc.get(p.name, module_doc(f"tests/{p.name}"))])
    s.append(KeepTogether([tests_head, table(rows, [0.25 * W, 0.08 * W, 0.67 * W])]))

    # ---- 5 rules summary
    s.append(Paragraph("5 Rules Summary", H1))
    groups = {}
    for r in kb.rules:
        g = groups.setdefault(r["group"], {"name": r["group_name"], "n": 0, "p": set(), "c": 0, "d": 0})
        g["n"] += 1
        g["p"].add(r["priority"])
        g["c" if r["type"] == "compute" else "d"] += 1
    rows = [["Group", "Name", "Priority", "Rules", "Compute", "Decision"]]
    for gid, g in groups.items():
        pr = sorted(g["p"], reverse=True)
        rows.append([gid, g["name"], str(pr[0]) if len(pr) == 1 else f"{pr[0]}\u2013{pr[-1]}", str(g["n"]), str(g["c"]), str(g["d"])])
    rows.append(["Total", "", "", str(counts["total"]), str(counts["compute"]), str(counts["decision"])])
    s.append(table(rows, [0.1 * W, 0.36 * W, 0.14 * W, 0.12 * W, 0.14 * W, 0.14 * W]))
    s.append(P(f"Together the rules have **{counts['leaf_conditions']} leaf conditions**. Five example rules:"))
    s += bullets([f"**{rid}** (priority {kb.rule_by_id[rid]['priority']}): {kb.rule_by_id[rid]['text']}"
                  for rid in ("DS06", "EL08", "AP13", "FM07", "RC07")])

    # ---- 6 worked example
    s.append(Paragraph("6 Worked Example: Hamza", H1))
    ham = next(x for x in samples if x["name"] == "Hamza")
    s.append(P(f"Hamza: {ham['blurb']}. These are the first eight rule firings from the engine\u2019s real trace."))
    rows = [["Cycle", "Rule", "Conflict set", "CF calculation", "New fact"]]
    for st in results["Hamza"].trace[:8]:
        cs = ", ".join(st["conflict_set"][:4]) + (" \u2026" if len(st["conflict_set"]) > 4 else "")
        rows.append([str(st["cycle"]), st["instance"], cs, st["cf_text"], "; ".join(a.replace("elig.", "") for a in st["added"])])
    s.append(table(rows, [0.08 * W, 0.1 * W, 0.24 * W, 0.24 * W, 0.34 * W]))
    s.append(P("Cycle 1: DF02 and DF08 have the same priority and one condition each, so the smaller ID (DF02) fires first. "
               "Cycle 3: AP01 and AP04 have two conditions and beat AP03, which has one (specificity). Cycle 4: Hamza answered "
               "Not sure about electronics, so apt_electrical gets 0.85 \u00d7 0.5 = 0.425."))
    cs_steps = [st for st in results["Hamza"].trace if st["instance"] in ("FM01", "MK02[cs]", "MK01[cs]", "RC01")]
    s += bullets([f"{st['instance']}: {st['cf_text']} \u2192 {'; '.join(st['added'])}" for st in cs_steps])

    # ---- 7 testing
    s.append(Paragraph("7 Testing", H1))
    s.append(P(f"Running pytest gives **{n_tests} passed**" + (f" and {n_failed} failed." if n_failed else ", with no failures.")
               + " The tests use small made-up knowledge bases to prove the engine rules (priority, specificity, ID order, "
               "refraction, the cycle cap) and the real knowledge base for the samples and eligibility checks."))
    rows = [["Student", "Profile", "Top results"]]
    for x in samples:
        r = results[x["name"]]
        rows.append([x["name"], x["blurb"], "; ".join(f"{t['name']} {t['cf']:.3f} {t['label']}" +
                                                      (" (conditional)" if t["status"] == "conditional" else "") for t in r.top)])
    s.append(table(rows, [0.13 * W, 0.32 * W, 0.55 * W]))
    s.append(P("All five students give the results expected in samples/sample_students.json. For guidance only \u2014 always "
               "confirm admission criteria with the university."))

    doc = Doc(out_path)
    doc.multiBuild(s, canvasmaker=NumberedCanvas)
    return out_path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "code_explanation.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Wrote {build(out)}")
