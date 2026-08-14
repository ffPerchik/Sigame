"""Telegram-бот квеста: трекинг прогресса игроков.

Игроки: /start <код> — старт, далее шлют ответы/фото. Где stage.mode=auto — бот
проверяет сам; где approve — сабмит уходит ведущему на апрув (кнопки/команды).
QR на локациях = deep link t.me/bot?start=CODE (или ввод кода вручную).
Ведущий (HOST_ID): /stats /pending /setstage /broadcast /reset + кнопки на сабмитах.
"""
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.types import (
    CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import config as cfg
import db
import quest

BASE = Path(__file__).resolve().parent

if cfg.PROXY:
    _session = AiohttpSession(proxy=cfg.PROXY)
    bot = Bot(token=cfg.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML),
              session=_session)
    print(f"Подключение через прокси: {cfg.PROXY.split('@')[-1]}")
else:
    bot = Bot(token=cfg.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class HostFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user and message.from_user.id == cfg.HOST_ID


PLAYER_HELP = (
    "Я — бот квеста. Каждый сам за себя.\n"
    "• Шли ответы текстом (на стадиях с шифрами).\n"
    "• На стадиях «докажи» — пришли фото/файл, ждём ведущего.\n"
    "• QR на локации можно отсканировать (откроется ссылка на меня) или ввести код текстом.\n"
    "Команды: /progress — где я, /hint — подсказка (влияет на счёт), /help."
)
ADMIN_HELP = (
    "Команды ведущего:\n"
    "/stats — прогресс всех игроков (+ id и баланс подсказок)\n"
    "/pending — очередь на апрув\n"
    "/addhint <@username или id> <n> — начислить/списать подсказки (n м.б. отрицательным)\n"
    "/sethint <@username или id> <n> — установить точный баланс подсказок\n"
    "/setstage <id> <stage_id> — перевести игрока вручную\n"
    "/broadcast <текст> — сообщение всем\n"
    "/reset <id> — сбросить игрока в начало\n"
    "На сабмитах есть кнопки ✅/❌ (можно и /approve, /reject)."
)


def _resolve(arg: str):
    """@username или числовой id -> user_id (или None)."""
    arg = (arg or "").strip().lstrip("@")
    if arg.isdigit():
        uid = int(arg)
        return uid if db.get_player(uid) else None
    return db.find_by_username(arg)


# ----------------- вспомогательные -----------------

async def notify_host(text: str) -> None:
    try:
        await bot.send_message(cfg.HOST_ID, text)
    except Exception:
        pass


async def send_stage(uid: int, stage_id: str) -> None:
    st = quest.get_stage(stage_id)
    if not st:
        await bot.send_message(uid, f"(стадия «{stage_id}» не найдена — скажи ведущему)")
        return
    text = (st.get("text") or "").strip()
    img = st.get("image")
    if img:
        path = Path(img) if Path(img).is_absolute() else BASE / img
        try:
            await bot.send_photo(uid, FSInputFile(path), caption=text)
            return
        except Exception:
            pass
    await bot.send_message(uid, text)


async def advance(uid: int) -> None:
    player = db.get_player(uid)
    if not player:
        return
    cur = player["stage"]
    st = quest.get_stage(cur)
    if not st:
        return
    nxt = st.get("next")
    if not nxt:
        return
    db.set_stage(uid, nxt)
    db.log_event(uid, "advance", f"{cur} -> {nxt}")
    name = player["name"] or player["username"] or str(uid)
    if cfg.NOTIFY_HOST:
        await notify_host(f"➡️ {name}: «{cur}» → «{nxt}»")
    await send_stage(uid, nxt)
    nst = quest.get_stage(nxt)
    if nst and nst.get("mode") == "info":
        await advance(uid)  # информационная стадия — авто-переход дальше
    if quest.is_finish(nxt):
        db.mark_finished(uid)
        p2 = db.get_player(uid)
        b = (p2["banked"] or 0) if p2 else 0
        await bot.send_message(
            uid, f"📊 Ты накопил {b} подсказок для грядущей Игры. "
                 f"Чем больше — тем больше преимущество в «Своей игре»."
        )
        if cfg.NOTIFY_HOST:
            await notify_host(f"🏆 {name} ЗАВЕРШИЛ квест! Накоплено подсказок: {b}")


def _name(p) -> str:
    return f"{p['name']} (@{p['username'] or '—'})"


# ----------------- игрок: /start -----------------

@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandStart) -> None:
    uid = message.from_user.id
    payload = (command.args or "").strip()
    player = db.get_player(uid)

    if payload and payload == quest.entry_code():
        if player is None:
            first = quest.first_stage()
            db.register(uid, message.from_user.username or "", message.from_user.full_name, first)
            db.log_event(uid, "register")
            await message.answer("🔑 Квест начался. Удачи — каждый сам за себя.")
            await send_stage(uid, first)
            if quest.get_stage(first) and quest.get_stage(first).get("mode") == "info":
                await advance(uid)
            await notify_host(
                f"🆕 Новый игрок: {message.from_user.full_name} (@{message.from_user.username or '—'})"
            )
        else:
            await message.answer("Ты уже в квесте. /progress — где ты сейчас.")
        return

    if player is None:
        await message.answer("Нужен код из квеста (из START.txt внутри пакета). Найди его и пришли /start <код>.")
        return

    # payload — QR-код или попытка ответа на текущую стадию
    await _try_answer(uid, message, payload)


