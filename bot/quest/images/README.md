# Медиа ARG «Аргус-1001»

Зависимости: `pip install -r bot/tools/requirements.txt`.
Пересборка: `python3 bot/tools/make_quest_assets.py`.

Все файлы принадлежат узлам N1–N6 (см. `bot/docs/QUEST_WALKTHROUGH.md`).
`n1_card.jpg` шлётся как document, иначе Telegram сожмёт EXIF и хвост JPEG.
N2 использует связанную цепочку `n2_reversed.wav` → `n2_spec.wav` → `n2_cipher.wav`.
