#!/usr/bin/env python3
"""
Сборщик пакета SIGame (.siq) из человеко-читаемого источника content/package.yaml.

Формат .siq: ZIP-архив, содержащий:
  - content.xml      — основной XML с вопросами (формат v4, namespace ygpackage3.0.xsd)
  - [Content].xml    — копия content.xml для совместимости со старыми читалками
  - Images/<файл>    — картинки, на которые ссылается @Images\\<файл>
  - Audio/<файл>     — звук (@Audio\\<файл>)
  - Video/<файл>     — видео (@Video\\<файл>)

Запуск:
    python3 tools/build_package.py            # собирает content/package.yaml -> *.siq
    python3 tools/build_package.py --validate # дополнительно валидирует content.xml по XSD

Зависимости: PyYAML. Опционально: xmlschema (для --validate).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import sys
import uuid
import zipfile
from pathlib import Path

import yaml

NS = "http://vladimirkhil.com/ygpackage3.0.xsd"
ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
SOURCE = CONTENT_DIR / "package.yaml"
XSD = ROOT / "tools" / "ygpackage3.1.xsd"

# Стабильный идентификатор пакета (не меняется при пересборке)
PKG_GUID = "7f3c9a1e-2b54-4e7d-8c01-9a6f4b2e0d77"


def _esc(text) -> str:
    """Экранирование текста для XML-содержимого."""
    return html.escape("" if text is None else str(text), quote=False)


def _attr(text) -> str:
    """Экранирование для значения атрибута."""
    return html.escape("" if text is None else str(text), quote=True)


def info_block(authors=None, sources=None, comments="") -> str:
    a = "".join(f"<author>{_esc(t)}</author>" for t in (authors or []))
    s = "".join(f"<source>{_esc(t)}</source>" for t in (sources or []))
    return (
        f"<info><authors>{a}</authors><sources>{s}</sources>"
        f"<comments>{_esc(comments)}</comments></info>"
    )


# Папка для каждого типа медиа
MEDIA_DIRS = {"image": "Images", "voice": "Audio", "video": "Video"}


def media_ref(kind: str, filename: str) -> str:
    folder = MEDIA_DIRS[kind]
    return f"@{folder}\\{filename}"


def build_scenario(q: dict) -> tuple[str, list[tuple[str, str]]]:
    """Собирает <scenario> и возвращает список (папка, имя_файла) для упаковки."""
    media: list[tuple[str, str]] = []
    atoms: list[str] = []

    def add_media(kind, key):
        fn = q.get(key)
        if fn:
            atoms.append(f'<atom type="{kind}">{_attr(media_ref(kind, fn))}</atom>')
            media.append((MEDIA_DIRS[kind], fn))

    # Часть вопроса
    if q.get("say"):
        atoms.append(f'<atom type="say">{_esc(q["say"])}</atom>')
    if q.get("text"):
        atoms.append(f'<atom type="text">{_esc(q["text"])}</atom>')
    add_media("image", "image")
    add_media("voice", "voice")
    add_media("video", "video")

    # Часть ответа (после маркера)
    answer_bits: list[str] = []
    if q.get("answer_text"):
        answer_bits.append(f'<atom type="text">{_esc(q["answer_text"])}</atom>')
    if q.get("answer_image"):
        fn = q["answer_image"]
        answer_bits.append(f'<atom type="image">{_attr(media_ref("image", fn))}</atom>')
        media.append((MEDIA_DIRS["image"], fn))
    if answer_bits:
        atoms.append('<atom type="marker"/>')
        atoms.extend(answer_bits)

    return "<scenario>" + "".join(atoms) + "</scenario>", media


def build_question(q: dict) -> tuple[str, list[tuple[str, str]]]:
    price = q.get("price")
    if price is None:
        raise ValueError("У вопроса не указана цена (price)")
    qtype = q.get("type", "simple")
    scenario, media = build_scenario(q)

    answers = q.get("answers")
    if not answers and q.get("answer"):
        answers = [q["answer"]]
    if not answers:
        raise ValueError(f"Вопрос (цена {price}) без ответа: {q.get('say') or q.get('text')}")
    right = "".join(f"<answer>{_esc(a)}</answer>" for a in answers)

    wrongs = q.get("wrong", []) or []
    wrong = "".join(f"<answer>{_esc(a)}</answer>" for a in wrongs)

    pieces = [
        f'<question price="{int(price)}">',
        info_block(comments=q.get("comment", "")),
        f'<type name="{_attr(qtype)}"/>',
        scenario,
        f"<right>{right}</right>",
        f"<wrong>{wrong}</wrong>",
        "</question>",
    ]
    return "".join(pieces), media


def build_theme(theme: dict) -> tuple[str, list[tuple[str, str]]]:
    media: list[tuple[str, str]] = []
    qs = theme.get("questions", [])
    qxml = []
    for q in qs:
        qx, m = build_question(q)
        qxml.append(qx)
        media.extend(m)
    body = "".join(qxml)
    return (
        f'<theme name="{_attr(theme["name"])}">'
        + info_block(comments=theme.get("comment", ""))
        + f"<questions>{body}</questions></theme>",
        media,
    )


def build_round(round_: dict) -> tuple[str, list[tuple[str, str]]]:
    media: list[tuple[str, str]] = []
    themes_xml = []
    for th in round_.get("themes", []):
        tx, m = build_theme(th)
        themes_xml.append(tx)
        media.extend(m)
    rtype = round_.get("type", "standart")
    if rtype not in ("standart", "final"):
        raise ValueError(f"Неизвестный тип раунда: {rtype} (нужно standart или final)")
    return (
        f'<round name="{_attr(round_["name"])}" type="{rtype}">'
        + info_block(comments=round_.get("comment", ""))
        + f"<themes>{''.join(themes_xml)}</themes></round>",
        media,
    )


def build_content_xml(pkg: dict) -> tuple[str, list[tuple[str, str]]]:
    media: list[tuple[str, str]] = []
    rounds_xml = []
    for r in pkg.get("rounds", []):
        rx, m = build_round(r)
        rounds_xml.append(rx)
        media.extend(m)

    authors = pkg.get("authors") or [pkg.get("author", "")]
    tags_xml = ""
    if pkg.get("tags"):
        tags_xml = "<tags>" + "".join(f"<tag>{_esc(t)}</tag>" for t in pkg["tags"]) + "</tags>"

    attrs = [
        f'id="{_attr(pkg.get("id", PKG_GUID))}"',
        f'name="{_attr(pkg["name"])}"',
        'version="4"',
    ]
    for opt in ("restriction", "date", "publisher", "difficulty", "logo", "language"):
        if pkg.get(opt) is not None and pkg.get(opt) != "":
            attrs.append(f'{opt}="{_attr(pkg[opt])}"')

    date = pkg.get("date") or _dt.date.today().isoformat()
    info = info_block(
        authors=[a for a in authors if a],
        sources=pkg.get("sources"),
        comments=pkg.get("comments", ""),
    )

    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<package xmlns="{NS}" '
        + " ".join(attrs)
        + ">"
        + tags_xml
        + info
        + "<rounds>" + "".join(rounds_xml) + "</rounds>"
        + "</package>"
    )
    return xml, media


def write_siq(xml: str, media: list[tuple[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", xml)
        # Копия под старым именем для совместимости со старыми версиями SIGame
        zf.writestr("[Content].xml", xml)
        seen = set()
        for folder, fn in media:
            key = (folder, fn)
            if key in seen:
                continue
            seen.add(key)
            src = CONTENT_DIR / folder / fn
            if not src.exists():
                raise FileNotFoundError(f"Медиафайл не найден: {src}")
            zf.write(src, arcname=f"{folder}/{fn}")


def validate(xml: str) -> bool:
    try:
        import xmlschema  # type: ignore
    except ImportError:
        print("[validate] xmlschema не установлен — пропускаю XSD-проверку", file=sys.stderr)
        return True
    if not XSD.exists():
        print(f"[validate] XSD не найден: {XSD} — пропускаю", file=sys.stderr)
        return True
    schema = xmlschema.XMLSchema(str(XSD))
    errors = list(schema.iter_errors(xml))
    if errors:
        print(f"[validate] Найдено {len(errors)} ошибок схемы:", file=sys.stderr)
        for e in errors[:20]:
            print(f"  - {e}", file=sys.stderr)
        return False
    print("[validate] content.xml соответствует схеме ygpackage3.1.xsd ✓")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Сборка пакета SIGame (.siq)")
    ap.add_argument("source", nargs="?", default=str(SOURCE), help="путь к package.yaml")
    ap.add_argument("-o", "--output", default=None, help="выходной .siq (по умолчанию рядом с источником)")
    ap.add_argument("--validate", action="store_true", help="проверить content.xml по XSD")
    args = ap.parse_args()

    src = Path(args.source)
    with open(src, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    pkg = data["package"] if "package" in data else data

    xml, media = build_content_xml(pkg)

    # Базовая проверка well-formedness
    import xml.etree.ElementTree as ET
    ET.fromstring(xml)

    if args.validate:
        if not validate(xml):
            return 1

    if args.output:
        out = Path(args.output)
    else:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in pkg["name"]).strip() or "package"
        out = ROOT / f"{safe}.siq"
    write_siq(xml, media, out)
    print(f"Готово: {out}  ({out.stat().st_size} байт, {len(set(media))} медиафайлов)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
