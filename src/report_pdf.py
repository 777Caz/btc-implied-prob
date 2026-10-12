"""
The write-up as a PDF: reports/REPORT.md -> reports/REPORT.pdf (A4), figures embedded.

Renders the Markdown to a standalone HTML page next to REPORT.md (so the relative figure paths
resolve) and prints it with a headless Chromium browser (Chrome or Edge), the same way as the
dashboard PDF. The intermediate HTML is deleted afterwards.
Run:  python -m src.report_pdf   (after python -m src.report_figures)
"""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

import config

log = logging.getLogger(__name__)
R = config.ROOT / "reports"
SRC, OUT = R / "REPORT.md", R / "REPORT.pdf"
# Chrome first: launched from Python, Edge on Windows can hand the job to a running instance and write nothing.
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome", "chromium", "chromium-browser",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "msedge"]

CSS = """
@page { size: A4; margin: 16mm 17mm; }
body { font: 10.5pt/1.5 "Segoe UI", system-ui, -apple-system, sans-serif; color: #111; max-width: 780px; margin: 0 auto; }
h1 { font-size: 19pt; line-height: 1.25; margin: 0 0 6px; }
h2 { font-size: 14pt; margin: 22px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 3px; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 16px 0 4px; break-after: avoid; }
p, li { orphans: 3; widows: 3; } ul, ol { padding-left: 20px; } li { margin: 2px 0; }
pre { background: #f5f5f3; border-radius: 4px; padding: 8px 10px; font-size: 9.5pt; white-space: pre-wrap; break-inside: avoid; }
code { font-family: Consolas, "SFMono-Regular", monospace; font-size: 9.5pt; }
table { border-collapse: collapse; margin: 8px 0; font-size: 9.5pt; break-inside: avoid; }
th, td { border-bottom: 1px solid #ddd; padding: 3px 8px; text-align: left; vertical-align: top; }
th { border-bottom: 1.5px solid #999; }
p:has(> img) { break-inside: avoid; break-after: avoid; margin: 12px 0 4px; }
img { width: 100%; height: auto; display: block; }
"""


def browser() -> str:
    for b in BROWSERS:
        if Path(b).exists() or shutil.which(b):
            return b
    raise FileNotFoundError("no Edge/Chrome/Chromium found to print the PDF")


def main() -> None:
    config.setup_logging()
    md = SRC.read_text(encoding="utf-8").replace(" PDF version: [REPORT.pdf](REPORT.pdf).", "")   # no self-link in the PDF
    body = MarkdownIt("commonmark").enable("table").render(md)   # CommonMark, so lists nest as on GitHub
    page = R / "_report_print.html"
    page.write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>BTC options vs Kalshi</title>'
                    f"<style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as profile:   # own profile, so a running browser doesn't swallow the job
            subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
                            "--no-pdf-header-footer", f"--print-to-pdf={OUT}", page.as_uri()],
                           check=True, capture_output=True, timeout=180)
    finally:
        page.unlink(missing_ok=True)
    log.info("report -> %s (%d KB)", OUT, OUT.stat().st_size // 1024)


if __name__ == "__main__":
    main()
