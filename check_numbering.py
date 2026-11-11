# -*- coding: utf-8 -*-
"""Проверка нумерации списков в готовых Markdown-файлах.

Markdown берёт номер только у первого пункта списка, остальные считает сам. Поэтому номер,
написанный в файле, и номер, который увидит читатель, могут разойтись. Скрипт отрисовывает
каждый файл парсером CommonMark (markdown-it-py, те же правила, что у GitHub и Nextcloud)
и сравнивает номера.

    python check_numbering.py <папка с ru/ и sah/>
"""
import os, re, sys
from markdown_it import MarkdownIt


def rendered_numbers(html):
    out = []; stack = []
    for m in re.finditer(r"<(/?)(ol|ul|li)\b([^>]*)>", html):
        close, tag, attrs = m.group(1) == "/", m.group(2), m.group(3)
        if tag in ("ol", "ul") and not close:
            st = re.search(r'start="(\d+)"', attrs)
            stack.append([tag == "ol", int(st.group(1)) if st else 1])
        elif tag in ("ol", "ul") and close:
            stack.pop()
        elif tag == "li" and not close and stack and stack[-1][0]:
            out.append(stack[-1][1]); stack[-1][1] += 1
    return out


def source_numbers(md):
    return [int(m.group(1)) for line in md.split("\n") for m in [re.match(r"^\s*(\d+)[.)]\s", line)] if m]


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    parser = MarkdownIt("commonmark").enable("table")
    files = bad = 0
    for lang in sorted(os.listdir(root)):
        d = os.path.join(root, lang)
        if not os.path.isdir(d):
            continue
        for f in sorted((x for x in os.listdir(d) if x.endswith(".md")), key=lambda x: (len(x), x)):
            files += 1
            md = open(os.path.join(d, f), encoding="utf-8").read()
            a, b = source_numbers(md), rendered_numbers(parser.render(md))
            diffs = [f"№{i + 1}: в файле {x}, читатель увидит {y}" for i, (x, y) in enumerate(zip(a, b)) if x != y]
            if len(a) != len(b):
                diffs.append(f"пунктов в файле {len(a)}, в отрисовке {len(b)}")
            if diffs:
                bad += 1
                print(f"{lang}/{f}: " + "; ".join(diffs[:4]) + (" …" if len(diffs) > 4 else ""))
    print(f"файлов: {files}, с расхождением нумерации: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
