#!/usr/bin/env python3
"""
Достаёт content.xml из .siq (ZIP) даже со сломанной центральной директорией.
Читает локальные заголовки файлов подряд от начала архива и не полагается
на central directory. Если данные content.xml повреждены — пытается восстановить
хотя бы начало (до первого сбоя), чего обычно хватает, чтобы прочитать темы.

Использование:
    python tools/extract_content_xml.py Zengame.siq content/zengame_content.xml
"""
import os
import struct
import sys
import zlib


def walk_and_extract(data: bytes, target: bytes, out_path: str) -> int:
    LFH = b"PK\x03\x04"
    pos = data.find(LFH)
    while pos != -1 and pos + 30 <= len(data):
        (sig, ver, flags, method, mt, md, crc,
         csize, usize, fnlen, eflen) = struct.unpack("<IHHHHHIIIHH", data[pos:pos + 30])
        name = data[pos + 30:pos + 30 + fnlen]
        dstart = pos + 30 + fnlen + eflen
        comp = data[dstart:dstart + csize]

        if name == target:
            print(f"  found {target.decode()} at offset {pos}: method={method} "
                  f"csize={csize} usize={usize}")
            raw = None
            if method in (0, 8):
                try:
                    raw = comp if method == 0 else zlib.decompress(comp, -15)
                    print(f"  full extraction OK: {len(raw)} bytes")
                except zlib.error as e:
                    print(f"  full decompress failed ({e}); пробую частичное восстановление...")
                    # Декомпрессия чанками — сохраняем всё, что удалось до сбоя
                    do = zlib.decompressobj(-15)
                    out = bytearray()
                    step = 4096
                    for i in range(0, len(comp), step):
                        try:
                            out += do.decompress(comp[i:i + step])
                        except zlib.error:
                            break
                    raw = bytes(out)
                    print(f"  частичное восстановление: {len(raw)} байт из {usize}")
            else:
                print(f"  неизвестный метод сжатия {method}")

            if raw:
                os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(raw)
                print(f"  >>> сохранено в {out_path}")
                return 0
            print("  content.xml не восстановить :(")
            return 2

        if csize == 0:
            # streamed-запись — не можем надёжно перейти к следующему
            break
        pos = data.find(LFH, dstart + max(csize, 1))

    print("  content.xml не найден среди локальных заголовков.")
    return 3


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else "Zengame.siq"
    dst = sys.argv[2] if len(sys.argv) > 2 else "content/zengame_content.xml"
    if not os.path.exists(src):
        print(f"файл не найден: {src}")
        return 1
    with open(src, "rb") as f:
        data = f.read()
    print(f"читаю {src}: {len(data)} байт")
    return walk_and_extract(data, b"content.xml", dst)


if __name__ == "__main__":
    raise SystemExit(main())
