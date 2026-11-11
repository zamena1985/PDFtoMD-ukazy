# -*- coding: utf-8 -*-
"""Страница проверки: PDF рядом с полученным Markdown.

    python review.py --pdf <папка с ru/ и sah/ PDF> --md <папка результата> [--prev <прежняя версия>] [--port 8765]

Поднимает маленький локальный веб-сервер (только для этого компьютера) и открывает браузер.
Интернет не нужен. Слева PDF, в середине Markdown так, как его увидит читатель, справа чистый
текст для сверки слов; при --prev добавляется колонка «Было» со списком изменённых абзацев.
Отметки «проверено» и заметки хранятся в браузере.
"""
import argparse, http.server, json, os, sys, threading, webbrowser
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    roots = {}          # url-префикс -> папка на диске
    config = {}

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path in ("/", "/review.html"):
            return os.path.join(HERE, "review", "review.html")
        if path == "/marked.min.js":
            return os.path.join(HERE, "review", "marked.min.js")
        for prefix, root in self.roots.items():
            if path.startswith(prefix):
                rel = path[len(prefix):].lstrip("/")
                return os.path.normpath(os.path.join(root, *rel.split("/")))
        return os.path.join(HERE, "review", "nope")

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/config.json":
            body = json.dumps(self.config, ensure_ascii=False).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")      # всегда свежие файлы после пересборки
        super().end_headers()

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description="Страница проверки Markdown против PDF")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")       # буквы вне кодировки консоли не роняют скрипт
    ap.add_argument("--pdf", required=True, help="папка с PDF (внутри ru/ и sah/)")
    ap.add_argument("--md", required=True, help="папка с результатом pdf2md.py (внутри ru/, sah/, docs.json)")
    ap.add_argument("--prev", help="прежняя версия результата для колонки «Было»")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    for d in (a.pdf, a.md) + ((a.prev,) if a.prev else ()):
        if not os.path.isdir(d):
            sys.exit(f"нет папки: {d}")
    if not os.path.exists(os.path.join(a.md, "docs.json")):
        sys.exit(f"в {a.md} нет docs.json: сначала выполните pdf2md.py")
    Handler.roots = {"/pdf/": os.path.abspath(a.pdf), "/md/": os.path.abspath(a.md)}
    if a.prev:
        Handler.roots["/prev/"] = os.path.abspath(a.prev)
    Handler.config = {"md": "/md/", "pdf": "/pdf/", "prev": "/prev/" if a.prev else None,
                      "local_md_dir": os.path.abspath(a.md).replace("\\", "/") + "/"}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), partial(Handler, directory=HERE))
    srv.handle_error = lambda *x: None                       # обрыв соединения браузером не ошибка
    url = f"http://127.0.0.1:{a.port}/review.html"
    print(f"страница проверки: {url}   (остановить: Ctrl+C)")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
