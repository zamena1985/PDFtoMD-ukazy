# -*- coding: utf-8 -*-
"""Черновой перевод указов Главы РС(Я) из PDF в Markdown по ТЗ «Перевод PDF-текстов в формат Markdown».

  python pdf2md.py <папка с ru/ и sah/> <папка результата> [--indent] [--only ru/1002.pdf ...]

  Подробности, ключи и смысл замечаний отчёта: README.md.

Что делает: читает текстовый слой PDF (PyMuPDF), склеивает строки в абзацы по отступу первой
строки, выкидывает шапку (ГЛАВА / УКАЗ / ЫЙААХ / г. Якутск ...) и номера страниц, заголовок и
жирные центрованные строки оформляет как # / ##, жирные фрагменты внутри абзацев - как **...**,
курсив - *...*, таблицы PDF - как Markdown-таблицы, подписной блок (должность, подпись, дата, №) -
как таблицу из двух строк; приложения после подписи сохраняются. Пишет отчёт о сомнительных местах.
Результат - ЧЕРНОВИК: каждый файл сверяется с PDF глазами, как требует ТЗ.
"""
import os, re, sys, json
import pymupdf

HEADER_PATTERNS = [
    r"^ГЛАВА$", r"^РЕСПУБЛИКИ САХА \(ЯКУТИЯ\)$", r"^ГЛАВА РЕСПУБЛИКИ САХА \(ЯКУТИЯ\)$",
    r"^САХА ӨРӨСПҮҮБҮЛҮКЭТИН$", r"^ИЛ ДАРХАНА$", r"^САХА ӨРӨСПҮҮБҮЛҮКЭТИН ИЛ ДАРХАНА$",
    r"^УКАЗ$", r"^ЫЙААХ$", r"^г\. ?Якутск$", r"^Дьокуускай к\.$",
]
HEADER_RE = [re.compile(p, re.I) for p in HEADER_PATTERNS]
NUM_ANY = re.compile(r"(№\s*\d+|\d+\s*№)\s*$")
NAME_TAIL = re.compile(r"\s([А-ЯЁӨҮҤҺ]\.\s*[А-ЯЁӨҮҤҺ][А-ЯЁӨҮҤҺ\-]+)\s*$")
WORD_CHARS = r"[^\wёӨөҮүҤҥҺһ]"
HYPHEN_JOINS = []   # места склейки по дефису в текущем документе (для отчёта)
INDENT = "--indent" in sys.argv   # красная строка абзацев: два широких пробела как HTML-сущности &emsp; (Nextcloud Text сырой U+2003 не показывает)
ALIGN = "--align" in sys.argv     # выравнивание по центру/справа HTML-тегами; Nextcloud Text их не отрисовывает, для облака не использовать


def is_bold(span):
    return bool(span["flags"] & 16) or "bold" in span["font"].lower()


def is_italic(span):
    return bool(span["flags"] & 2) or "italic" in span["font"].lower() or "oblique" in span["font"].lower()


