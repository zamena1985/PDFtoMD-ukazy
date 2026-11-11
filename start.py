# -*- coding: utf-8 -*-
"""Запуск без командной строки: задаёт три вопроса, переводит PDF в Markdown и открывает страницу проверки.
Запускается двойным щелчком по start.bat (Windows) или `python start.py`."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def ask(prompt, default=None):
    tail = f" [{default}]" if default else ""
    while True:
        s = input(f"{prompt}{tail}: ").strip().strip('"').strip("'")
        if s:
            return s
        if default is not None:
            return default


def yes(prompt, default=True):
    s = input(f"{prompt} ({'Д/н' if default else 'д/Н'}): ").strip().lower()
    if not s:
        return default
    return s[0] in "дyд1"


def main():
    print("Перевод указов из PDF в Markdown\n" + "-" * 34)
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        print("Не установлена библиотека PyMuPDF. Запустите install.bat (нужен интернет, один раз) и повторите.")
        return 1
    while True:
        src = ask("Папка с PDF (внутри должны быть подпапки ru и sah; путь можно вставить или перетащить папку в окно)")
        if os.path.isdir(src) and any(os.path.isdir(os.path.join(src, d)) for d in ("ru", "sah")):
            break
        print("  В этой папке нет подпапок ru или sah, проверьте путь.")
    dst = ask("Папка для результата", os.path.join(os.path.dirname(os.path.abspath(src)), "markdown"))
    indent = yes("Ставить красную строку у абзацев (&emsp;&emsp; в начале абзаца)?", True)
    cmd = [sys.executable, "-X", "utf8", os.path.join(HERE, "pdf2md.py"), src, dst] + (["--indent"] if indent else [])
    print("\nЗапуск:", " ".join(f'"{c}"' if " " in c else c for c in cmd[1:]), "\n")
    code = subprocess.call(cmd)
    if code != 0:
        print("\nСкрипт завершился с ошибкой, текст выше.")
        return code
    print(f"\nГотово. Файлы в папке: {os.path.abspath(dst)}")
    print("Отчёт с замечаниями: report.json там же (значок ✱ на странице проверки).")
    if yes("\nОткрыть страницу проверки (PDF рядом с Markdown)?", True):
        print("Страница откроется в браузере. Чтобы закончить, закройте это окно или нажмите Ctrl+C.\n")
        subprocess.call([sys.executable, "-X", "utf8", os.path.join(HERE, "review.py"), "--pdf", src, "--md", dst])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nОстановлено.")
