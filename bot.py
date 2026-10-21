# -*- coding: utf-8 -*-
"""
Квест «Архив Ночных Дел» — мистический Хэллоуин-квест для Telegram-бота
проекта «Другое Дело» (категории: обучение, экология, волонтёрство,
культура и искусство, здоровье и спорт).

Запуск: python3 bot.py
Токен берётся из переменной окружения BOT_TOKEN, а если её нет —
из файла token.txt.
"""

import asyncio, aiosqlite, re, time, csv, random, os

from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (Message, FSInputFile,
                           InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery)

TOKEN = os.environ.get("BOT_TOKEN") or (
    open("token.txt").read().strip() if os.path.exists("token.txt") else "")
if not TOKEN:
    raise SystemExit("Токен не найден: задай переменную окружения BOT_TOKEN "
                     "или создай файл token.txt с токеном от @BotFather")

DB = "quest.db"
ADMIN_IDS = {1467490182}  # ← впиши свой Telegram user_id (узнать: @userinfobot)

PAUSE = 1.5   # пауза между «наградой» и переходом к новому делу, секунды
STAGE_GAP = 5 # пауза между лором (с картинкой) и заданием, секунды

# Ссылка на одностраничный сайт с тайным заданием (дело №3).
# После включения GitHub Pages сверь адрес с реальным.
SITE_URL = "https://teresa2003love555.github.io/night-archive-bot/"

bot = Bot(TOKEN)
dp = Dispatcher()

# ============================================================
#  ЛОР: тексты Хранителя Архива
# ============================================================

LORE_INTRO = (
    "🕯 <b>Архив Ночных Дел</b>\n\n"
    "Доброй ночи. Или утра. В Архиве это неважно.\n\n"
    "Долгие годы здесь хранились дела, которые люди так и не завершили:\n"
    "недописанные конспекты, недосортированный мусор, недосказанные\n"
    "тёплые слова, недорисованные наброски и так ни разу и не сделанные\n"
    "приседания. Каждое незакрытое дело рождает <b>Тень</b> — и Тени\n"
    "просыпаются к Хэллоуину.\n\n"
    "Последняя Хранительница Архива — <b>Мия</b>. Она приходит сюда в\n"
    "кремовом свитере, со свечой в руке: зажигает лампу под потолком,\n"
    "поправляет стеллажи и следит, чтобы Тени не разбрелись по живым.\n\n"
    "Сегодня Мия передаёт лампу тебе: в эту ночь ты станешь Ночным\n"
    "Секретарём. Пять дел, пять кодовых слов, пять огоньков. Собери их —\n"
    "и зажги лампу, чтобы закрыть Архив навсегда.\n\n"
    "«Дело, доведённое до конца, не боится темноты»."
)

LORE_REG = (
    "Прежде чем впустить тебя, Хранитель обязан занести тебя в книгу.\n\n"
    "📜 <b>Страница реестра</b>\n"
    "Имя — под ним Тени будут звать тебя.\n"
    "Фамилия — чтобы отличать от других Секретарей (отчество Архиву не нужен).\n"
    "Отметка ВКонтакте — чтобы Архив знал, где ты живёшь среди живых.\n"
    "Почта — туда «Другое Дело» начислит баллы за закрытые дела."
)

LORE_FINAL = (
    "🔦 <b>ЛАМПА ЗАЖГЛАСЬ</b>\n\n"
    "Пять огоньков слились в один ровный свет. Мия поднимает лампу —\n"
    "и Тени поклонились и растаяли, как чернила, наконец высохшие\n"
    "на бумаге.\n\n"
    "Архив закрыт. Ни одного незавершённого дела не осталось в этих\n"
    "стенах. А это значит — у каждой Тени теперь есть шанс стать\n"
    "не тенью, а делом.\n\n"
    "Доброй ночи, {nick}. Или доброго утра.\n"
    "Теперь это уже неважно."
)

LORE_PLEDGE = (
    "Один Секретарь ушёл, не закончив дело, — и теперь он бродит\n"
    "по снам участников квеста, шепчет: «доведи до конца…».\n"
    "Не будь как он. Закрой все пять дел."
)

# --- Переходы между делами (отправляются одним сообщением с картинкой) ---

TRANS_1 = (
    "Мия зажигает свечу и ведёт тебя мимо стеллажей, где шепчут конспекты.\n"
    "«Первое дело почти всегда про учёбу, — говорит она. — Брошенный\n"
    "конспект шумит громче всех».\n\n"
    "🕯 <b>Дело №1: «Тень на таблицах»</b>\n"
    "Один студент оставил незакрытый конспект — и теперь цифры шепчут по ночам."
)

TRANS_2 = (
    "Мия гасит свечу и указывает на винтовую лестницу: «Чердак. Там живёт\n"
    "призрак, который давно просился на переработку. Экология — дело второе».\n\n"
    "🕯 <b>Дело №2: «Мусор, который не призрак»</b>\n"
    "На чердаке Архива завёлся призрак. Присмотрись: это не призрак —\n"
    "это пластиковая бутылка 1997 года, которую забыли рассортировать.\n"
    "Разберём чердак!"
)

TRANS_3 = (
    "Мия ведёт тебя по коридору и останавливается у двери без таблички.\n"
    "«Это дело никто так и не завершил. Даже я не знаю всего, что за этой\n"
    "дверью, — говорит она тихо. — Но у него есть тайная часть…»\n\n"
    "🕯 <b>Дело №3: «Тень без имени»</b>\n"
    "У этого дела нет имени — его не завершил никто и никогда.\n"
    "Тени нужен человек, который сделает доброе дело прямо сейчас."
)