def page_lines(page, pno, table_rects=()):
    """Строки страницы: фрагменты одной базовой линии склеены по x (выключка по ширине режет строку на слова).
    Фрагменты внутри рамок таблиц (table_rects) в поток не попадают: таблицы переносятся отдельно."""
    raw = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            spans = [s for s in l["spans"] if s["text"] != ""]
            frag = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
            if not frag:
                continue
            # шапка: фрагменты ГЛАВА / УКАЗ / ЫЙААХ / г. Якутск ... в верхней части первой страницы
            if pno == 0 and l["bbox"][1] < 240 and any(r.match(frag) for r in HEADER_RE):
                continue
            cx, cy = (l["bbox"][0] + l["bbox"][2]) / 2, (l["bbox"][1] + l["bbox"][3]) / 2
            if any(r.x0 - 2 <= cx <= r.x1 + 2 and r.y0 - 2 <= cy <= r.y1 + 2 for r in table_rects):
                continue
            raw.append({"y": round(l["bbox"][1], 0), "y1": l["bbox"][3], "x0": l["bbox"][0], "x1": l["bbox"][2],
                        "spans": [{"t": s["text"], "b": is_bold(s), "i": is_italic(s), "sz": s["size"]} for s in spans]})
    raw.sort(key=lambda r: (r["y"], r["x0"]))
    lines = []
    for r in raw:
        if lines and abs(lines[-1]["y"] - r["y"]) <= 2.5 and r["x0"] >= lines[-1]["x1"] - 2:
            prev = lines[-1]
            if r["x0"] - prev["x1"] > 1.5 and not prev["spans"][-1]["t"].endswith(" ") and not r["spans"][0]["t"].startswith(" "):
                prev["spans"].append({"t": " ", "b": False, "i": False, "sz": r["spans"][0]["sz"]})
            prev["spans"].extend(r["spans"]); prev["x1"] = r["x1"]; prev["y1"] = max(prev["y1"], r["y1"])
        else:
            lines.append(dict(r))
    for ln in lines:
        ln["text"] = re.sub(r"\s+", " ", "".join(s["t"] for s in ln["spans"])).strip()
        ln["bold"] = all(s["b"] for s in ln["spans"] if s["t"].strip())
        ln["italic"] = all(s["i"] for s in ln["spans"] if s["t"].strip())
        ln["size"] = max(s["sz"] for s in ln["spans"])
        ln["page"] = pno
        ln["width"] = page.rect.width
    return lines


def spans_to_md(spans):
    """Текст абзаца с **жирным** и *курсивом* по фрагментам."""
    out = []; cur = None; buf = ""
    def flush():
        nonlocal buf
        if not buf:
            return
        core = buf.strip(" ")
        lead = buf[: len(buf) - len(buf.lstrip(" "))]; trail = buf[len(buf.rstrip(" ")):]
        mark = {"bi": "***", "b": "**", "i": "*"}.get(cur, "")
        out.append(lead + mark + core + mark + trail if core else buf)
        buf = ""
    for s in spans:
        kind = "bi" if s["b"] and s["i"] else "b" if s["b"] else "i" if s["i"] else ""
        if not s["t"].strip():
            buf += s["t"]; continue
        if not re.search(r"[\wёӨөҮүҤҥҺһ]", s["t"]):
            kind = cur or ""      # одинокая кавычка или скобка жирным шрифтом - артефакт вёрстки, не выделение
        if kind != cur:
            flush(); cur = kind
        buf += s["t"]
    flush()
    return re.sub(r"\s+", " ", "".join(out)).strip()


def join_lines(lines):
    """Абзац из строк: склейка через пробел, перенос слова по дефису в конце строки убираем."""
    text = ""
    for ln in lines:
        piece = spans_to_md(ln["spans"])
        if not text:
            text = piece
        elif text.endswith("-") and piece[:1].islower():
            # в этих PDF слова по слогам не переносятся: дефис на конце строки - настоящий
            # («информационно-телекоммуникационной»), склеиваем без пробела и дефис оставляем
            HYPHEN_JOINS.append(text[-22:] + "|" + piece[:14])   # место склейки: «…слово-|продолжение»
            text = text + piece
        else:
            text += " " + piece
    text = re.sub(r"\*\*\s+\*\*", " ", text)      # "**а** **б**" -> "**а б**"
    text = re.sub(r"(?<!\*)\*\s+\*(?!\*)", " ", text)
    return text


