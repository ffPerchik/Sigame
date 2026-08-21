"""Telegram-бот квеста ARGVS-1001: хаб-модель, 6 независимых узлов.

Хаб с кнопками: игрок выбирает узел -> проходит целиком -> возвращается в хаб.
После пролога ARGVS требует ключ активации, найденный внутри пакета SIGame.
"""
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.types import (
    CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

try:  # `python -m bot.bot`
    from . import config as cfg
    from . import db, quest
    from . import texts as T
    from .argus import send_lines as send_argus_lines
except ImportError:  # `python bot/bot.py` или запуск из папки bot
    import config as cfg
    import db
    import quest
    import texts as T
    from argus import send_lines as send_argus_lines

BASE = Path(__file__).resolve().parent
INTRO_STAGE = quest.first_stage()

if cfg.PROXY:
    _session = AiohttpSession(proxy=cfg.PROXY)
    bot = Bot(token=cfg.BOT_TOKEN, default=DefaultBotProperties(parse_mode=None),
              session=_session)
    print(T.PROXY_NOTE.format(proxy=cfg.PROXY.split("@")[-1]))
else:
    bot = Bot(token=cfg.BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
dp = Dispatcher()


class HostFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user and message.from_user.id == cfg.HOST_ID


# ---- helpers ----------------------------------------------------------------

def _host_print(text: str) -> None:
    print(f"[HOST] {text}", flush=True)


async def notify_host(text: str) -> None:
    if cfg.HOST_CONSOLE:
        _host_print(text)
        return
    try:
        await bot.send_message(cfg.HOST_ID, text)
    except Exception:
        pass


async def send_host(text: str, **kwargs) -> None:
    """Сообщение ведущему (кнопки апрува и т.п.). В HOST_CONSOLE — только stdout."""
    if cfg.HOST_CONSOLE:
        _host_print(text)
        return
    try:
        await bot.send_message(cfg.HOST_ID, text, **kwargs)
    except Exception as e:
        _host_print(f"не удалось написать ведущему: {e}")


def _resolve(arg: str):
    arg = (arg or "").strip().lstrip("@")
    if arg.isdigit():
        uid = int(arg)
        return uid if db.get_player(uid) else None
    return db.find_by_username(arg)


def _name(p) -> str:
    return f"{p['name']} (@{p['username'] or '—'})"


# ======================== send_stage ========================================

async def send_stage(uid: int, stage_id: str) -> None:
    """Отправляет игроку содержимое стадии (текст + медиа).
    Хаб обрабатывается отдельно — _send_hub()."""
    if stage_id == "hub":
        await _send_hub(uid)
        return
    st = quest.get_stage(stage_id)
    if not st:
        await bot.send_message(uid, T.STAGE_MISSING.format(stage=stage_id))
        return
    before_text = (st.get("before_text") or "").strip()
    if before_text:
        await bot.send_message(uid, before_text)

    argus_lines = st.get("argus") or []
    if isinstance(argus_lines, str):
        argus_lines = [argus_lines]
    if argus_lines:
        await send_argus_lines(
            argus_lines,
            lambda line: bot.send_message(uid, line),
            delay=st.get("argus_delay", 0.5),
        )

    text = (st.get("text") or "").strip()
    media_dir = BASE / "quest" / "images"
    for field, sender, kind_label in (
        ("image",    bot.send_photo,    "photo"),
        ("audio",    bot.send_audio,    "audio"),
        ("video",    bot.send_video,    "video"),
        ("document", bot.send_document, "document"),
    ):
        fn = st.get(field)
        if not fn:
            continue
        path = Path(fn) if Path(fn).is_absolute() else media_dir / fn
        try:
            await sender(uid, FSInputFile(path), caption=text)
            return
        except Exception as e:
            print(T.MEDIA_FAIL.format(kind=kind_label, path=path, err=e))
    if text:
        await bot.send_message(uid, text)


# ======================== HUB ===============================================

async def _send_hub(uid: int) -> None:
    """Динамически строит хаб с кнопками выбора узла."""
    status = db.nodes_status(uid)
    done_count = sum(1 for v in status.values() if v == "done")

    if done_count == 6:
        db.set_stage(uid, "final_hint")
        await bot.send_message(uid, T.HUB_DONE_NOTICE)
        await send_stage(uid, "final_hint")
        return

    nodes = quest.nodes_meta()
    lines = [T.HUB_HEADER, ""]
    for nid, meta in nodes.items():
        n = nid[1:]
        tmpl = T.HUB_LINE_DONE if status[nid] == "done" else T.HUB_LINE_TODO
        lines.append(tmpl.format(n=n, label=meta.get("label", ""), hint=meta.get("hint", "")))
    lines.append("")
    lines.append(T.HUB_FOOTER.format(done=done_count))
    text = "\n".join(lines)

    # Кнопки: только непройденные узлы
    buttons = []
    for nid in nodes:
        if status[nid] != "done":
            buttons.append(InlineKeyboardButton(text=nid, callback_data=f"node:{nid}"))
    kb_lines = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_lines)

    await bot.send_message(uid, text, reply_markup=kb)


# ======================== advance ===========================================

async def advance(uid: int) -> None:
    """Авто-прогон по цепочке next: до первой не-info стадии.
    Хаб — терминал. Фрагмент -> хаб отмечает узел пройденным."""
    player = db.get_player(uid)
    if not player:
        return
    cur = player["stage"]
    if cur == "hub":
        return

    st = quest.get_stage(cur)
    if not st:
        return
    nxt = st.get("next")
    if not nxt:
        return

    # Уходим с Nx_fragment -> отмечаем узел пройденным
    node_id = quest.extract_node_id(cur)
    if cur.endswith("_fragment") and node_id:
        db.mark_node_done(uid, node_id)

    db.set_stage(uid, nxt)
    db.log_event(uid, "advance", f"{cur} -> {nxt}")
    name = player["name"] or player["username"] or str(uid)
    if cfg.NOTIFY_HOST:
        await notify_host(T.ADVANCE_HOST.format(name=name, cur=cur, nxt=nxt))
    await send_stage(uid, nxt)

    if nxt == "hub":
        return

    nst = quest.get_stage(nxt)
    if nst and nst.get("mode") == "info":
        await advance(uid)

    if quest.is_finish(nxt):
        db.mark_finished(uid)
        p2 = db.get_player(uid)
        b = (p2["banked"] or 0) if p2 else 0
        await bot.send_message(uid, T.FINISH_PLAYER.format(bal=b))
        if cfg.NOTIFY_HOST:
            await notify_host(T.FINISH_HOST.format(name=name, bal=b))


# ======================== answers & submissions =============================

async def _try_answer(uid: int, message: Message, text: str) -> None:
    player = db.get_player(uid)
    st = quest.get_stage(player["stage"]) if player else None
    if not st or st.get("mode") != "auto":
        return
    accepted = [quest.entry_code()] if st.get("accept_entry_code") else st.get("accept", [])
    if quest.validate(accepted, text):
        correct_text = st.get("correct_text", T.CORRECT)
        if correct_text:
            await message.answer(correct_text)
        await advance(uid)
    else:
        wrong_argus = st.get("wrong_argus")
        if wrong_argus:
            await send_argus_lines(
                [wrong_argus],
                lambda line: message.answer(line),
                delay=0,
            )
        else:
            await message.answer(st.get("wrong_text", T.WRONG))


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
    caption = T.SUBMIT_RELAY.format(name=_name(player), stage=stage_id,
                                    payload=payload or "(нет)")
    if cfg.HOST_CONSOLE:
        _host_print(caption)
        _host_print(f"HOST_CONSOLE=1 → авто-одобрение sub#{sub_id}")
        db.set_submission_status(sub_id, "approved")
        db.log_event(uid, "approved", f"sub#{sub_id} (console)")
        await message.answer(T.APPROVED_TO_PLAYER)
        await advance(uid)
        return
    try:
        if kind in ("photo", "video") and file_id:
            if kind == "photo":
                await bot.send_photo(cfg.HOST_ID, file_id, caption=caption,
                                     reply_markup=kb)
            else:
                await bot.send_video(cfg.HOST_ID, file_id, caption=caption,
                                     reply_markup=kb)
        elif kind in ("document", "voice") and file_id:
            await bot.send_document(cfg.HOST_ID, file_id, caption=caption,
                                    reply_markup=kb)
        else:
            await send_host(caption, reply_markup=kb)
    except Exception as e:
        await send_host(T.SUBMIT_RELAY_FAIL.format(
            name=_name(player), stage=stage_id, err=e))
    await message.answer(T.SUBMIT_SENT)


# ======================== /start ============================================

@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandStart) -> None:
    uid = message.from_user.id
    player = db.get_player(uid)
    if player is not None:
        await message.answer(T.ALREADY_IN_QUEST)
        return

    # Ключ из SIGame не тратится на вход: он понадобится Аргусу после пролога.
    db.register(uid, message.from_user.username or "",
                message.from_user.full_name, INTRO_STAGE)
    db.log_event(uid, "register")

    welcome = quest.welcome_info()
    welcome_text = welcome.get("text", T.WELCOME)
    welcome_image = welcome.get("image")
    if welcome_image:
        path = (Path(welcome_image) if Path(welcome_image).is_absolute()
                else BASE / "quest" / "images" / welcome_image)
        try:
            await bot.send_photo(uid, FSInputFile(path), caption=welcome_text)
        except Exception:
            await bot.send_message(uid, welcome_text)
    else:
        await bot.send_message(uid, welcome_text)

    name = message.from_user.full_name
    username = message.from_user.username or "—"
    await notify_host(T.NEW_PLAYER_INTRO.format(name=name, username=username))
    await send_stage(uid, INTRO_STAGE)


