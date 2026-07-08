"""Build the Trendkept Owner's Manual — one document containing everything.

    python business/build_manual.py            # writes the HTML
    python business/build_manual.py --pdf      # also prints to PDF (Chromium)

Assembles START_HERE (the action steps) followed by every business document
and the launch content pack into a single print-ready HTML file, then
optionally renders `Trendkept_Owners_Manual.pdf` via headless Chromium
(pass --chromium PATH if yours isn't on PATH as `chromium`).

Standard library only, including the small markdown converter — it covers
exactly the constructs these documents use (headings, lists, tables, code
blocks, quotes, bold/italic/code, links, checkboxes, rules).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Order matters: actions first, then the why, then the detail, then the
# ready-to-paste launch material.
SECTIONS = [
    ("START_HERE.md", None),
    ("PLAN.md", "The business plan"),
    ("FINANCIALS.md", None),
    ("GO_TO_MARKET.md", None),
    ("LEGAL.md", None),
    ("LAUNCH_CHECKLIST.md", None),
    ("PAPER_TRADING_GUIDE.md", None),
    ("launch/show_hn.md", "Launch pack — Show HN"),
    ("launch/reddit_algotrading.md", "Launch pack — r/algotrading"),
    ("launch/reddit_swingtrading.md", "Launch pack — r/swingtrading"),
    ("launch/trend_check_001.md", "Launch pack — The Trend Check #1"),
]

_INLINE_RULES = [
    (re.compile(r"`([^`]+)`"), lambda m: f"<code>{m.group(1)}</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: f"<b>{m.group(1)}</b>"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"),
     lambda m: f"<i>{m.group(1)}</i>"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
     lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>'),
]


def _inline(text: str) -> str:
    # Protect code spans from bold/italic processing by converting them
    # first; escape everything before any tags are introduced.
    out = html.escape(text, quote=False)
    for rx, sub in _INLINE_RULES:
        out = rx.sub(sub, out)
    out = out.replace("[ ]", "&#9744;").replace("[x]", "&#9745;")
    return out


def md_to_html(md: str) -> str:
    """Just enough markdown for these documents."""
    lines = md.split("\n")
    out: List[str] = []
    i = 0
    in_ul = in_ol = in_quote = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol, in_quote
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            close_lists()
            block: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i], quote=False))
                i += 1
            out.append("<pre><code>" + "\n".join(block) + "</code></pre>")
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            close_lists()
            headers = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("<table><tr>"
                       + "".join(f"<th>{_inline(h)}</th>" for h in headers)
                       + "</tr>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip()
                         for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>"
                           + "".join(f"<td>{_inline(c)}</td>" for c in cells)
                           + "</tr>")
                i += 1
            out.append("</table>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^\s*(---|\*\*\*)\s*$", line):
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        if line.startswith(">"):
            if not in_quote:
                close_lists()
                out.append("<blockquote>")
                in_quote = True
            out.append(f"<p>{_inline(line.lstrip('> '))}</p>")
            i += 1
            continue
        if in_quote and line.strip():
            out.append(f"<p>{_inline(line)}</p>")
            i += 1
            continue

        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = [m.group(1)]
            while i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]) \
                    and not re.match(r"^\s*[-*\d]", lines[i + 1].lstrip()):
                i += 1
                item.append(lines[i].strip())
            out.append(f"<li>{_inline(' '.join(item))}</li>")
            i += 1
            continue

        m = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m:
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            item = [m.group(1)]
            while i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]) \
                    and not re.match(r"^\s*[-*\d]", lines[i + 1].lstrip()):
                i += 1
                item.append(lines[i].strip())
            out.append(f"<li>{_inline(' '.join(item))}</li>")
            i += 1
            continue

        if not line.strip():
            close_lists()
            i += 1
            continue

        # Paragraph: gather soft-wrapped continuation lines.
        close_lists()
        para = [line.strip()]
        while i + 1 < len(lines) and lines[i + 1].strip() \
                and not re.match(r"^(\s*[-*]\s|\s*\d+\.\s|#{1,4}\s|>|\||```)",
                                 lines[i + 1]):
            i += 1
            para.append(lines[i].strip())
        out.append(f"<p>{_inline(' '.join(para))}</p>")
        i += 1

    close_lists()
    return "\n".join(out)


_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #111; margin: 0; }
.cover { text-align: left; padding-top: 90mm; page-break-after: always; }
.cover .brand { color: #2a78d6; font-weight: 700; letter-spacing: .14em;
  text-transform: uppercase; font-size: 12pt; }
.cover h1 { font-size: 30pt; margin: 8pt 0 6pt; letter-spacing: -.02em; }
.cover p { color: #555; font-size: 12pt; max-width: 130mm; }
.toc { page-break-after: always; }
.toc ol { font-size: 11pt; line-height: 2; }
section.doc { page-break-before: always; }
h1 { font-size: 19pt; margin: 0 0 10pt; letter-spacing: -.01em;
  border-bottom: 2.5pt solid #2a78d6; padding-bottom: 6pt; }
h2 { font-size: 13.5pt; margin: 16pt 0 6pt; }
h3 { font-size: 11.5pt; margin: 13pt 0 4pt; }
p { margin: 6pt 0; }
ul, ol { margin: 6pt 0; padding-left: 18pt; }
li { margin: 3pt 0; }
code { font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 9.2pt; background: #f2f1ee; padding: 1pt 3pt;
  border-radius: 3pt; }
pre { background: #f2f1ee; border: .5pt solid #ddd; border-radius: 5pt;
  padding: 8pt 10pt; overflow-wrap: anywhere; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0;
  font-size: 9.3pt; }
th, td { border-bottom: .5pt solid #ccc; padding: 4pt 6pt;
  text-align: left; vertical-align: top; }
th { color: #555; font-weight: 600; border-bottom: 1pt solid #999; }
tr { page-break-inside: avoid; }
blockquote { border-left: 2.5pt solid #2a78d6; margin: 8pt 0;
  padding: 2pt 0 2pt 10pt; color: #444; }
hr { border: 0; border-top: .5pt solid #ccc; margin: 12pt 0; }
a { color: #2a78d6; text-decoration: none; }
h1, h2, h3 { page-break-after: avoid; }
pre, blockquote { page-break-inside: avoid; }
.footer-note { color: #777; font-size: 9pt; margin-top: 18pt;
  border-top: .5pt solid #ccc; padding-top: 8pt; }
"""


