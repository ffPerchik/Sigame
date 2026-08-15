# bot/texts.py
# ВСЕ тексты бота собраны здесь. Меняй формулировки в этом файле — логику в bot.py трогать не нужно.
# Шаблоны с {фигурными скобками} заполняются кодом через .format(...). Не удаляй сами плейсхолдеры.

# ============ ПОМОЩЬ ============
PLAYER_HELP = (
    "Я — бот квеста. Каждый сам за себя.\n"
    "• Шли ответы текстом (на стадиях с шифрами).\n"
    "• На стадиях «докажи» — пришли фото/файл, ждём ведущего.\n"
    "• QR на локации можно отсканировать (откроется ссылка на меня) или ввести код текстом.\n"
    "Команды: /progress — где я, /hint — подсказка (стоит 1 подсказку), /help."
)
ADMIN_HELP = (
    "Команды ведущего:\n"
    "/stats — прогресс всех игроков (+ id и баланс подсказок)\n"
    "/pending — очередь на апрув\n"
    "/addhint <@username или id> <n> — начислить игроку подсказки (сколько он ЗАРАБОТАЛ в «Своей игре»)\n"
    "/sethint <@username или id> <n> — установить точный баланс подсказок\n"
    "/setstage <id> <stage_id> — перевести игрока вручную\n"
    "/broadcast <текст> — сообщение всем\n"
    "/reset <id> — сбросить игрока в начало\n"
    "На сабмитах есть кнопки ✅/❌ (можно и /approve, /reject)."
)

# ============ СТАРТ / РЕГИСТРАЦИЯ ============
WELCOME = "🔑 Квест начался. Удачи — каждый сам за себя."
ALREADY_IN_QUEST = "Ты уже в квесте. /progress — где ты сейчас."
NEED_CODE = "Нужен код из квеста (из START.txt внутри пакета). Найди его и пришли /start <код>."
NEW_PLAYER = "🆕 Новый игрок: {name} (@{username})"

# ============ ОТВЕТЫ ИГРОКА ============
CORRECT = "✅ Верно!"
WRONG = "❌ Неверно. Попробуй ещё. /hint — подсказка (стоит 1 подсказку)."
UNKNOWN_COMMAND = "Неизвестная команда. /help"
START_FIRST = "Сначала /start <код из квеста>."
ALREADY_FINISHED = "Ты уже прошёл квест 🏆"
WAIT_INFO = "Жди — это информационная стадия или нужна проверка. /hint"

# ============ САБМИТ НА АПРУВ ============
SUBMIT_SENT = "📨 Отправлено ведущему на проверку. Жди."
SUBMIT_RELAY = "📥 Сабмит: {name}\nСтадия: «{stage}»\nТекст: {payload}"
SUBMIT_RELAY_FAIL = "📥 Сабмит: {name} ({stage}) — не удалось переслать: {err}"

# ============ ПРОГРЕСС / ПОДСКАЗКИ (КВЕСТ) ============
NOT_IN_QUEST = "Ты ещё не в квесте."
PROGRESS_STAGE = "Ты на стадии: «{stage}». Осталось подсказок: {bal}."
PROGRESS_FINISHED = "🏁 Ты прошёл квест! Осталось подсказок: {bal}."
HINT_NEED_START = "Сначала /start <код>."
NO_HINT_HERE = "На эту стадию подсказки нет."
NO_HINTS_LEFT = "У тебя нет подсказок. Подсказки зарабатывают в «Своей игре», а здесь — тратят."
HINT_USED = "💡 {hint}\n\n(Потрачена 1 подсказка. Осталось: {remaining}.)"

# ============ ДИАГНОСТИКА ============
PONG = "🏓 pong — бот жив и отвечает"
ID_VERDICT_HOST = "✅ совпадает — ты ведущий, админ-команды работают"
ID_VERDICT_NOT_HOST = "❌ НЕ совпадает с HOST_ID — админ-команды (/stats и т.д.) молчат. Впиши свой реальный id в .env как HOST_ID и перезапусти бота."
ID_TEMPLATE = "Твой Telegram ID: {uid}\nHOST_ID в .env: {host}\n{verdict}"