# ======================== node pick (hub buttons) ===========================

@dp.callback_query(F.data.startswith("node:"))
async def cb_node_pick(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    node_id = cq.data.split(":", 1)[1]

    if db.is_node_done(uid, node_id):
        await cq.answer(T.NODE_ALREADY_DONE, show_alert=True)
        return

    intro_stage = f"{node_id}_intro"
    if not quest.get_stage(intro_stage):
        await cq.answer(T.NODE_NOT_FOUND, show_alert=True)
        return

    db.set_stage(uid, intro_stage)
    db.log_event(uid, "node_pick", node_id)
    await cq.answer(T.NODE_PICK_OK.format(node=node_id))

    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await send_stage(uid, intro_stage)
    await advance(uid)


# ======================== player commands ===================================

@dp.message(Command("progress"))
async def cmd_progress(message: Message) -> None:
    uid = message.from_user.id
    p = db.get_player(uid)
    if not p:
        return await message.answer(T.NOT_IN_QUEST)
    bal = p["banked"] or 0
    if p["finished_at"]:
        return await message.answer(T.PROGRESS_FINISHED.format(bal=bal))
    await message.answer(T.PROGRESS_STAGE_HEADER.format(stage=p["stage"], bal=bal))
    await send_stage(uid, p["stage"])


@dp.message(Command("hint"))
async def cmd_hint(message: Message) -> None:
    uid = message.from_user.id
    p = db.get_player(uid)
    if not p:
        return await message.answer(T.HINT_NEED_START)
    if p["stage"] == "hub":
        return await message.answer(T.NO_HINT_HERE)
    st = quest.get_stage(p["stage"])
    hint = st.get("hint") if st else None
    if not hint:
        return await message.answer(T.NO_HINT_HERE)
    bal = p["banked"] or 0
    if bal <= 0:
        return await message.answer(T.NO_HINTS_LEFT)
    db.add_banked(uid, -1)
    bal -= 1
    await message.answer(T.HINT_USED.format(hint=hint, remaining=bal))
    if cfg.NOTIFY_HOST:
        await notify_host(T.HINT_HOST.format(name=_name(p), stage=p["stage"], remaining=bal))


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        T.ADMIN_HELP if message.from_user.id == cfg.HOST_ID else T.PLAYER_HELP)


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    uid = message.from_user.id
    verdict = T.ID_VERDICT_HOST if uid == cfg.HOST_ID else T.ID_VERDICT_NOT_HOST
    await message.answer(T.ID_TEMPLATE.format(uid=uid, host=cfg.HOST_ID, verdict=verdict))


