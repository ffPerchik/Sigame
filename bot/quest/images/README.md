# Медиа ARG «Аргус-1001»

Зависимости: `pip install -r bot/tools/requirements.txt`.
Пересборка: `python3 bot/tools/make_quest_assets.py`.

Все файлы принадлежат узлам N1–N6 (см. `bot/docs/QUEST_WALKTHROUGH.md`).
`n1_card.jpg` шлётся как document, иначе Telegram сожмёт EXIF и хвост JPEG.
N2 использует связанную цепочку `n2_1.wav` → `n2_2.wav` → `n2_3.wav`;
в последнем файле скрытая спектрограмма наложена на слышимый вальс.
Файлы N3–N6 называются нейтрально (`artifact_*`), чтобы имя не выдавало метод решения.
