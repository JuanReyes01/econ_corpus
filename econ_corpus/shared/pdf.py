"""Render a markdown datasheet as a PDF, for the delivery folder.

Input: a markdown file written by `datasheet` or `datasheet_clean`.
Output: a PDF next to it, with the tables and the SVG figures.

Lives here: the HTML page and the call to the browser that prints it. Does not live here: the
content of the datasheets. Needs Google Chrome (`google-chrome`) on the PATH.
"""

from pathlib import Path
import subprocess
import sys
import tempfile

import markdown

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 10.5pt; line-height: 1.45;
       color: #222; }
h1 { font-size: 18pt; line-height: 1.25; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin-top: 18pt; border-bottom: 1px solid #bbb; padding-bottom: 2pt;
     break-after: avoid; }
h3 { font-size: 11.5pt; margin-top: 12pt; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt;
        font-family: 'DejaVu Sans', sans-serif; font-size: 8.5pt; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
th, td { border: 1px solid #ccc; padding: 2.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt; background: #f4f4f4;
       padding: 0 2pt; }
img { max-width: 100%; break-inside: avoid; }
"""
CHROME = ["google-chrome", "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer"]


def page(text: str, folder: Path) -> str:
    """Return the HTML page of a markdown text; relative links resolve from `folder`."""
    body = markdown.markdown(text, extensions=["tables", "sane_lists"])
    head = f"<meta charset='utf-8'><base href='{folder.as_uri()}/'><style>{CSS}</style>"
    return f"<!doctype html><html><head>{head}</head><body>{body}</body></html>"


def render(source: Path, out: Path) -> None:
    """Print a markdown file to a PDF with headless Chrome."""
    html = page(source.read_text(encoding="utf-8"), source.parent.resolve())
    with tempfile.TemporaryDirectory() as folder:
        html_file = Path(folder) / "page.html"
        html_file.write_text(html, encoding="utf-8")
        command = [*CHROME, "--allow-file-access-from-files", f"--print-to-pdf={out.resolve()}"]
        subprocess.run([*command, html_file.as_uri()], check=True, capture_output=True)  # noqa: S603


def main() -> None:
    """Render every markdown file given on the command line to a PDF beside it."""
    for name in sys.argv[1:]:
        render(Path(name), Path(name).with_suffix(".pdf"))


if __name__ == "__main__":
    main()