@dp.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer(T.PONG)


@dp.message(Command("hub"))
async def cmd_hub(message: Message) -> None:
    uid = message.from_user.id
    p = db.get_player(uid)
    if not p:
        return await message.answer(T.NOT_IN_QUEST)
    if p["stage"] == "hub":
        await _send_hub(uid)
    else:
        await message.answer(T.NO_HUB_MID_NODE)


# ======================== approve / reject (submissions) ====================

@dp.callback_query(F.data.startswith("appr:"))
async def cb_appr(cq: CallbackQuery) -> None:
    if cq.from_user.id != cfg.HOST_ID:
        return await cq.answer(T.ONLY_HOST, show_alert=True)
    _, uid, sub_id = cq.data.split(":")
    uid, sub_id = int(uid), int(sub_id)
    db.set_submission_status(sub_id, "approved")
    db.log_event(uid, "approved", f"sub#{sub_id}")
    await cq.answer(T.APPROVED_ALERT)
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(uid, T.APPROVED_TO_PLAYER)
    await advance(uid)


@dp.callback_query(F.data.startswith("rej:"))
async def cb_rej(cq: CallbackQuery) -> None:
    if cq.from_user.id != cfg.HOST_ID:
        return await cq.answer(T.ONLY_HOST, show_alert=True)
    _, uid, sub_id = cq.data.split(":")
    db.set_submission_status(int(sub_id), "rejected")
    db.log_event(int(uid), "rejected", f"sub#{sub_id}")
    await cq.answer(T.REJECTED_ALERT)
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(int(uid), T.REJECTED_TO_PLAYER)


