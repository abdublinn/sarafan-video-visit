"""Синхронизирует обсидиановские .md из корня репозитория в docs/ для MkDocs.

Что делает:
  1. Транслитерирует имена файлов в kebab-case (для красивых URL).
  2. Конвертирует wikilinks [[Name]] и [[Name|Display]] в обычные [Display](slug.md).
  3. Конвертирует [[Name#Anchor]] в [Display](slug.md#anchor).
  4. Callouts (> [!info]) MkDocs Material рендерит через плагин mkdocs-callouts
     автоматически, конвертировать не нужно.

Запуск: python scripts/sync.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

MAPPING = {
    "00 Процесс подготовки видео-визита": "index",
    "01 Стартовая карточка кейса": "01-startovaya-kartochka",
    "02 Опросный лист для менеджера проекта": "02-oprosnyy-list",
    "03 ТЗ — сбор и обработка данных Битрикс": "03-tz-bitrix",
    "04 OSINT-чек-лист — пробив клиента": "04-osint",
    "05 Досье клиента (шаблон сборки)": "05-dosye-klienta",
    "06 ТЗ — генерация сценариев роликов": "06-tz-stsenariy",
    "07 Сценарий ролика (шаблон)": "07-stsenariy",
    "08 Памятка съёмочной группы": "08-pamyatka",
}


def slugify_anchor(anchor: str) -> str:
    """MkDocs Material делает якоря из заголовков в kebab-case латиницей.
    Для русских заголовков якоря не работают как есть; оставляем как написано,
    пользователь может уточнить вручную при необходимости."""
    a = anchor.strip().lower()
    a = re.sub(r"[\s_]+", "-", a)
    a = re.sub(r"[^\w\-а-яё]", "", a, flags=re.UNICODE)
    return a


def convert_wikilinks(text: str) -> str:
    def repl(match: re.Match) -> str:
        body = match.group(1)
        if "|" in body:
            target, display = body.split("|", 1)
        else:
            target, display = body, body
        if "#" in target:
            base, anchor = target.split("#", 1)
        else:
            base, anchor = target, ""
        base = base.strip()
        slug = MAPPING.get(base, base)
        href = f"{slug}.md"
        if anchor:
            href += "#" + slugify_anchor(anchor)
        return f"[{display.strip()}]({href})"

    return re.sub(r"\[\[([^\]]+)\]\]", repl, text)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    written = []
    for src_name, dst_name in MAPPING.items():
        src = ROOT / f"{src_name}.md"
        if not src.exists():
            print(f"MISSING: {src}")
            continue
        content = src.read_text(encoding="utf-8")
        content = convert_wikilinks(content)
        (DOCS / f"{dst_name}.md").write_text(content, encoding="utf-8")
        written.append(dst_name)
    print(f"OK: written {len(written)} files to {DOCS}")


if __name__ == "__main__":
    main()