TRANS_4 = (
    "Мия проводит тебя в картинную галерею Архива: рамы на стенах —\n"
    "все пустые. «Культура греет лучше свечи, — улыбается она. —\n"
    "Заполни раму — и Тень внутри неё станет делом».\n\n"
    "🕯 <b>Дело №4: «Портрет в скетчбуке»</b>\n"
    "В Архиве висит пустая рама. Тень, которую коснётся картина,\n"
    "перестанет быть тенью."
)

TRANS_5 = (
    "Мия останавливается перед зеркальным залом и впервые за ночь молчит.\n"
    "«Последнее дело — про тебя самого, — наконец говорит она. — Тело,\n"
    "которое не двигается, тоже однажды станет тенью».\n\n"
    "🕯 <b>Дело №5: «Зеркало без отражения»</b>"
)

TRANS_FINAL = (
    "Мия снимает лампу с крюка и держит её над столом: «Пять дел закрыты,\n"
    "Секретарь. Осталось сложить ключи вместе — и Архив закроется навсегда»."
)

# --- Тайное задание (дело №3) ---

SECRET_LORE = (
    "🌙 <b>Тайное задание</b>\n\n"
    "Мия понижает голос, и свеча в её руке дрожит: «Это дело не хранится на\n"
    "полках Архива. Его передают из рук в руки — через страницу в сети,\n"
    "которую я открываю немногим».\n\n"
    "Она проводит пальцем по воздуху — и перед тобой вспыхивает свиток-ссылка.\n"
    "Открой тайное задание, выполни его — а слово, которое спрятано внутри,\n"
    "шепни мне сюда в чат."
)

# ============================================================
#  ЭТАЛОНЫ ОТВЕТОВ
# ============================================================

def norm(s: str) -> str:
    return re.sub(r"[\s\-]+", "", (s or "").lower())

RIDDLES = [
    ("Первый вопрос:\n«У Тени было 13 огоньков. Половину она потратила,\n"
     "ещё 2 отдала Ключнику. Сколько осталось?»",
     {"4", "четыре"}, "Считай: 13 пополам, потом минус 2."),
    ("Второй вопрос:\n«Найди лишнее: конспект, лекция, дедлайн, шпаргалка-призрак».",
     {"дедлайн", "deadline"}, "Три из них — источники знаний. Один — источник паники."),
    ("Третий вопрос:\n«Прочитай слово наоборот: ТЕНЬ».",
     {"ьнет"}, "Слово из четырёх букв. Просто разверни."),
    ("Четвёртый вопрос — шифр:\n«ЬДЙСЕ НЕМЕ» — это анаграмма фразы,\n"
     "которой Хранитель закрывает дела. Расшифруй.",
     {"семьдней", "7дней"}, "Сколько ночей длится Хэллоуинская неделя? ПИШИ С ЗАГЛАВНОЙ БУКВЫ."),
]

SORT_ITEMS = [
    ("батарейка", "Опасное"),
    ("ртутный градусник", "Опасное"),
    ("стеклянная банка", "Переработка"),
    ("алюминиевая банка", "Переработка"),
    ("чистый полиэтиленовый пакет", "Переработка"),
    ("пицц-коробка с жирными пятнами", "Не переработать"),
    ("кассовый чек", "Не переработать"),
]

CODES = ["ЬНЕТ", "СОРТИРОВКА", "ДОБРО", "СВЕТ", "ОТРАЖЕНИЕ"]

# --- Тайное задание дела №3 ---
SECRET_TASK_NAME = "Ночной переписчик"   # название задания на сайте
CIPHER_LINE = "15-16-25-30"              # числа, спрятанные на сайте
L3_SECRET = {"ночь"}                     # разгадка (НОЧЬ: Н=15, О=16, Ч=25, Ь=30)

# ============================================================
#  КАРТИНКИ: шлём, если файл лежит рядом с bot.py
# ============================================================

async def send_img(m: Message, path: str, caption: str = None):
    """Отправляет картинку, если она есть в репозитории. Нет файла — тихо пропускаем."""
    if not os.path.exists(path):
        return False
    try:
        if caption:
            await m.answer_photo(FSInputFile(path), caption=caption, parse_mode="HTML")
        else:
            await m.answer_photo(FSInputFile(path))
        return True
    except Exception:
        return False

async def send_stage(m: Message, img: str, lore: str, task: str = None, kb=None):
    """Лор одним сообщением с картинкой; через 5 секунд — задание."""
    sent = await send_img(m, img, caption=lore)
    if not sent:
        await m.answer(lore, parse_mode="HTML")
    if task:
        await asyncio.sleep(STAGE_GAP)
        await m.answer(task, parse_mode="HTML", reply_markup=kb)

# ============================================================
#  КЛАВИАТУРЫ (кнопки друг под другом)
# ============================================================

