"""Готовит исходные .md из корня проекта к публикации на сайте.

Что делает:
  1. Транслитерирует имена файлов в kebab-case (чтобы URL были чистые).
  2. Переписывает wikilinks [[Имя]] и [[Имя|Текст]] в обычные [Текст](slug.md).
  3. Кладёт результат в docs/.
  4. Конвертирует каждый документ в Word (.docx) через pandoc, складывает в docs/downloads/.
  5. В начало каждого документа в docs/ добавляет кнопку «Скачать документ в Word».

Запуск: python scripts/sync.py
Требования: pandoc в PATH.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"

# Маппинг исходного имени файла (без .md) → slug для сайта и для downloads
MAPPING = {
    "00 Процесс подготовки видео-визита": ("index", "00 Процесс подготовки видео-визита"),
    "01 Стартовая карточка кейса": ("01-startovaya-kartochka", "01 Стартовая карточка клиента"),
    "02 Опросный лист для менеджера проекта": ("02-oprosnyy-list", "02 Опросный лист для менеджера проекта"),
    "03 ТЗ — сбор и обработка данных Битрикс": ("03-tz-bitrix", "03 Сбор и обработка данных Битрикс"),
    "04 OSINT-чек-лист — пробив клиента": ("04-osint", "04 Изучение клиента по открытым источникам"),
    "05 Досье клиента (шаблон сборки)": ("05-dosye-klienta", "05 Досье клиента"),
    "06 ТЗ — генерация сценариев роликов": ("06-tz-stsenariy", "06 Задание нейросети на сценарии"),
    "07 Сценарий ролика (шаблон)": ("07-stsenariy", "07 Сценарий ролика"),
    "08 Памятка съёмочной группы": ("08-pamyatka", "08 Памятка съёмочной группы"),
}


def slugify_anchor(anchor: str) -> str:
    a = anchor.strip().lower()
    a = re.sub(r"[\s_]+", "-", a)
    a = re.sub(r"[^\w\-а-яё]", "", a, flags=re.UNICODE)
    return a


def convert_wikilinks(text: str) -> str:
    slug_only_map = {src: dst[0] for src, dst in MAPPING.items()}

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
        slug = slug_only_map.get(base, base)
        href = f"{slug}.md"
        if anchor:
            href += "#" + slugify_anchor(anchor)
        return f"[{display.strip()}]({href})"

    return re.sub(r"\[\[([^\]]+)\]\]", repl, text)


def add_download_button(content: str, docx_name: str, slug: str) -> str:
    """Добавляет кнопку скачивания .docx после первого заголовка H1."""
    button = (
        f'\n\n[Скачать документ в Word]'
        f'(downloads/{slug}.docx){{ .md-button .md-button--primary download="{docx_name}" }}\n\n'
    )
    # вставляем после первой строки, начинающейся с "# "
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, button)
            return "\n".join(lines)
    # если H1 не нашли — добавляем в самое начало
    return button + content


def strip_obsidian_callouts(text: str) -> str:
    """Конвертирует обсидиановские callouts в pandoc-совместимый формат.
    pandoc сам не понимает > [!info], но понимает обычные blockquote.
    Превращаем > [!type] Заголовок → > **Заголовок** (или просто blockquote).
    """
    def repl(m: re.Match) -> str:
        callout_type = m.group(1).upper()
        title = m.group(2).strip()
        type_to_label = {
            "INFO": "ℹ Информация",
            "TIP": "💡 Совет",
            "WARNING": "⚠ Внимание",
            "CHECK": "✓ Проверка",
            "SUCCESS": "✓ Готово",
            "QUOTE": "❝ Цитата",
            "NOTE": "Заметка",
            "BUG": "Проблема",
            "EXAMPLE": "Пример",
        }
        label = type_to_label.get(callout_type, callout_type.title())
        if title:
            return f"> **{label}: {title}**"
        return f"> **{label}**"

    return re.sub(
        r"^> \[!(\w+)\][\-\+]?\s*(.*)$",
        repl,
        text,
        flags=re.MULTILINE,
    )


def make_docx(md_path: Path, docx_path: Path) -> bool:
    """Конвертирует один .md → .docx через pandoc.
    Возвращает True при успехе.
    """
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pandoc",
        str(md_path),
        "-o", str(docx_path),
        "--from", "gfm+yaml_metadata_block",
        "--to", "docx",
        "--standalone",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"  pandoc ERROR for {md_path.name}: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError:
        print("  pandoc not found in PATH — skipping .docx generation", file=sys.stderr)
        return False


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    written_md = 0
    written_docx = 0

    for src_name, (slug, docx_basename) in MAPPING.items():
        src_file = ROOT / f"{src_name}.md"
        if not src_file.exists():
            print(f"MISSING: {src_file}")
            continue

        raw = src_file.read_text(encoding="utf-8")

        # Версия для сайта: с переписанными wikilinks и кнопкой скачивания
        site_content = convert_wikilinks(raw)
        site_content = add_download_button(site_content, f"{docx_basename}.docx", slug)
        site_md = DOCS / f"{slug}.md"
        site_md.write_text(site_content, encoding="utf-8")
        written_md += 1

        # Версия для Word: исходный текст с конвертированными callouts (без кнопки)
        docx_md = ROOT / f".tmp-docx-{slug}.md"
        docx_content = strip_obsidian_callouts(raw)
        docx_content = re.sub(r"\[\[([^\]|]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), docx_content)
        docx_md.write_text(docx_content, encoding="utf-8")

        docx_out = DOWNLOADS / f"{slug}.docx"
        if make_docx(docx_md, docx_out):
            written_docx += 1
        docx_md.unlink(missing_ok=True)

    print(f"OK: {written_md} .md to docs/, {written_docx} .docx to docs/downloads/")


if __name__ == "__main__":
    main()