# ----------------- игрок: ответ/сабмит -----------------

async def _try_answer(uid: int, message: Message, text: str) -> None:
    player = db.get_player(uid)
    st = quest.get_stage(player["stage"]) if player else None
    if not st or st.get("mode") != "auto":
        return
    if quest.validate(st.get("accept", []), text):
        b = db.add_banked(uid, 1)
        await message.answer(f"✅ Верно! +1 подсказка для Игры (накоплено: {b}).")
        await advance(uid)
    else:
        await message.answer("❌ Неверно. Попробуй ещё. /hint — подсказка.")


async def _submit_for_approval(uid: int, message: Message) -> None:
    player = db.get_player(uid)
    stage_id = player["stage"]
    kind = ("photo" if message.photo else "document" if message.document
            else "voice" if message.voice else "video" if message.video else "text")
    payload = message.text or message.caption or ""
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.voice:
        file_id = message.voice.file_id
    elif message.video:
        file_id = message.video.file_id
    sub_id = db.add_submission(uid, stage_id, kind, payload, file_id)
    db.log_event(uid, "submit", f"sub#{sub_id} ({kind})")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"appr:{uid}:{sub_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej:{uid}:{sub_id}"),
    ]])
    caption = (f"📥 Сабмит: {_name(player)}\n"
               f"Стадия: «{stage_id}»\n"
               f"Текст: {payload or '(нет)'}")
    try:
        if kind in ("photo", "video") and file_id:
            await bot.send_photo(cfg.HOST_ID, file_id, caption=caption, reply_markup=kb) if kind == "photo" \
                else await bot.send_video(cfg.HOST_ID, file_id, caption=caption, reply_markup=kb)
        elif kind in ("document", "voice") and file_id:
            await bot.send_document(cfg.HOST_ID, file_id, caption=caption, reply_markup=kb)
        else:
            await bot.send_message(cfg.HOST_ID, caption, reply_markup=kb)
    except Exception as e:
        await bot.send_message(cfg.HOST_ID, f"📥 Сабмит: {_name(player)} ({stage_id}) — не удалось переслать: {e}")
    await message.answer("📨 Отправлено ведущему на проверку. Жди.")