# ============ АПРУВ (КНОПКИ / ВЕДУЩИЙ) ============
ONLY_HOST = "Только ведущий."
APPROVED_ALERT = "Одобрено ✅"
APPROVED_TO_PLAYER = "✅ Засчитано! Двигаемся дальше."
REJECTED_ALERT = "Отклонено ❌"
REJECTED_TO_PLAYER = "❌ Не засчитано. Попробуй иначе или пришли другое доказательство."

# ============ УВЕДОМЛЕНИЯ ВЕДУЩЕМУ + ФИНИШ ============
ADVANCE_HOST = "➡️ {name}: «{cur}» → «{nxt}»"
FINISH_HOST = "🏆 {name} ЗАВЕРШИЛ квест! Осталось подсказок: {bal}"
FINISH_PLAYER = "📊 Квест пройден! У тебя осталось {bal} подсказок."
HINT_HOST = "💡 {name} потратил подсказку на «{stage}» (осталось {remaining})"
STAGE_MISSING = "(стадия «{stage}» не найдена — скажи ведущему)"

# ============ ВЕДУЩИЙ: СПИСКИ ============
STATS_EMPTY = "Игроков пока нет."
STATS_HEADER = "📊 Прогресс (подсказки заработаны в «Своей игре», тратятся в квесте):"
STATS_LINE = "{mark} {name} (@{username}) [id:{uid}]: «{stage}» | подсказок: {bal}"
PENDING_EMPTY = "Очередь пуста."
PENDING_HEADER = "⏳ На проверке:"
PENDING_LINE = "#{sid} {name} (@{username}): «{stage}» — {payload}"

# ============ ВЕДУЩИЙ: КОМАНДЫ (usage + ответы) ============
ADDHINT_USAGE = "/addhint <@username или id> <число>  (отрицательное — списать)"
SETHINT_USAGE = "/sethint <@username или id> <число>"
SIGN_CREDIT = "начислено {n}"
SIGN_DEBIT = "списано {n}"
PLAYER_NOT_FOUND = "Игрок не найден. /stats — список с id."
BAD_NUMBER = "Число некорректно."
ADDHINT_RESULT = "✅ {name}: {sign}. Теперь подсказок: {bal}."
BANK_CHANGED = "📊 Твой баланс подсказок изменился ({sign}). Теперь: {bal}."
SETHINT_RESULT = "✅ {name}: баланс подсказок установлен = {bal}."
BANK_SET_PLAYER = "📊 Твой баланс подсказок: {bal}."

SETSTAGE_USAGE = "/setstage <id> <stage_id>"
STAGE_NOT_FOUND = "Стадии «{stage}» нет в квесте."
SETSTAGE_RESULT = "✅ {uid} переведён на «{stage}»."

BROADCAST_USAGE = "/broadcast <текст>"
BROADCAST_DONE = "Разослано {n} игрокам."

RESET_USAGE = "/reset <id>"
RESET_DONE = "Сброшен {uid} → «{stage}»."

APPROVE_USAGE = "/approve <id> (одобряет последний pending сабмит игрока)"
APPROVE_OK = "Одобрено."
NO_PENDING = "У этого игрока нет pending-сабмитов."

REJECT_USAGE = "/reject <id> [причина]"
REJECT_DEFAULT_REASON = "не засчитано"
REJECT_PLAYER = "❌ {reason}"
REJECT_OK = "Отклонено."
NO_PENDING_2 = "Нет pending-сабмита."

# ============ КОНСОЛЬ (не игрокам) ============
STARTUP = "Бот @{username} запущен. HOST_ID={host}. Жду игроков."
PROXY_NOTE = "Подключение через прокси: {proxy}"