def build_paragraphs(lines, left):
    """Группировка строк в абзацы."""
    def centered(ln):
        return abs((ln["x0"] + ln["x1"]) / 2 - ln["width"] / 2) < 25 and ln["x0"] > left + 8
    def right_block(ln):
        return ln["x0"] > ln["width"] * 0.5 and not centered(ln)
    paras = []; cur = []; prev = None
    for ln in lines:
        if prev is None:
            new_par = True
        elif ln["bold"] and prev["bold"] and (centered(ln) or centered(prev)):
            new_par = False                     # строки одного жирного заголовка
        elif ln["bold"] != prev["bold"]:
            new_par = True                      # граница жирного блока
        elif right_block(ln) and right_block(prev):
            new_par = ln["y"] - prev["y1"] > ln["size"] * 1.1   # «Приложение / к Указу / ...» - один блок
        elif ln["page"] == prev["page"] and ln["y"] - prev["y1"] > ln["size"] * 1.1:
            new_par = True                      # пустая строка между блоками
        elif ln["x0"] <= left + 12 and prev["x0"] > left + 70:
            new_par = True                      # возврат к левому краю после висячего отступа: новая запись
                                                # (составы советов: «Фамилия И.О. - должность» в несколько строк)
        elif left + 12 < ln["x0"] <= left + 70:
            new_par = True                      # красная строка
        elif ln["x0"] > left + 70:
            # Строка далеко от левого края: либо висячий отступ (продолжение записи состава совета),
            # либо отдельная центрованная строка (подпись таблицы, закрывающая кавычка после таблицы).
            # Новый абзац, если строка на новой странице, либо предыдущая строка закончена знаком
            # препинания и это похоже на центрованную строку или предыдущая была обычной строкой с полей.
            ended = bool(re.search(r"[.:;]\s*$", prev["text"]))
            loose_centered = abs((ln["x0"] + ln["x1"]) / 2 - ln["width"] / 2) < 60 and ln["x1"] < ln["width"] - left - 20
            ended_strict = ended and not re.search(r"(^|\s)[а-яёөүҥһ]\.\s*$", prev["text"])   # «Дьокуускай к.» - сокращение, запись продолжается
            # запись с висячим отступом могла перейти на новую страницу: предыдущая строка не закончена и это либо
            # её начало с левого поля, либо строка той же колонки; иначе новая страница = новый абзац
            hang_cont = not ended and not ln["bold"] and (prev["x0"] <= left + 12 or abs(prev["x0"] - ln["x0"]) < 4)
            new_par = ((ln["page"] != prev["page"] and not hang_cont)
                       or (loose_centered and (ln["bold"] or ended))
                       or (prev["x0"] <= left + 12 and (ln["bold"] or ended_strict)))
        elif (prev["x1"] < prev["width"] * 0.70 and prev["x1"] - prev["x0"] > 30
              and re.search(r"[.;:»\")]\s*$", prev["text"]) and ln["x0"] <= left + 12
              and re.match(r"[A-ZА-ЯЁӨҮҤҺ0-9«\"]", ln["text"])):
            new_par = True                      # абзац без красной строки: предыдущая строка короткая и закончена
                                                # (списки фамилий в составах советов, вставляемые пункты)
        else:
            new_par = False
        if new_par and cur:
            paras.append(cur); cur = []
        cur.append(ln); prev = ln
    if cur:
        paras.append(cur)
    return paras, centered


def drop_trailing_empty_cols(rows):
    """Пустой последний столбец - артефакт вёрстки (часть таблицы до разрыва страницы)."""
    rows = [list(r) for r in rows]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    while width > 1 and all(not r[width - 1] for r in rows):
        width -= 1
        rows = [r[:width] for r in rows]
    return rows


def rows_to_md(rows):
    return "\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
                     + ["| " + " | ".join(r) + " |" for r in rows[1:]])