@dp.message(F.content_type.in_({"text", "photo", "document", "voice", "video"}))
async def on_message(message: Message) -> None:
    uid = message.from_user.id
    if uid == cfg.HOST_ID:
        return
    if message.text and message.text.startswith("/"):
        await message.answer("Неизвестная команда. /help")
        return
    player = db.get_player(uid)
    if player is None:
        await message.answer("Сначала /start <код из квеста>.")
        return
    st = quest.get_stage(player["stage"])
    if not st or st.get("mode") == "finish":
        await message.answer("Ты уже прошёл квест 🏆")
        return
    if st.get("mode") == "auto":
        await _try_answer(uid, message, message.text or message.caption or "")
    elif st.get("mode") == "approve":
        await _submit_for_approval(uid, message)
    else:
        await message.answer("Жди — это информационная стадия или нужна проверка. /hint")


# ----------------- игрок: команды -----------------

@dp.message(Command("progress"))
async def cmd_progress(message: Message) -> None:
    p = db.get_player(message.from_user.id)
    if not p:
        return await message.answer("Ты ещё не в квесте.")
    if p["finished_at"]:
        await message.answer(f"🏁 Ты прошёл квест! Накоплено подсказок для Игры: {p['banked'] or 0}.")
    else:
        await message.answer(f"Ты на стадии: «{p['stage']}». Накоплено подсказок для Игры: {p['banked'] or 0}.")


@dp.message(Command("hint"))
async def cmd_hint(message: Message) -> None:
    uid = message.from_user.id
    p = db.get_player(uid)
    if not p:
        return await message.answer("Сначала /start <код>.")
    st = quest.get_stage(p["stage"])
    hint = st.get("hint") if st else None
    if not hint:
        return await message.answer("На эту стадию подсказки нет.")
    db.inc_hint(uid, p["stage"])
    await message.answer(f"💡 {hint}\n\n(подсказки учитываются в финальном счёте)")
    if cfg.NOTIFY_HOST:
        await notify_host(f"💡 {_name(p)} взял подсказку на «{p['stage']}»")


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.from_user.id == cfg.HOST_ID:
        await message.answer(ADMIN_HELP)
    else:
        await message.answer(PLAYER_HELP)


# ----------------- ведущий: апрув (кнопки) -----------------

@dp.callback_query(F.data.startswith("appr:"))
async def cb_appr(cq: CallbackQuery) -> None:
    if cq.from_user.id != cfg.HOST_ID:
        return await cq.answer("Только ведущий.", show_alert=True)
    _, uid, sub_id = cq.data.split(":")
    uid, sub_id = int(uid), int(sub_id)
    db.set_submission_status(sub_id, "approved")
    db.log_event(uid, "approved", f"sub#{sub_id}")
    b = db.add_banked(uid, 1)
    await cq.answer("Одобрено ✅")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(uid, f"✅ Засчитано! +1 подсказка для Игры (накоплено: {b}).")
    await advance(uid)


@dp.callback_query(F.data.startswith("rej:"))
async def cb_rej(cq: CallbackQuery) -> None:
    if cq.from_user.id != cfg.HOST_ID:
        return await cq.answer("Только ведущий.", show_alert=True)
    _, uid, sub_id = cq.data.split(":")
    db.set_submission_status(int(sub_id), "rejected")
    db.log_event(int(uid), "rejected", f"sub#{sub_id}")
    await cq.answer("Отклонено ❌")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(int(uid), "❌ Не засчитано. Попробуй иначе или пришли другое доказательство.")


# ----------------- ведущий: команды -----------------

@dp.message(HostFilter(), Command("stats"))
async def cmd_stats(message: Message) -> None:
    rows = db.all_players()
    if not rows:
        return await message.answer("Игроков пока нет.")
    lines = ["📊 Прогресс (подсказки для Игры накоплены за пройденные этапы):"]
    for r in rows:
        mark = "🏁" if r["finished_at"] else "🚶"
        lines.append(
            f"{mark} {r['name']} (@{r['username'] or '—'}) [id:{r['user_id']}]: "
            f"«{r['stage'] or '—'}» | подсказок: {r['banked'] or 0}"
        )
    await message.answer("\n".join(lines))


@dp.message(HostFilter(), Command("pending"))
async def cmd_pending(message: Message) -> None:
    rows = db.pending()
    if not rows:
        return await message.answer("Очередь пуста.")
    lines = ["⏳ На проверке:"]
    for r in rows:
        lines.append(f"#{r['id']} {r['name']} (@{r['username'] or '—'}): «{r['stage']}» — {r['payload'] or r['kind']}")
    await message.answer("\n".join(lines))