# ======================== host commands =====================================

@dp.message(HostFilter(), Command("stats"))
async def cmd_stats(message: Message) -> None:
    rows = db.all_players()
    if not rows:
        return await message.answer(T.STATS_EMPTY)
    lines = [T.STATS_HEADER]
    for r in rows:
        mark = "🏁" if r["finished_at"] else "🚶"
        ns = db.nodes_status(r["user_id"])
        nodes_str = " ".join(
            f"{nid[1:]}✓" if st == "done" else f"{nid[1:]}✗"
            for nid, st in ns.items()
        )
        lines.append(T.STATS_LINE.format(
            mark=mark, name=r["name"], username=r["username"] or "—",
            uid=r["user_id"], stage=r["stage"] or "—",
            nodes=nodes_str, bal=r["banked"] or 0))
    await message.answer("\n".join(lines))


@dp.message(HostFilter(), Command("pending"))
async def cmd_pending(message: Message) -> None:
    rows = db.pending()
    if not rows:
        return await message.answer(T.PENDING_EMPTY)
    lines = [T.PENDING_HEADER]
    for r in rows:
        lines.append(T.PENDING_LINE.format(
            sid=r["id"], name=r["name"], username=r["username"] or "—",
            stage=r["stage"], payload=r["payload"] or r["kind"]))
    await message.answer("\n".join(lines))


