# N4 · Сценарий узла «НАБЛЮДЕНИЕ» (новый концепт, v1)

Статус: РЕАЛИЗОВАНО. Сборка `bot/tools/make_n4_video.py` (сток Tokyo 4451),
стейджи N4_* в stages.yaml перезаписаны, QR-декод проверен.
Усложнено (4 загадки): hex разрезан на 2 глитч-кадра; буквы ВЗГЛЯД по кадрам;
LOG в hex; QR-ловушка CAM3TRAP в середине + зеркальная метка CAM3EYE в конце.
Осталось: залить artifact_4a.mp4 на YouTube (unlisted), вписать ссылку
в `N4_vid` вместо `TODO_YOUTUBE_LINK` и добавить в описание `LOG 0C 06 0E 08 01`.

## Концепция

Аргус «перехватил» архив уличной камеры CAM-3, который оператор выложил
на YouTube (unlisted). Игрок: смотрит видео → ловит вспышку-кадр → копает
метаданные YouTube → сканирует QR прямо с экрана на паузе.
Связь с внешним миром: реальная ссылка, реальный канал, реальный QR.

## Структура (3 загадки → фрагмент НАБЛЮДАЙ)

| # | Стейдж | Механика | Ответ |
|---|--------|----------|-------|
| 1 | N4_flash | Вспышка ~0.4 c в середине ролика: тёмный глитч-кадр с hex-строка `d0 a8 d0 a3 d0 9c`. Hex UTF-8 → слово | **ШУМ** |
| 2 | N4_meta | Шифр в описании YouTube: строка `LOG 0C 06 0E 08 01` (hex → A1Z26, 32 без Ё, выглядит как лог камеры) | **ЛИНЗА** |
| 3 | N4_qr | Фальшивый QR (CAM3TRAP, ловушка) на ≈57% + настоящий зеркальный QR в конце: отразить кадр и сканировать → deep-link | код **CAM3EYE** (qr: true) |

Фрагмент: **НАБЛЮДАЙ** (как раньше).

Мета узла: label «НАБЛЮДЕНИЕ», hint «уличная камера · архив онлайн · скан с экрана».

## Разделение труда: AI vs пост-обработка

AI-видео **не** рисует текст — поэтому:

- AI генерирует только «улицу» (прогулка/статичный ракурс камеры);
- весь текст (таймкод, REC, hex-вспышка, QR) накладывается программно
  в пост-обработке — `bot/tools/make_n4_video.py` (напишу).

## Источники видео (сток, лицензии свободные)

Скачивать вручную (CDN стоков недоступны из песочницы). Положить в
`bot/quest/source/` как `n4_clip_a.mp4` (улица) — дальше вся сборка моя.

Приоритет — статичный ракурс «камеры наблюдения» (не нужна стабилизация,
QR-плакат ложится на фиксированную область кадра):

1. **Mixkit 4451 «Quiet Tokyo street at night»** — статика, ночь, улица
   с фасадами (стена под QR есть).
   https://mixkit.co/free-stock-video/quiet-tokyo-street-at-night-4451/
   mp4: https://assets.mixkit.co/videos/preview/mixkit-quiet-tokyo-street-at-night-4451-large.mp4
2. **Mixkit 4331 «Traffic on a rainy night»** — статика, ночь, мокрый асфальт.
   https://mixkit.co/free-stock-video/traffic-on-a-rainy-night-4331/
   mp4: https://assets.mixkit.co/videos/preview/mixkit-traffic-on-a-rainy-night-4331-large.mp4
3. **Pexels 5108891 «View of City Traffic at Night»** — Лондон, 30 c, CC0,
   витрины и тротуар.
   https://www.pexels.com/video/view-of-city-traffic-at-night-5108891/
   mp4: https://www.pexels.com/download/video/5108891/
4. **Mixkit 4332 «Times Square rainy night»** — запасной, но в кадре
   много текста (шум для загадки).
   https://mixkit.co/free-stock-video/times-square-during-a-rainy-night-4332/

## ТЗ на AI-клип (для генерации)

- 16:9, 1080p, 25–30 fps, 20–40 сек, цвет — вечерний/ночной город.
- Стиль: камера наблюдения (лёгкий глитч допустим) ИЛИ медленное POV-движение.
- **Без текста в кадре** (вывески нечитаемы — не важно, букв больше нет).
- Обязательно: в конце 4–5 сек почти статичный участок **пустой стены/столба** —
  туда в посте ляжет QR-плакат.
- Людей крупным планом — избегать.

### Промт для нейросети

Если генератор делает короткие клипы (5–10 с) — сгенерируй два и пришли оба:
клип A (улица) и клип B (стена). Я склею.

**Основной промт (EN, клип A — прогулка):**

> Nighttime quiet city street, first-person view walking slowly forward at
> a calm steady pace, wet asphalt reflecting neon shop lights, parked cars,
> distant silhouettes of people far away, cinematic realistic footage,
> slight camera noise and grain, moody urban atmosphere, empty street ahead,
> no text, no captions, no watermarks, no logos. Aspect 16:9, 24fps.

**Клип B — финальная стена (критично для QR):**

> Static security camera shot of an empty brick wall at night, fixed camera
> with no movement, single dim streetlight illuminating a large blank wall
> surface in the center of the frame, slight film grain, realistic CCTV
> footage, desaturated colors, no people, no text, no captions, no watermarks.
> Aspect 16:9, 24fps.

**Вариант одним клипом (если генератор тянет 20+ с):**

> Realistic CCTV security camera footage, night city street, slow smooth
> forward dolly along an empty sidewalk, wet asphalt reflections, dim
> streetlights, the camera gradually approaches and then holds steady on a
> large empty blank wall for the last several seconds, fixed static frame at
> the end, cinematic grain, no people in focus, no text, no captions,
> no watermarks. Aspect 16:9.

**Негатив-промт (если поддерживается):**

> text, captions, subtitles, watermark, logo, letters, signs with readable
> writing, crowds, close-up faces, fast camera motion, shaky footage,
> daylight, cartoon, anime

### Настройки
- Разрешение: максимально доступное (≥1080p), 16:9.
- Движение камеры: минимальное; в клипе B — строго нулевое.
- Если есть seed — зафиксируй и запиши, чтобы можно было перегенерить похоже.


## Пост-обработка (мой инструмент)

1. Оверлей: `REC ● CAM-3` + бегущий таймкод.
2. ~60% ролика: 10–12 кадров тёмного глитча с hex ШУМ (`d0a8 d0a3 d09c`).
3. Финальная статичная секция: на стену накладывается плакат с QR
   (`t.me/<BOT>?start=CAM3EYE`), фикс 2.5–3 c.
4. Экспорт mp4 (yuv420p).

## Текст описания YouTube (загадка 2)

```
CAM-3 · ARGVS-1001 · ARCHIVE 2026
00:00 ПАТРУЛЬ
00:xx ПОТЕРЯ СИГНАЛА
LOG 12 06 14 08 01
```

Пояснение ведущему: 12=Л 06=Е 14=Н 08=З 01=А → ЛИНЗА.
Комментарий от аккаунта ARGVS-1001 (опционально): «ГЛАЗ ВСЁ ВИДЕЛ. ГЛАЗ ВСЁ ЗАПОМНИЛ».

## Открытые вопросы

- YouTube-ссылку и время вспышки подставим после генерации клипа.
- Запасной ход: если AI не осилит — те же точки дорабатываются подсъёмом
  (структура узла не меняется, меняется только исходник видео).