@dp.message(HostFilter(), Command("addhint"))
async def cmd_addhint(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer("/addhint <@username или id> <число>  (число может быть отрицательным — списать)")
    target = _resolve(args[0])
    if not target:
        return await message.answer("Игрок не найден. /stats — список с id.")
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer("Число некорректно.")
    p = db.get_player(target)
    b = db.add_banked(target, n)
    sign = f"{'начислено' if n>=0 else 'списано'} {abs(n)}"
    await message.answer(f"✅ {p['name']}: {sign}. Теперь подсказок: {b}.")
    try:
        await bot.send_message(target, f"📊 Твой баланс подсказок изменился ({sign}). Теперь: {b}.")
    except Exception:
        pass


@dp.message(HostFilter(), Command("sethint"))
async def cmd_sethint(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer("/sethint <@username или id> <число>")
    target = _resolve(args[0])
    if not target:
        return await message.answer("Игрок не найден. /stats — список с id.")
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer("Число некорректно.")
    p = db.get_player(target)
    b = db.set_banked(target, n)
    await message.answer(f"✅ {p['name']}: баланс подсказок установлен = {b}.")
    try:
        await bot.send_message(target, f"📊 Твой баланс подсказок: {b}.")
    except Exception:
        pass


@dp.message(HostFilter(), Command("setstage"))
async def cmd_setstage(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer("/setstage <user_id> <stage_id>")
    uid, stage = int(args[0]), args[1]
    if not quest.get_stage(stage):
        return await message.answer(f"Стадии «{stage}» нет в квесте.")
    db.set_stage(uid, stage)
    await send_stage(uid, stage)
    await message.answer(f"✅ {uid} переведён на «{stage}».")


@dp.message(HostFilter(), Command("broadcast"))
async def cmd_broadcast(message: Message, command: Command) -> None:
    text = command.args
    if not text:
        return await message.answer("/broadcast <текст>")
    n = 0
    for r in db.all_players():
        try:
            await bot.send_message(r["user_id"], text)
            n += 1
        except Exception:
            pass
    await message.answer(f"Разослано {n} игрокам.")


@dp.message(HostFilter(), Command("reset"))
async def cmd_reset(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if not args:
        return await message.answer("/reset <user_id>")
    uid = int(args[0])
    first = quest.first_stage()
    db.set_stage(uid, first)
    await message.answer(f"Сброшен {uid} → «{first}».")


@dp.message(HostFilter(), Command("approve"))
async def cmd_approve(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if not args:
        return await message.answer("/approve <user_id> (одобряет последний pending сабмит игрока)")
    uid = int(args[0])
    for r in db.pending():
        if r["user_id"] == uid:
            db.set_submission_status(r["id"], "approved")
            db.log_event(uid, "approved", f"sub#{r['id']}")
            b = db.add_banked(uid, 1)
            await bot.send_message(uid, f"✅ Засчитано! +1 подсказка для Игры (накоплено: {b}).")
            await advance(uid)
            return await message.answer("Одобрено.")
    await message.answer("У этого игрока нет pending-сабмитов.")


@dp.message(HostFilter(), Command("reject"))
async def cmd_reject_cmd(message: Message, command: Command) -> None:
    args = (command.args or "").split(maxsplit=1)
    if not args:
        return await message.answer("/reject <user_id> [причина]")
    uid = int(args[0])
    reason = args[1] if len(args) > 1 else "не засчитано"
    for r in db.pending():
        if r["user_id"] == uid:
            db.set_submission_status(r["id"], "rejected")
            await bot.send_message(uid, f"❌ {reason}")
            return await message.answer("Отклонено.")
    await message.answer("Нет pending-сабмита.")


# ----------------- main -----------------

async def main() -> None:
    db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"Бот @{me.username} запущен. HOST_ID={cfg.HOST_ID}. Жду игроков.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