@dp.message(HostFilter(), Command("addhint"))
async def cmd_addhint(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer(T.ADDHINT_USAGE)
    target = _resolve(args[0])
    if not target:
        return await message.answer(T.PLAYER_NOT_FOUND)
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer(T.BAD_NUMBER)
    p = db.get_player(target)
    b = db.add_banked(target, n)
    sign = (T.SIGN_CREDIT if n >= 0 else T.SIGN_DEBIT).format(n=abs(n))
    await message.answer(T.ADDHINT_RESULT.format(name=p["name"], sign=sign, bal=b))
    try:
        await bot.send_message(target, T.BANK_CHANGED.format(sign=sign, bal=b))
    except Exception:
        pass


@dp.message(HostFilter(), Command("sethint"))
async def cmd_sethint(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer(T.SETHINT_USAGE)
    target = _resolve(args[0])
    if not target:
        return await message.answer(T.PLAYER_NOT_FOUND)
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer(T.BAD_NUMBER)
    p = db.get_player(target)
    b = db.set_banked(target, n)
    await message.answer(T.SETHINT_RESULT.format(name=p["name"], bal=b))
    try:
        await bot.send_message(target, T.BANK_SET_PLAYER.format(bal=b))
    except Exception:
        pass


@dp.message(HostFilter(), Command("setstage"))
async def cmd_setstage(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if len(args) < 2:
        return await message.answer(T.SETSTAGE_USAGE)
    uid, stage = int(args[0]), args[1]
    if not quest.get_stage(stage):
        return await message.answer(T.STAGE_NOT_FOUND.format(stage=stage))
    db.set_stage(uid, stage)
    await send_stage(uid, stage)
    await advance(uid)
    await message.answer(T.SETSTAGE_RESULT.format(uid=uid, stage=stage))


@dp.message(HostFilter(), Command("broadcast"))
async def cmd_broadcast(message: Message, command: Command) -> None:
    text = command.args
    if not text:
        return await message.answer(T.BROADCAST_USAGE)
    n = 0
    for r in db.all_players():
        try:
            await bot.send_message(r["user_id"], text)
            n += 1
        except Exception:
            pass
    await message.answer(T.BROADCAST_DONE.format(n=n))


@dp.message(HostFilter(), Command("reset"))
async def cmd_reset(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if not args:
        return await message.answer(T.RESET_USAGE)
    uid = int(args[0])
    db.set_stage(uid, INTRO_STAGE)
    await message.answer(T.RESET_DONE.format(uid=uid, stage=INTRO_STAGE))


@dp.message(HostFilter(), Command("approve"))
async def cmd_approve(message: Message, command: Command) -> None:
    args = (command.args or "").split()
    if not args:
        return await message.answer(T.APPROVE_USAGE)
    uid = int(args[0])
    for r in db.pending():
        if r["user_id"] == uid:
            db.set_submission_status(r["id"], "approved")
            db.log_event(uid, "approved", f"sub#{r['id']}")
            await bot.send_message(uid, T.APPROVED_TO_PLAYER)
            await advance(uid)
            return await message.answer(T.APPROVE_OK)
    await message.answer(T.NO_PENDING)


@dp.message(HostFilter(), Command("reject"))
async def cmd_reject_cmd(message: Message, command: Command) -> None:
    args = (command.args or "").split(maxsplit=1)
    if not args:
        return await message.answer(T.REJECT_USAGE)
    uid = int(args[0])
    reason = args[1] if len(args) > 1 else T.REJECT_DEFAULT_REASON
    for r in db.pending():
        if r["user_id"] == uid:
            db.set_submission_status(r["id"], "rejected")
            await bot.send_message(uid, T.REJECT_PLAYER.format(reason=reason))
            return await message.answer(T.REJECT_OK)
    await message.answer(T.NO_PENDING_2)


# ======================== universal message handler =========================

@dp.message(F.content_type.in_({"text", "photo", "document", "voice", "video"}))
async def on_message(message: Message) -> None:
    uid = message.from_user.id
    if message.text and message.text.startswith("/"):
        await message.answer(T.UNKNOWN_COMMAND)
        return

    player = db.get_player(uid)
    if player is None:
        await message.answer(T.START_FIRST)
        return

    if player["stage"] == "hub":
        await message.answer(T.IN_HUB_USE_BUTTONS)
        return

    st = quest.get_stage(player["stage"])
    if not st:
        await message.answer(T.STAGE_MISSING.format(stage=player["stage"]))
        return
    if st.get("mode") == "finish":
        await message.answer(T.ALREADY_FINISHED)
        return
    if st.get("mode") == "gate":
        await message.answer(T.IN_GATE)
        return
    if st.get("mode") == "auto":
        await _try_answer(uid, message, message.text or message.caption or "")
    elif st.get("mode") == "approve":
        await _submit_for_approval(uid, message)
    else:
        await message.answer(T.WAIT_INFO)


# ======================== main ==============================================

async def main() -> None:
    db.init_db()
    # Старые тестовые БД могли сохранить гейт до пролога. После переноса гейта
    # возвращаем таких игроков на первую задачу Жени.
    for player in db.all_players():
        if player["stage"] == "start_gate":
            db.set_stage(player["user_id"], INTRO_STAGE)
            db.log_event(player["user_id"], "stage_migrated", "start_gate -> z_1")
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    extra = " HOST_CONSOLE=1 (уведомления ведущего → консоль)" if cfg.HOST_CONSOLE else ""
    print(T.STARTUP.format(username=me.username, host=cfg.HOST_ID) + extra)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