def build_html() -> str:
    from datetime import date

    docs = []
    toc = []
    for idx, (rel, title_override) in enumerate(SECTIONS, 1):
        path = os.path.join(HERE, rel)
        with open(path) as fh:
            md = fh.read()
        m = re.match(r"^#\s+(.*)$", md.split("\n", 1)[0])
        title = title_override or (m.group(1) if m else rel)
        if m:  # drop the doc's own H1; the section header replaces it
            md = md.split("\n", 1)[1]
        toc.append(f"<li>{html.escape(title)}</li>")
        docs.append(f'<section class="doc"><h1>{html.escape(title)}</h1>'
                    f"{md_to_html(md)}</section>")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Trendkept — Owner's Manual</title><style>{_CSS}</style></head><body>
<div class="cover">
  <div class="brand">Trendkept</div>
  <h1>The Owner's Manual</h1>
  <p>Everything, in one document: the steps to take right now, the business
  plan, the financial projections, the go-to-market playbook, the legal
  guide, the 90-day checklist, and the ready-to-paste launch content.</p>
  <p><b>Start with section 1 and work top to bottom.</b></p>
  <p style="color:#888">Compiled {date.today():%d %B %Y} · regenerate with
  <code>python business/build_manual.py --pdf</code></p>
</div>
<div class="toc"><h1>Contents</h1><ol>{''.join(toc)}</ol>
<p class="footer-note">Trendkept is analysis software and education, not
investment advice. Trading involves risk of loss; past and backtested
performance do not predict future results. This document contains business
planning material, not legal or financial advice — the one-hour solicitor
review in the Legal guide covers the specifics.</p></div>
{''.join(docs)}
</body></html>"""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", action="store_true",
                        help="also render the PDF with headless Chromium")
    parser.add_argument("--chromium", default=None,
                        help="path to a Chromium/Chrome binary")
    args = parser.parse_args(argv)

    html_path = os.path.join(HERE, "Trendkept_Owners_Manual.html")
    with open(html_path, "w") as fh:
        fh.write(build_html())
    print(f"wrote {html_path}")

    if not args.pdf:
        return 0

    chromium = args.chromium or shutil.which("chromium") \
        or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if not chromium:
        print("no Chromium/Chrome found; open the HTML in a browser and "
              "print to PDF instead, or pass --chromium PATH")
        return 1
    pdf_path = os.path.join(HERE, "Trendkept_Owners_Manual.pdf")
    subprocess.run(
        [chromium, "--headless", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path],
        check=True, capture_output=True)
    print(f"wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
