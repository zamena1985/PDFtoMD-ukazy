# -*- coding: utf-8 -*-
"""Сборка doc/guide_ru.pdf из doc/guide_ru.md: Markdown -> HTML (markdown-it-py) -> PDF (Chrome в фоновом режиме).
Нужны пакет markdown-it-py (requirements-dev.txt) и установленный Google Chrome или Microsoft Edge."""
import os, shutil, subprocess, sys, tempfile
from markdown_it import MarkdownIt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "guide_ru.md")
OUT = os.path.join(HERE, "guide_ru.pdf")
CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font: 11.5pt/1.5 Arial, "Segoe UI", sans-serif; color: #1b1b1f; max-width: 180mm; margin: 0 auto; }
h1 { font-size: 22pt; line-height: 1.25; margin: 0 0 14pt; color: #0b3d6e; }
h2 { font-size: 15pt; margin: 22pt 0 8pt; color: #0b63c6; border-bottom: 1px solid #c9d8ea; padding-bottom: 3pt; page-break-after: avoid; }
p, li { text-align: left; }
code { font: 10pt Consolas, monospace; background: #f1f3f6; padding: 1px 4px; border-radius: 3px; }
pre { font: 10pt/1.4 Consolas, monospace; background: #f1f3f6; padding: 9pt 11pt; border-radius: 5px; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; font-size: 10.5pt; margin: 8pt 0 12pt; page-break-inside: avoid; }
th, td { border: 1px solid #c9d8ea; padding: 5pt 7pt; vertical-align: top; }
th { background: #eaf2fb; text-align: left; }
img { max-width: 100%; border: 1px solid #c9d8ea; border-radius: 4px; margin: 6pt 0 10pt; }
strong { color: #0b3d6e; }
a { color: #0b63c6; text-decoration: none; }
ol, ul { padding-left: 22pt; }
"""


def browser():
    for p in (os.environ.get("CHROME"), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")):
        if p and os.path.exists(p):
            return p
    sys.exit("не найден Chrome/Edge: укажите путь в переменной CHROME")


def main():
    md = open(SRC, encoding="utf-8").read()
    html = MarkdownIt("commonmark").enable("table").render(md)
    page = f'<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Гайд pdf2md-ukazy</title><style>{CSS}</style></head><body>{html}</body></html>'
    tmp = os.path.join(HERE, "_guide_tmp.html")          # рядом с картинками, чтобы относительные пути работали
    open(tmp, "w", encoding="utf-8").write(page)
    prof = tempfile.mkdtemp(prefix="chrome-guide-")
    try:
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={prof}",
                        f"--print-to-pdf={OUT}", "file:///" + tmp.replace("\\", "/")], check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        os.remove(tmp); shutil.rmtree(prof, ignore_errors=True)
    print("готово:", OUT, f"{os.path.getsize(OUT) / 1024:.0f} КБ")


if __name__ == "__main__":
    main()