def merge_split_tables(tables, lines, report):
    """Таблица, продолжающаяся на следующей странице, в PDF выглядит как две (или больше) таблицы:
    первая упирается в низ страницы, вторая начинается у верха, текста между ними нет.
    Части склеиваются; повтор шапки убирается; строка, разрезанная границей страницы
    (первая строка продолжения без номера или с маленькой буквы), дописывается к последней строке."""
    keys = sorted(tables); out = {}; i = 0
    while i < len(keys):
        k = keys[i]; rows = drop_trailing_empty_cols(tables[k]["rows"]); last = k; j = i + 1
        while j < len(keys):
            k2 = keys[j]; cur = tables[last]
            if k2[0] != last[0] + 1 or cur["y1"] < cur["h"] - 100 or k2[1] > 150:
                break
            if any((ln["page"] == last[0] and ln["y"] > cur["y1"]) or (ln["page"] == k2[0] and ln["y"] < k2[1]) for ln in lines):
                break                                            # между частями есть текст - это разные таблицы
            rows2 = drop_trailing_empty_cols(tables[k2]["rows"])
            if len(rows2[0]) != len(rows[0]):
                report.append(f"таблица на стр. {last[0] + 1} и стр. {k2[0] + 1}: похоже на одну таблицу, но число столбцов разное ({len(rows[0])} и {len(rows2[0])}), склейте вручную")
                break
            if rows2 and rows2[0] == rows[0]:
                rows2 = rows2[1:]                                # повтор шапки на новой странице
            if rows2 and (not rows2[0][0] or re.match(r"[a-zа-яёөүҥһ]", rows2[0][0])):
                rows[-1] = [(a + " " + b).strip() if b else a for a, b in zip(rows[-1], rows2[0])]
                rows2 = rows2[1:]                                # строка, разрезанная границей страницы
            rows += rows2
            report.append(f"таблица на стр. {last[0] + 1} продолжается на стр. {k2[0] + 1}: части склеены, проверьте")
            last = k2; j += 1
        out[k] = rows_to_md(rows); i = j
    return out


PAGES_ALL = {}   # имя файла -> число страниц, для docs.json страницы проверки