def inline_kb(labels, cbs):
    """Каждая кнопка — отдельной строкой (столбиком)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=l, callback_data=c)] for l, c in zip(labels, cbs)])

SORT_CB = ["danger", "recycle", "trash"]
SORT_KB = inline_kb(["Опасное", "Переработка", "Не переработать"], SORT_CB)
BONUS_KB = inline_kb(["Цвет краски", "Тип пластика для переработки",
                      "Срок годности", "Штрих-код"],
                     ["b_color", "b_plastic", "b_exp", "b_bar"])
L3_KB = inline_kb(["Тайное задание", "Звонок близкому"],
                  ["l3_task", "l3_call"])
URL_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🌙 Открыть тайное задание", url=SITE_URL)]])
L4_KB = inline_kb(["Бестиарий Теней", "Хоррор-катрен", "Викторина"],
                  ["l4_best", "l4_poem", "l4_quiz"])
QUIZ_KB = inline_kb(["Марло", "Булгаков", "Гоголь"],
                    ["q_marlo", "q_bulgakov", "q_gogol"])

# ============================================================
#  ВАЛИДАЦИЯ РЕГИСТРАЦИИ
# ============================================================

def parse_vk(text: str):
    """Принимает id123456, ссылку vk.com/id… или короткое имя."""
    t = (text or "").strip()
    m = re.search(r"(?:vk\.com/|vk\.ru/)?id(\d{4,})", t, re.I)
    if m:
        return "id" + m.group(1)
    m = re.search(r"(?:vk\.com/|vk\.ru/)([A-Za-z][A-Za-z0-9_.]{3,})", t, re.I)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{3,}", t):
        return t
    return None

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

def parse_email(text: str):
    t = (text or "").strip().lower()
    return t if EMAIL_RE.fullmatch(t) else None

def is_valid_name(text: str) -> bool:
    """Имя/фамилия: по-русски, с заглавной; фамилия может быть двойной через дефис."""
    t = (text or "").strip()
    return bool(re.fullmatch(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?", t))

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================

CREATE_PLAYERS = (
    "CREATE TABLE IF NOT EXISTS players ("
    "user_id INTEGER PRIMARY KEY,"
    "nickname TEXT,"
    "vk_id TEXT,"
    "email TEXT,"
    "level INTEGER DEFAULT 0,"
    "sparks INTEGER DEFAULT 0,"
    "codes TEXT,"
    "l3_names TEXT,"
    "code_l3 TEXT,"
    "last_seen REAL)")

async def init_db():
    """Создаёт базу и таблицу при старте бота — до первого запроса."""
    async with aiosqlite.connect(DB) as db:
        await db.execute(CREATE_PLAYERS)
        await db.commit()

async def save(user_id, **fields):
    async with aiosqlite.connect(DB) as db:
        await db.execute(CREATE_PLAYERS)
        await db.execute("INSERT OR IGNORE INTO players(user_id) VALUES(?)", (user_id,))
        for k, v in fields.items():
            await db.execute(f"UPDATE players SET {k}=? WHERE user_id=?", (v, user_id))
        await db.execute("UPDATE players SET last_seen=? WHERE user_id=?", (time.time(), user_id))
        await db.commit()

async def get_player(user_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT nickname, vk_id, email, level FROM players WHERE user_id=?", (user_id,))
        return await cur.fetchone()

class Seen(BaseMiddleware):
    """Один UPDATE на сообщение вместо четырёх запросов."""
    async def __call__(self, handler, event, data):
        try:
            async with aiosqlite.connect(DB) as db:
                await db.execute("UPDATE players SET last_seen=? WHERE user_id=?",
                                 (time.time(), event.from_user.id))
                await db.commit()
        except Exception:
            pass
        return await handler(event, data)

dp.message.middleware(Seen())

# ============================================================
#  ИГРОВЫЕ МЕХАНИКИ
# ============================================================

async def wrong(m: Message, state: FSMContext, hint: str, reveal: str):
    d = await state.get_data()
    att = d.get("att", 0) + 1
    await state.update_data(att=att)
    if att >= 5:
        await state.update_data(att=0, penalty=True)
        await m.answer(f"Хранитель вздыхает и разворачивает свиток: {reveal}\n"
                       "Но за подсмотренное — минус огонёк.")
    elif att >= 3:
        await m.answer(f"Тень шепчет подсказку: {hint}")
    else:
        await m.answer(random.choice([
            "Хм. Тень покачала головой. Ещё раз.",
            "Страница перевернулась сама. Ответ не тот.",
            "Свеча моргнула недовольно. Попробуй иначе."]))

async def _grant(state: FSMContext, code: str, user_id: int):
    d = await state.get_data()
    sparks = 1 if d.get("penalty") else 2
    await state.update_data(att=0, penalty=False)
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE players SET sparks=sparks+?, codes=COALESCE(codes,'')||? WHERE user_id=?",
            (sparks, code + ";", user_id))
        await db.commit()
    return sparks

async def reward(m: Message, state: FSMContext, code: str, text: str):
    """Первое сообщение: похвала + награда. Новое дело присылается отдельно."""
    sparks = await _grant(state, code, m.from_user.id)
    await m.answer(f"{text}\n\n🔥 +{sparks} огонька.\n"
                   f"🔑 Кодовое слово уровня: <b>{code}</b> — запомни, без него не зажечь лампу.",
                   parse_mode="HTML")

async def reward_c(c: CallbackQuery, state: FSMContext, code: str, text: str):
    sparks = await _grant(state, code, c.from_user.id)
    await c.message.answer(f"{text}\n\n🔥 +{sparks} огонька.\n"
                           f"🔑 Кодовое слово уровня: <b>{code}</b> — запомни, без него не зажечь лампу.",
                           parse_mode="HTML")

# ============================================================
#  СОСТОЯНИЯ
# ============================================================

class Quest(StatesGroup):
    intro = State()
    surname = State()
    vk_id = State()
    email = State()
    riddle = State()
    sort_item = State()
    sort_bonus_num = State()
    sort_bonus_q = State()
    l3_choice = State()
    l3_task = State()
    l3_call = State()
    l4_choice = State()
    l4_best = State()
    l4_poem = State()
    l4_quiz = State()
    l5_maze = State()
    l5_squat = State()
    l5_time = State()
    final = State()
    done = State()

L5_MAZE_TEXT = (
    "🗺 Карта зала: из стартовой залы — только <b>вправо</b>; в коридоре —\n"
    "<b>лестница вверх</b>, ещё одна <b>лестница вверх</b>, затем дверь\n"
    "<b>вправо</b> и <b>спуск вниз</b>.\n"
    "Запиши маршрут буквами без пробелов (П — вправо, В — вверх, Н — вниз).")

# ============================================================
#  ОБЩИЕ ВХОДЫ В ИГРУ (без взаимных вызовов — рекурсия невозможна)
# ============================================================

async def begin_registration(m: Message, state: FSMContext):
    await state.set_state(Quest.intro)
    await state.set_data({})
    await send_stage(m, "img_intro.png", LORE_INTRO)
    await m.answer("Назови своё имя, Ночной Секретарь.")

async def continue_quest(m: Message, state: FSMContext, reentry: bool = False):
    row = await get_player(m.from_user.id)
    if not row or not (row[0] and row[1] and row[2]):
        await begin_registration(m, state)
        return
    lvl = row[3] or 0
    if reentry:
        await m.answer("Тень привела тебя обратно.")
    if lvl in (0, 1):
        await state.set_state(Quest.riddle)
        await state.set_data({"r": 0})
        await send_stage(m, "img_task1.png", TRANS_1, RIDDLES[0][0])
        return
    if lvl == 2:
        await state.set_state(Quest.sort_item)
        await state.set_data({"idx": 0})
        await send_stage(m, "img_task2.png", TRANS_2,
                         f"Куда отправить: <b>{SORT_ITEMS[0][0]}</b>?", SORT_KB)
        return
    if lvl == 3:
        await state.set_state(Quest.l3_choice)
        await state.set_data({})
        await send_stage(m, "img_task3.png", TRANS_3, "Выбери путь:", L3_KB)
        return
    if lvl == 4:
        await state.set_state(Quest.l4_choice)
        await state.set_data({})
        await send_stage(m, "img_task4.png", TRANS_4, "Выбери, чем заполнить раму:", L4_KB)
        return
    if lvl == 5:
        await state.set_state(Quest.l5_maze)
        await state.set_data({})
        await send_stage(m, "img_task5.png", TRANS_5, L5_MAZE_TEXT)
        return
    if lvl >= 6:
        await state.set_state(Quest.done)
        await m.answer("Архив закрыт. Мия тихонько полирует лампу 🕯")
        return

# ============================================================
#  КОМАНДЫ (зарегистрированы ДО игровых состояний —
#  срабатывают из любого состояния, включая середину загадки)
# ============================================================

@dp.message(Command("start"))
async def start_cmd(m: Message, state: FSMContext):
    await state.clear()
    row = await get_player(m.from_user.id)
    if row and row[0] and row[1] and row[2]:
        await continue_quest(m, state)
    else:
        await begin_registration(m, state)

@dp.message(Command("quest"))
async def quest_cmd(m: Message, state: FSMContext):
    await continue_quest(m, state, reentry=True)

@dp.message(Command("progress"))
async def progress_cmd(m: Message):
    row = await get_player(m.from_user.id)
    if not row or not row[0]:
        await m.answer("Книга Архива пока не знает тебя. Начни с /start")
        return
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT level, sparks, codes FROM players WHERE user_id=?", (m.from_user.id,))
        lvl, sparks, codes = (await cur.fetchone()) or (0, 0, "")
    got = (codes or "").replace(";", " ").split()
    chain = " ".join("✅" if c in got else "⬜" for c in CODES)
    await m.answer(f"🕯 Секретарь <b>{row[0]}</b>\n"
                   f"Дела: {chain}\n"
                   f"Огоньки: {sparks}🔥\n"
                   + (LORE_PLEDGE if lvl < 6 else "Ты довёл дело до конца. Тени гордятся тобой."),
                   parse_mode="HTML")

# --- АДМИН-КОМАНДЫ ---

ADMIN_HELP = (
    "🛠 Команды Хранителя:\n"
    "/stats — сводка по участникам\n"
    "/export — выгрузка итогов CSV-файлом\n"
    "/reset <id_игрока> — полный сброс (прогресс и регистрация)\n"
    "/broadcast <текст> — объявление всем участникам")

def is_admin(m: Message) -> bool:
    return m.from_user.id in ADMIN_IDS

@dp.message(Command("admin"))
async def admin_cmd(m: Message):
    await m.answer(ADMIN_HELP if is_admin(m) else "🔒 Здесь пахнет сургучом. Это не для Секретарей.")

@dp.message(Command("stats"))
async def stats_cmd(m: Message):
    if not is_admin(m):
        await m.answer("🔒 Книга Архива доступна только Хранителю.")
        return
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            """SELECT nickname, vk_id, email, level, sparks, user_id
               FROM players WHERE nickname IS NOT NULL
               ORDER BY sparks DESC, level DESC""")
        rows = await cur.fetchall()
    if not rows:
        await m.answer("Архив пока пуст — ни одного Секретаря.")
        return
    lines = ["📊 <b>Итоги квеста</b> (по огонькам)\n"]
    for i, (nick, vk, email, lvl, sparks, uid) in enumerate(rows, 1):
        place = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        status = "🏁 финал" if lvl >= 6 else f"дело №{max(lvl, 1)}"
        lines.append(f"{place} <b>{nick}</b> — {sparks}🔥, {status}\n"
                     f"   VK: vk.com/{vk or '—'} | почта: {email or '—'} | TG: {uid}")
    text = "\n".join(lines)
    for chunk in (text[i:i + 4000] for i in range(0, len(text), 4000)):
        await m.answer(chunk, parse_mode="HTML")

@dp.message(Command("export"))
async def export_cmd(m: Message):
    if not is_admin(m):
        await m.answer("🔒 Книга Архива доступна только Хранителю.")
        return
    path = "quest_export.csv"
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            """SELECT user_id, nickname, vk_id, email, level, sparks, codes
               FROM players WHERE nickname IS NOT NULL ORDER BY sparks DESC""")
        rows = await cur.fetchall()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Telegram ID", "Фамилия Имя", "VK", "Почта", "Дело №", "Огоньки", "Коды"])
        for uid, nick, vk, email, lvl, sparks, codes in rows:
            w.writerow([uid, nick or "", vk or "", email or "", max(lvl, 1),
                        sparks, (codes or "").replace(";", ", ")])
    await m.answer_document(FSInputFile(path), caption="Свиток итогов 🕯")

@dp.message(Command("reset"))
async def reset_cmd(m: Message, state: FSMContext):
    if not is_admin(m):
        await m.answer("🔒 Только Хранитель может стирать дела из книги.")
        return
    parts = m.text.split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await m.answer("Формат: /reset <id_игрока>. ID можно взять из /stats.")
        return
    uid = int(parts[1])
    async with aiosqlite.connect(DB) as db:
        await db.execute(CREATE_PLAYERS)
        cur = await db.execute("SELECT nickname FROM players WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        if not row:
            await m.answer("Такого Секретаря в книге нет.")
            return
        # ПОЛНЫЙ сброс: прогресс + регистрация (имя, ВК, почта)
        await db.execute("""UPDATE players SET level=0, sparks=0, codes='',
                            l3_names='', code_l3=NULL, nickname=NULL,
                            vk_id=NULL, email=NULL WHERE user_id=?""", (uid,))
        await db.commit()
    # Сброс FSM-состояния игрока (даже если это не сам админ)
    try:
        key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await dp.storage.set_state(key, state=None)
        await dp.storage.set_data(key, {})
    except Exception:
        pass
    await m.answer(f"Прогресс и регистрация «{row[0]}» стёрты полностью.\n"
                   "Архив забыл Секретаря — пусть напишет /start и запишется заново.")

@dp.message(Command("broadcast"))
async def broadcast_cmd(m: Message):
    if not is_admin(m):
        await m.answer("🔒 Голос Хранителя не подделать.")
        return
    text = (m.text or "").removeprefix("/broadcast").strip()
    if not text:
        await m.answer("Формат: /broadcast <текст> — объявление придёт всем участникам.")
        return
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id FROM players WHERE nickname IS NOT NULL")
        ids = await cur.fetchall()
    sent = 0
    for (uid,) in ids:
        try:
            await bot.send_message(uid, f"🕯 <b>Шёпот из Архива</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await m.answer(f"📢 Объявление доставлено: {sent} из {len(ids)} Секретарей.")

# ============================================================
#  РЕГИСТРАЦИЯ: имя → фамилия → ВК → почта
# ============================================================

@dp.message(Quest.intro)
async def intro(m: Message, state: FSMContext):
    if not is_valid_name(m.text):
        await m.answer("Имя — по-русски, одним словом и с заглавной буквы. Например: Мария.")
        return
    await state.update_data(first=m.text.strip())
    await state.set_state(Quest.surname)
    await m.answer(f"Приятно познакомиться, {m.text.strip()}.\n"
                   "Теперь фамилия — тоже с заглавной (двойную пиши через дефис,\n"
                   "отчество Архиву не нужен).")

@dp.message(Quest.surname)
async def surname_input(m: Message, state: FSMContext):
    if not is_valid_name(m.text):
        await m.answer("Фамилия — по-русски, с заглавной буквы (двойную — через дефис). Попробуй ещё раз.")
        return
    d = await state.get_data()
    full = f"{m.text.strip()} {d.get('first', 'Секретарь')}"
    await save(m.from_user.id, nickname=full)
    await state.set_state(Quest.vk_id)
    await m.answer(LORE_REG, parse_mode="HTML")
    await m.answer(f"В книгу вписано: <b>{full}</b>.\n\n"
                   "Оставь отметку ВКонтакте:\n"
                   "ссылку (vk.com/…), ID (например id123456789) или короткое имя страницы.",
                   parse_mode="HTML")

@dp.message(Quest.vk_id)
async def vk_input(m: Message, state: FSMContext):
    vk = parse_vk(m.text)
    if not vk:
        await m.answer("Это не похоже на отметку ВКонтакте.\n"
                       "Нужна ссылка vk.com/…, ID вида id123456 или короткое имя страницы.")
        return
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id FROM players WHERE vk_id=? AND user_id<>?",
                               (vk.lower(), m.from_user.id))
        if await cur.fetchone():
            await m.answer("Эта душа уже значится в книге под другим секретарём.\n"
                           "Пришли свой собственный профиль ВКонтакте.")
            return
    await save(m.from_user.id, vk_id=vk.lower())
    await state.set_state(Quest.email)
    await m.answer("Отметка принята. Теперь почта — туда «Другое Дело»\n"
                   "начислит баллы за закрытые дела. Пример: secretar@pochta.ru")

@dp.message(Quest.email)
async def email_input(m: Message, state: FSMContext):
    email = parse_email(m.text)
    if not email:
        await m.answer("Почта не похожа на почту. Проверь формат: имя@домен.ру")
        return
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id FROM players WHERE email=? AND user_id<>?",
                               (email, m.from_user.id))
        if await cur.fetchone():
            await m.answer("Эта почта уже записана в книгу за другим Секретарём.\n"
                           "Пришли свою — иначе баллы уйдут не туда.")
            return
    await save(m.from_user.id, email=email, level=1)
    await state.set_state(Quest.riddle)
    await state.set_data({"r": 0})
    await m.answer("✅ Реестр подписан. Двери Архива скрипят и открываются…")
    await asyncio.sleep(PAUSE)
    await send_stage(m, "img_task1.png", TRANS_1, RIDDLES[0][0])

# ============================================================
#  УРОВЕНЬ 1. Обучение
# ============================================================

@dp.message(Quest.riddle)
async def riddle(m: Message, state: FSMContext):
    d = await state.get_data()
    r = d.get("r", 0)
    q, ans, hint = RIDDLES[r]
    if norm(m.text) in ans:
        if r + 1 < len(RIDDLES):
            await state.update_data(r=r + 1)
            await m.answer("✅ Верно. Свеча дрожит — следующий вопрос:\n\n" + RIDDLES[r + 1][0])
        else:
            await save(m.from_user.id, level=2)
            await state.set_state(Quest.sort_item)
            await state.update_data(idx=0)
            await reward(m, state, CODES[0],
                         "✅ Конспект закрыт. Цифры замолчали — по крайней мере, до сессии.")
            await asyncio.sleep(PAUSE)
            await send_stage(m, "img_task2.png", TRANS_2,
                             f"Куда отправить: <b>{SORT_ITEMS[0][0]}</b>?", SORT_KB)
    else:
        await wrong(m, state, hint, "ответ: " + ", ".join(sorted(ans)))

# ============================================================
#  УРОВЕНЬ 2. Экология
# ============================================================

@dp.message(Quest.sort_item)
async def sort_item(m: Message, state: FSMContext):
    await m.answer("Выбери склеп кнопкой под сообщением 🔘")

@dp.callback_query(Quest.sort_item, F.data.in_(SORT_CB))
async def sort_cb(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    idx = d.get("idx", 0)
    item, right = SORT_ITEMS[idx]
    pressed = {"danger": "Опасное", "recycle": "Переработка",
               "trash": "Не переработать"}[c.data]
    if pressed == right:
        await c.answer("✅ Склеп принял.")
        idx += 1
        await state.update_data(idx=idx)
        if idx < len(SORT_ITEMS):
            try:
                await c.message.edit_text(
                    f"✅ Склеп принял. Далее: куда отправить — <b>{SORT_ITEMS[idx][0]}</b>?",
                    reply_markup=SORT_KB, parse_mode="HTML")
            except Exception:
                await c.message.answer(
                    f"✅ Склеп принял. Далее: куда отправить — <b>{SORT_ITEMS[idx][0]}</b>?",
                    reply_markup=SORT_KB, parse_mode="HTML")
        else:
            await state.set_state(Quest.sort_bonus_num)
            try:
                await c.message.edit_text(
                    "✅ Чердак чист! Бутылка 1997 года наконец ушла на переработку.\n\n"
                    "Последний штрих Хранителя: подойди к любой пластиковой ёмкости дома\n"
                    "и найди треугольник со стрелками — внутри цифра от 1 до 7. Введи её.")
            except Exception:
                await c.message.answer(
                    "✅ Чердак чист! Бутылка 1997 года наконец ушла на переработку.\n\n"
                    "Последний штрих Хранителя: подойди к любой пластиковой ёмкости дома\n"
                    "и найди треугольник со стрелками — внутри цифра от 1 до 7. Введи её.")
    else:
        await c.answer("❌ Не тот склеп!", show_alert=False)
        await c.message.answer(
            "❌ Призрак недовольно дребезжит бутылкой. Попробуй другой склеп.")

@dp.message(Quest.sort_bonus_num)
async def sort_bonus_num(m: Message, state: FSMContext):
    t = (m.text or "").strip()
    if t in "1234567" and len(t) == 1:
        await state.set_state(Quest.sort_bonus_q)
        await m.answer(f"Цифра {t}. Хорошо. А что означает она в треугольнике?",
                       reply_markup=BONUS_KB)
    else:
        await wrong(m, state, "Подойди к любой ёмкости — внутри треугольника цифра от 1 до 7.",
                    "цифра от 1 до 7")

@dp.message(Quest.sort_bonus_q)
async def sort_bonus_q(m: Message, state: FSMContext):
    await m.answer("Выбери ответ кнопкой под сообщением 🔘")

@dp.callback_query(Quest.sort_bonus_q, F.data == "b_plastic")
async def bonus_ok(c: CallbackQuery, state: FSMContext):
    await c.answer("✅ Верно!")
    await save(c.from_user.id, level=3)
    await state.set_state(Quest.l3_choice)
    await state.set_data({})
    await reward_c(c, state, CODES[1],
                   "✅ Призрак рассортирован и наконец успокоился. Мусор, рассортированный вовремя,\n"
                   "не призрак, а ресурс.")
    await asyncio.sleep(PAUSE)
    await send_stage(c.message, "img_task3.png", TRANS_3, "Выбери путь:", L3_KB)

@dp.callback_query(Quest.sort_bonus_q)
async def bonus_wrong(c: CallbackQuery):
    await c.answer("❌ Не то. Цифра — это материал, из которого сделан пластик.",
                   show_alert=False)
    await c.message.answer("❌ Тень качает головой. Попробуй другую кнопку.")

# ============================================================
#  УРОВЕНЬ 3. Волонтёрство: «Тайное задание» на сайте или звонок
# ============================================================

@dp.message(Quest.l3_choice)
async def l3_choice(m: Message, state: FSMContext):
    await m.answer("Выбери путь кнопкой под сообщением 🔘")

@dp.callback_query(Quest.l3_choice, F.data == "l3_task")
async def l3_task_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l3_task)
    try:
        await c.message.edit_text(SECRET_LORE, reply_markup=URL_KB, parse_mode="HTML")
    except Exception:
        await c.message.answer(SECRET_LORE, reply_markup=URL_KB, parse_mode="HTML")

@dp.callback_query(Quest.l3_choice, F.data == "l3_call")
async def l3_call_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l3_call)
    await c.message.edit_text(
        "Позвони пожилому близкому человеку и узнай,\n"
        "в каком ГОДУ он пошёл в первый класс.\n"
        "Введи только год — Архив слышит звонки.")

@dp.message(Quest.l3_task)
async def l3_secret(m: Message, state: FSMContext):
    if norm(m.text) in L3_SECRET:
        await save(m.from_user.id, level=4)
        await state.set_state(Quest.l4_choice)
        await state.set_data({})
        await reward(m, state, CODES[2],
                     "✅ Шифр разгадан — страница переписана набело, и дело получило имя.\n"
                     "Добро, сделанное ночью, светит вдвойне.")
        await asyncio.sleep(PAUSE)
        await send_stage(m, "img_task4.png", TRANS_4, "Выбери, чем заполнить раму:", L4_KB)
    else:
        await wrong(m, state,
                    "Каждое число — номер буквы алфавита (с Ё). Открой тайное задание по ссылке "
                    "и найди строку чисел в описании.",
                    f"числа из задания: {CIPHER_LINE} — это слово НОЧЬ")

@dp.message(Quest.l3_call)
async def l3_call(m: Message, state: FSMContext):
    digits = re.sub(r"\D", "", m.text or "")
    if digits.isdigit() and 1900 <= int(digits) <= 2020:
        await save(m.from_user.id, level=4, code_l3=digits)
        await state.set_state(Quest.l4_choice)
        await state.set_data({})
        await reward(m, state, CODES[2],
                     f"✅ История услышана — Тень улыбнулась. Год {digits} занесён в книгу Архива.\n"
                     "Такие разговоры, пока звучат, не дают Теням расти.")
        await asyncio.sleep(PAUSE)
        await send_stage(m, "img_task4.png", TRANS_4, "Выбери, чем заполнить раму:", L4_KB)
    else:
        await wrong(m, state, "Нужен год первого класса — четыре цифры от 1900 до 2020.",
                    "год поступления в первый класс (1900–2020)")

# ============================================================
#  УРОВЕНЬ 4. Культура и искусство
# ============================================================

@dp.message(Quest.l4_choice)
async def l4_choice(m: Message, state: FSMContext):
    await m.answer("Выбирай кнопкой под сообщением 🔘")

@dp.callback_query(Quest.l4_choice, F.data == "l4_best")
async def l4_best_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l4_best)
    await c.message.edit_text(
        "Опиши свою Тень (то, что мешает тебе завершать дела)\n"
        "тремя словами-существительными.\nНапример: дедлайн, лень, тревога.")

@dp.callback_query(Quest.l4_choice, F.data == "l4_poem")
async def l4_poem_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l4_poem)
    await c.message.edit_text(
        "Напиши 4 строки хоррора. Условие Хранителя:\n"
        "последняя строка ОБЯЗАНА содержать слово «свет» —\n"
        "иначе стихотворение не выйдет из Архива.")

@dp.callback_query(Quest.l4_choice, F.data == "l4_quiz")
async def l4_quiz_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l4_quiz)
    try:
        await c.message.edit_text(
            "Кто написал пьесу, где герой продаёт душу дьяволу ради знаний?",
            reply_markup=QUIZ_KB)
    except Exception:
        await c.message.answer(
            "Кто написал пьесу, где герой продаёт душу дьяволу ради знаний?",
            reply_markup=QUIZ_KB)

@dp.message(Quest.l4_quiz)
async def l4_quiz(m: Message, state: FSMContext):
    await m.answer("Выбери ответ кнопкой под сообщением 🔘")

@dp.callback_query(Quest.l4_quiz, F.data == "q_marlo")
async def quiz_ok(c: CallbackQuery, state: FSMContext):
    await c.answer("✅ Верно!")
    await save(c.from_user.id, level=5)
    await state.set_state(Quest.l5_maze)
    await state.set_data({})
    await reward_c(c, state, CODES[3],
                   "✅ Кристофер Марло — современник Шекспира. Фауст, продавший душу,\n"
                   "в Архиве числится с 1588 года.")
    await asyncio.sleep(PAUSE)
    await send_stage(c.message, "img_task5.png", TRANS_5, L5_MAZE_TEXT)

@dp.callback_query(Quest.l4_quiz)
async def quiz_wrong(c: CallbackQuery):
    await c.answer("❌ Тень качает головой. Не Булгаков и не Гоголь.", show_alert=False)
    await c.message.answer("❌ Не то. Это англичанин, современник Шекспира.")

@dp.message(Quest.l4_best)
async def l4_best(m: Message, state: FSMContext):
    words = re.findall(r"[а-яёА-ЯЁa-zA-Z]+", m.text or "")
    if len(words) == 3 and len(set(map(str.lower, words))) == 3:
        await save(m.from_user.id, level=5, l3_names=", ".join(words))
        await state.set_state(Quest.l5_maze)
        await state.set_data({})
        await reward(m, state, CODES[3],
                     f"✅ Твоя Тень занесена в Бестиарий: <b>{', '.join(words)}</b>.\n"
                     "Названная тень — уже наполовину обычный страх.")
        await asyncio.sleep(PAUSE)
        await send_stage(m, "img_task5.png", TRANS_5, L5_MAZE_TEXT)
    else:
        await wrong(m, state, "Ровно три разных слова-существительных.",
                    "ровно три различных существительных")

@dp.message(Quest.l4_poem)
async def l4_poem(m: Message, state: FSMContext):
    lines = [l for l in (m.text or "").split("\n") if l.strip()]
    if len(lines) == 4 and "свет" in lines[3].lower():
        await save(m.from_user.id, level=5)
        await state.set_state(Quest.l5_maze)
        await state.set_data({})
        await reward(m, state, CODES[3],
                     "✅ Тень прочитала катрен и… заплакала светом.\n"
                     "Твой стих повесят в раме. Слава Хранителя.")
        await asyncio.sleep(PAUSE)
        await send_stage(m, "img_task5.png", TRANS_5, L5_MAZE_TEXT)
    else:
        await wrong(m, state, "Ровно 4 строки, в последней — слово «свет».",
                    "4 строки, последняя содержит слово «свет»")

# ============================================================
#  УРОВЕНЬ 5. Здоровье и спорт
# ============================================================

@dp.message(Quest.l5_maze)
async def l5_maze(m: Message, state: FSMContext):
    if norm(m.text).upper() == "ПВВПН":
        await state.set_state(Quest.l5_squat)
        await state.update_data(squat_time=time.time())
        await m.answer("✅ Отражение мигнуло — живое!\n\n"
                       "Последний зал: <b>Приседания Хранителя</b>.\n"
                       "Сделай серию: 10 → пауза → 15 → пауза → 20.\n"
                       "Когда закончишь — напиши, сколько всего приседаний сделал.\n"
                       "На это 3 минуты: Архив видит всё, но считает только честное.",
                       parse_mode="HTML")
    else:
        await wrong(m, state, "Перечитай карту: вправо, вверх, вверх, вправо, вниз.",
                    "П В В П Н")

@dp.message(Quest.l5_squat)
async def l5_squat(m: Message, state: FSMContext):
    d = await state.get_data()
    if norm(m.text) in {"45", "сорокпять"}:
        if time.time() - d.get("squat_time", 0) <= 180:
            await state.set_state(Quest.l5_time)
            await m.answer("✅ 45! Зеркало снова показывает тебя.\n\n"
                           "Последний вопрос Хранителя:\n"
                           "Лекция в 8:30, дорога 40 минут, сборы 30, запас 10.\n"
                           "Во сколько встать? (формат ЧЧ:ММ)")
        else:
            await state.update_data(squat_time=time.time())
            await m.answer("Время вышло — Тень усомнилась. Сделай серию заново:\n"
                           "10 → 15 → 20, и напиши сумму.")
    else:
        await wrong(m, state, "Посчитать можно только сделав: 10 + 15 + 20.",
                    "сумма 10 + 15 + 20 (но приседания всё равно сделать — Архив всё видит)")

@dp.message(Quest.l5_time)
async def l5_time(m: Message, state: FSMContext):
    if norm(m.text) in {"710", "0710", "7:10", "07:10", "7ч10м"}:
        await save(m.from_user.id, level=6)
        await state.set_state(Quest.final)
        await state.set_data({})
        await reward(m, state, CODES[4],
                     "✅ Отражение вернулось на место — и впервые за много лет\n"
                     "улыбнулось человеку.\n\n"
                     "🔥 <b>АРХИВ ГОТОВ К ЗАКРЫТИЮ</b> 🔥")
        await asyncio.sleep(PAUSE)
        await send_stage(m, None, TRANS_FINAL,
                         "Введи все пять кодовых слов одной строкой, через пробел,\n"
                         "в порядке дел 1–5.")
    else:
        await wrong(m, state, "Из 8:30 вычти дорогу, сборы и запас.", "07:10")

# ============================================================
#  ФИНАЛ: лор и итоговый «сертификат» одним сообщением с фото
# ============================================================

@dp.message(Quest.final)
async def final(m: Message, state: FSMContext):
    row = await get_player(m.from_user.id)
    nick, sparks, code_l3 = (row[0], 0, None) if row else ("Секретарь", 0, None)
    if row:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT sparks, code_l3 FROM players WHERE user_id=?", (m.from_user.id,))
            s = await cur.fetchone()
        if s:
            sparks, code_l3 = s
    expected = norm(" ".join(CODES))
    said = norm(m.text)
    # Страховка для старых записей: третий код мог сохраниться как год звонка
    ok = said == expected
    if not ok and code_l3:
        alt = norm(" ".join(CODES[:2] + [str(code_l3)] + CODES[3:]))
        ok = said == alt
    if ok:
        await state.set_state(Quest.done)
        cert_text = (
            "🔦 <b>СЕРТИФИКАТ НОЧНОГО СЕКРЕТАРЯ</b>\n\n"
            f"<b>{nick}</b>\n"
            f"закрыл(а) все дела Архива — {sparks} огоньков\n\n"
            "Квест «Другая Сторона Дела» — проект «Другое Дело»\n\n"
            "Отправь это сообщение в мини-приложение «Другого Дела» —\n"
            "там зачтут задание и начислят баллы на почту из реестра.\n\n"
            "«Дело, доведённое до конца, не боится темноты»")
        caption = LORE_FINAL.format(nick=nick) + "\n\n" + cert_text
        sent = await send_img(m, "img_final.png", caption=caption)
        if not sent:
            await m.answer(LORE_FINAL.format(nick=nick), parse_mode="HTML")
            await m.answer(cert_text, parse_mode="HTML")
    else:
        await wrong(m, state, "Пять слов, по одному с каждого уровня, в порядке дел 1–5.",
                    "коды уровней в порядке 1–5 через пробел")

@dp.message(Quest.done)
async def done(m: Message):
    await m.answer(random.choice([
        "Архив закрыт. Мия полирует лампу и улыбается 🕯",
        "Тени впервые за год спят спокойно. Спасибо, Секретарь.",
        "Ты уже всё закрыл. Отдыхай — дело доведено до конца."]))

# ============================================================
#  НАПОМИНАНИЯ
# ============================================================

async def reminders():
    while True:
        await asyncio.sleep(3600)
        try:
            async with aiosqlite.connect(DB) as db:
                cur = await db.execute(
                    "SELECT user_id FROM players WHERE last_seen < ? AND level BETWEEN 1 AND 5",
                    (time.time() - 20 * 3600,))
                ids = await cur.fetchall()
            for (uid,) in ids:
                try:
                    await bot.send_message(uid, random.choice([
                        "🕯 Шёпот из Архива: дела сами себя не закроют, Секретарь.",
                        "🕯 Тень шуршит страницами: /quest — вернись к делу.",
                        "🕯 Мия зажгла лампу и ждёт. /quest — вернись к делу."]))
                    await save(uid)
                except Exception:
                    pass
        except Exception:
            pass

# ============================================================
#  СТРАХОВКА: кнопки из старых сообщений
# ============================================================

@dp.callback_query()
async def stale_buttons(c: CallbackQuery):
    await c.answer("Это кнопка из старого сообщения — нажми на кнопки под последним вопросом.",
                   show_alert=True)

# ============================================================
#  ЗАПУСК
# ============================================================

async def main():
    await init_db()
    asyncio.create_task(reminders())
    print("🕯 Архив открыт. Бот работает.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