def convert(pdf_path, report):
    doc = pymupdf.open(pdf_path)
    lines = []; tables = {}; tables_text = []
    for pno, page in enumerate(doc):
        try:
            tabs = page.find_tables(strategy="lines_strict")   # только реальные линии: невидимые сетки вёрстки не ловит
        except Exception:
            tabs = None
        accepted = []
        if tabs and tabs.tables:
            draws = page.get_drawings()
            for t in tabs.tables:
                data = t.extract()
                if not data or len(data) < 2 or len(data[0]) < 2:
                    continue
                # В этих PDF обычный текст часто свёрстан невидимыми таблицами: сетка есть, но все её
                # линии - белые заливки. У настоящих таблиц границы чёрные (заливка или обводка).
                R = pymupdf.Rect(t.bbox)
                def dark(c):
                    return c is not None and max(c) < 0.5
                visible = any(pymupdf.Rect(d["rect"]).intersects(R) and (dark(d.get("fill")) or dark(d.get("color"))) for d in draws)
                if not visible:
                    report.append(f"сетка без видимых границ {len(data)}x{len(data[0])} на стр. {pno + 1} оставлена текстом, взгляните")
                    continue
                cell = lambda c: re.sub(r"\s+", " ", (c or "")).strip().replace("|", "\\|")
                tables[(pno, t.bbox[1])] = {"rows": [[cell(c) for c in row] for row in data], "y1": t.bbox[3], "h": page.rect.height}
                tables_text.append("".join((c or "") for row in data for c in row))
                accepted.append(pymupdf.Rect(t.bbox))
                report.append(f"таблица на стр. {pno + 1}: {len(data)} строк x {len(data[0])} столбцов, проверьте")
        # строки страницы без содержимого таблиц; текст сбоку от таблицы (например «».») остаётся
        lines.extend(page_lines(page, pno, accepted))
    if not lines:
        report.append("НЕТ ТЕКСТОВОГО СЛОЯ")
        return ""
    # номера страниц сверху страниц 2+
    lines = [ln for ln in lines if not (ln["page"] > 0 and re.fullmatch(r"\d{1,2}", ln["text"]) and ln["y"] < 90)]
    # черта из подчёркиваний перед сноской: оформление, а не текст
    lines = [ln for ln in lines if not re.fullmatch(r"_{5,}", ln["text"].strip())]
    tables_md = merge_split_tables(tables, lines, report)

    # подписной блок: строка с «№ <номер указа>» (номер = имя файла); перед ней дата, должность и подпись.
    # Ищем по всему документу: после подписи могут идти приложения.
    sig = None; after = []
    stem = re.sub(r"\D", "", os.path.splitext(os.path.basename(pdf_path))[0])
    num_exact = re.compile(rf"(№\s*{stem}|{stem}\s*№)\s*$") if stem else None
    # кандидаты: строки с номером указа (в приложениях он тоже встречается: «от ... № 831»),
    # берём первую, над которой есть жирная должность и/или фамилия
    cands = [i for i in range(len(lines)) if num_exact and num_exact.search(lines[i]["text"])]
    if not cands:
        cands = [i for i in range(len(lines) - 1, max(-1, len(lines) - 8), -1) if NUM_ANY.search(lines[i]["text"])]
    parsed = None
    for idx in cands:
        m = (num_exact.search(lines[idx]["text"]) if num_exact else None) or NUM_ANY.search(lines[idx]["text"])
        num = m.group(1).strip(); date = lines[idx]["text"][: m.start()].strip()
        if re.match(r"^(от|к)\s", date, re.I):
            continue                        # «от 22 января 2026 г. № 831» - ссылка в приложении, не подпись
        j = idx - 1
        if not date and j >= 0 and re.search(r"\d{4}", lines[j]["text"]):
            date = lines[j]["text"]; j -= 1
        name = ""; pos_parts = []; k = j; sig_bold = []
        while k >= 0 and j - k < 4:
            t = lines[k]["text"]
            mm = NAME_TAIL.search(" " + t)
            if mm and not name:
                name = mm.group(1).strip(); t = (" " + t)[: mm.start()].strip()
            if not (lines[k]["bold"] or mm or (name and len(pos_parts) < 2 and len(t) < 40)):
                break
            if t:
                pos_parts.insert(0, t)
            sig_bold.append(lines[k]["bold"])
            k -= 1
        if pos_parts or name:
            # должность и фамилия в PDF набраны жирным - по разделу 3.3 ТЗ выделяем **…**; дата и номер обычные
            b = "**" if sig_bold and all(sig_bold) else ""
            pos_md = (b + " ".join(pos_parts) + b) if pos_parts else ""
            name_md = (b + name + b) if name else ""
            parsed = (idx, k, {"pos": pos_md, "name": name_md, "date": date, "num": num, "plain": " ".join(pos_parts) + name})
            break
    if parsed:
        idx, k, sig = parsed
        after = lines[idx + 1:]
        lines = lines[: k + 1]
        if not sig["name"]:
            report.append("подписной блок: не нашёл фамилию, проверьте таблицу подписи")
        if not sig["date"]:
            report.append("подписной блок: не нашёл дату, проверьте таблицу подписи")
    elif cands:
        report.append("подписной блок не распознан, оформите таблицу вручную")
    else:
        report.append("подписной блок: не найден номер «№ ...», оформите таблицу вручную")

    xs = sorted(ln["x0"] for ln in lines + after if not ln["bold"]) or sorted(ln["x0"] for ln in lines + after)
    left = xs[max(0, int(len(xs) * 0.1))] if xs else 85
    page_top = {}                                   # верх текста на каждой странице
    for ln in lines + after:
        page_top[ln["page"]] = min(page_top.get(ln["page"], 1e9), ln["y"])
    paras_before, centered = build_paragraphs(lines, left)
    paras_after, _ = build_paragraphs(after, left)

    out = []; heading_seen = False
    table_keys = sorted(tables_md)
    # признаки блока «Приложение к Указу…» / «…Ыйааҕар сыһыарыы» / «УТВЕРЖДЕН…» перед заголовком приложения
    APPENDIX_KEYS = ("приложение", "к указу", "утвержден", "сыһыарыы", "бигэргэ")   # бигэргэтиллибит / бигэргэммит / бигэргэннэ
    def emit(paras, appendix=False):
        """Абзацы -> Markdown. Пункты указа «N.» - список первого уровня, подпункты «N)» - вложенный
        список (сдвиг на ширину маркера родителя), остальные абзацы и таблицы внутри пункта сдвигаются
        до его текста. INDENT - красная строка широкими пробелами, ALIGN - выравнивание HTML-тегами."""
        nonlocal heading_seen
        prev_text = ""
        stack = []                                   # уровни списка: {"kind": "."|")", "next": ожидаемый номер, "indent": колонка маркера, "col": колонка текста}
        kind = None                                  # что было перед абзацем: text / heading / table / right

        def cur_col():
            return stack[-1]["col"] if stack else 0

        def push(text, col):
            pad = " " * col
            out.append("\n".join((pad + l) if l.strip() else l for l in text.split("\n")))

        def heading(level, text):
            stack.clear()
            if ALIGN:
                out.append(f'<div align="center">\n\n{"#" * level} {text}\n\n</div>')
            else:
                out.append(f'{"#" * level} {text}')

        for p in paras:
            prev_kind = kind; kind = "text"
            while table_keys and (table_keys[0][0] < p[0]["page"] or (table_keys[0][0] == p[0]["page"] and table_keys[0][1] < p[0]["y"])):
                push(tables_md[table_keys.pop(0)], cur_col()); prev_kind = "table"
            all_bold = all(ln["bold"] for ln in p)
            plain = " ".join(ln["text"] for ln in p)
            if all_bold and (any(centered(ln) for ln in p) or not heading_seen):
                if not heading_seen:
                    heading(1, plain); heading_seen = True                  # заголовок указа
                elif appendix and (not prev_text or any(k in prev_text.lower() for k in APPENDIX_KEYS)):
                    heading(1, plain)                                        # заголовок приложения - отдельный документ
                    if re.search(r"структур", plain, re.I):
                        report.append("приложение «Структура» это схема из блоков: текст перенесён, расположение блоков оформите вручную")
                elif re.match(r"^\d+\.\d+", plain):
                    heading(3, plain)
                else:
                    heading(2, plain)
                prev_text = plain; kind = "heading"
                continue
            text = join_lines(p)
            mnum = re.match(r"^(\d+)([.)])\s", text)                          # пункт «1. » или подпункт «1) »
            if mnum:
                n, kind = int(mnum.group(1)), mnum.group(2)
                m2 = re.match(r"\d+([.)])\s", text[mnum.end():])
                if m2:                                                       # «2. 2. Текст»: второй маркер экранируем
                    k = mnum.end() + m2.start(1)
                    text = text[:k] + "\\" + text[k:]
                lvl = next((k for k in range(len(stack) - 1, -1, -1) if stack[k]["kind"] == kind and stack[k]["next"] == n), None)
                if lvl is not None:                                          # продолжение уровня, который ждёт этот номер
                    del stack[lvl + 1:]
                    stack[lvl]["next"] = n + 1
                    push(text, stack[lvl]["indent"])
                else:                                                        # новая нумерация: список глубже текущего текста
                    if n != 1 and any(e["kind"] == kind for e in stack):
                        report.append(f"нумерация: после пункта «{stack[-1]['next'] - 1}{stack[-1]['kind']}» идёт «{n}{kind}», оформлен как вложенный список, проверьте")
                    indent = cur_col()
                    inner = bool(stack) and (n != 1 or any(e["kind"] == kind for e in stack))
                    stack.append({"kind": kind, "next": n + 1, "indent": indent, "col": indent + len(mnum.group(0)), "inner": inner})
                    push(text, indent)
            else:
                while stack and stack[-1].get("inner"):                      # обычный абзац закрывает список вставляемого текста
                    stack.pop()
                first = p[0]
                # блок справа («Приложение / к Указу…», «УТВЕРЖДЕН»): в начале страницы либо после заголовка, таблицы или
                # такого же блока. Продолжение записи с висячим отступом посреди текста сюда не попадает.
                first_on_page = first["y"] <= page_top.get(first["page"], 0) + 2
                right = (first["x0"] > first["width"] * 0.5 and not centered(first) and re.search(r"\w", text)
                         and (first_on_page or prev_kind in (None, "right", "heading", "table")))
                if re.match(r"^[*+]\s", text):
                    text = "\\" + text                                      # «* - сноска»: звёздочка в начале строки это маркер списка
                if ALIGN and right:
                    text = '<p align="right">' + "<br>".join(spans_to_md(ln["spans"]) for ln in p) + "</p>"; kind = "right"
                elif ALIGN and all(centered(ln) for ln in p) and first["x0"] > left + 70:   # подпись таблицы и т.п., в том числе внутри пункта
                    text = '<p align="center">' + text + "</p>"
                elif INDENT and left + 12 < first["x0"] <= left + 70:
                    text = "&emsp;&emsp;" + text                            # красная строка: два широких пробела
                push(text, cur_col())
            prev_text = plain
    emit(paras_before)
    if sig:
        while table_keys and after and (table_keys[0][0] < after[0]["page"] or (table_keys[0][0] == after[0]["page"] and table_keys[0][1] < after[0]["y"])) and False:
            pass
        out.append(f"| {sig['pos']} | {sig['name']} |\n|---|---|\n| {sig['date']} | {sig['num']} |")
    emit(paras_after, appendix=True)
    while table_keys:
        out.append(tables_md[table_keys.pop(0)])

    md = "\n\n".join(x for x in out if x.strip()) + "\n"
    # мелкая гигиена пробелов у знаков препинания; отступы в начале строк не трогаем
    md = re.sub(r"(?<=\S) ([,.»])", r"\1", md).replace("« ", "«")
    if HYPHEN_JOINS:
        report.append("дефис на границе строки склеен без пробела: " + "; ".join("…" + h for h in HYPHEN_JOINS[:3]) + (" и ещё" if len(HYPHEN_JOINS) > 3 else "") + " - проверьте")
        HYPHEN_JOINS.clear()
    # полнота: буквы и цифры исходника (без шапки и номеров страниц) против результата
    src = "".join(ln["text"] for ln in lines + after) + "".join(tables_text)
    if sig:
        src += sig.get("plain", "") + sig["date"] + sig["num"]
    src_plain = re.sub(WORD_CHARS, "", src); md_plain = re.sub(WORD_CHARS, "", md.replace("&emsp;", ""))   # сущности отступа не текст
    if src_plain:
        ratio = len(md_plain) / len(src_plain)
        if ratio < 0.985 or ratio > 1.015:
            report.append(f"ПОЛНОТА: в Markdown {ratio:.1%} знаков от исходника, проверьте пропуски")
    return md


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")       # буквы вне кодировки консоли не роняют скрипт
    src, dst = args[0], args[1]
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    report_all = {}
    for lang in ("ru", "sah"):
        d = os.path.join(src, lang)
        if not os.path.isdir(d):
            continue
        os.makedirs(os.path.join(dst, lang), exist_ok=True)
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(".pdf"):
                continue
            rel = f"{lang}/{f}"
            if only and rel not in only:
                continue
            rep = []
            md = convert(os.path.join(d, f), rep)
            with open(os.path.join(dst, lang, os.path.splitext(f)[0] + ".md"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(md)
            report_all[rel] = rep
            PAGES_ALL[rel] = len(pymupdf.open(os.path.join(d, f)))
    rep_path = os.path.join(dst, "report.json"); docs_path = os.path.join(dst, "docs.json")
    if only and os.path.exists(rep_path):                        # частичный прогон: дополняем прежний отчёт
        old = json.load(open(rep_path, encoding="utf-8")); old.update(report_all); report_all = old
        if os.path.exists(docs_path):
            for dd in json.load(open(docs_path, encoding="utf-8")):
                PAGES_ALL.setdefault(dd["id"] + ".pdf", dd["pages"])
    with open(rep_path, "w", encoding="utf-8") as fh:
        json.dump(report_all, fh, ensure_ascii=False, indent=1)
    docs = [{"id": k[:-4], "pages": PAGES_ALL.get(k, 0), "flags": v} for k, v in report_all.items()]
    docs.sort(key=lambda dd: (dd["id"].split("/")[0], len(dd["id"]), dd["id"]))
    with open(docs_path, "w", encoding="utf-8") as fh:
        json.dump(docs, fh, ensure_ascii=False)
    flagged = {k: v for k, v in report_all.items() if v}
    print(f"готово: {len(report_all)} файлов, с замечаниями {len(flagged)} -> {dst}")
    for k, v in list(flagged.items())[:40]:
        print(" ", k, "|", "; ".join(v))


if __name__ == "__main__":
    main()
