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
from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardRemove, FSInputFile,
                           InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery)

TOKEN = os.environ.get("BOT_TOKEN") or (
    open("token.txt").read().strip() if os.path.exists("token.txt") else "")
if not TOKEN:
    raise SystemExit("Токен не найден: задай переменную окружения BOT_TOKEN "
                     "или создай файл token.txt с токеном от @BotFather")

DB = "quest.db"
ADMIN_IDS = {1467490182}  # ← впиши свой Telegram user_id (узнать: @userinfobot)

PAUSE = 1.5  # пауза между «наградой» и «новым делом», секунды

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
    "В эту ночь тебе выпадет должность Ночного Секретаря. Пять дел,\n"
    "пять кодовых слов, пять огоньков. Собери их — и помоги Мие зажечь лампу,\n"
    "чтобы закрыть Архив навсегда.\n\n"
    "«Дело, доведённое до конца, не боится темноты»."
)

LORE_REG = (
    "Прежде чем впустить тебя, Хранитель обязан занести тебя в книгу.\n\n"
    "📜 <b>Страница реестра</b>\n"
    "Имя и фамилия — под ними Тени будут звать тебя.\n"
    "Отметка ВКонтакте — чтобы Архив знал, где ты живёшь среди живых.\n"
    "Почта — туда «Другое Дело» начислит баллы за закрытые дела."
)

LORE_FINAL = (
    "🔦 <b>ЛАМПА ЗАЖГЛАСЬ</b>\n\n"
    "Пять огоньков слились в один ровный свет. Тени поклонились —\n"
    "и растаяли, как чернила, наконец высохшие на бумаге.\n\n"
    "Архив закрыт. Ни одного незавершённого дела не осталось в этих\n"
    "стенах. А это значит — у каждой Тени теперь есть шанс стать\n"
    "не тенью, а делом.  \n\n"
    "Поздравляю, {nick} мы справились!!!. \n"
)

LORE_PLEDGE = (
    "Один Секретарь ушёл, не закончив дело, — и теперь он бродит\n"
    "по снам участников квеста, шепчет: «доведи до конца…».\n"
    "Не будь как он. Закрой все пять дел."
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

# --- Секретное задание дела №3 ---
SECRET_TASK_NAME = "Ночной переписчик"   # название задания в «Другом Деле»
CIPHER_LINE = "15-16-25-30"              # числа, вшитые в описание задания
L3_SECRET = {"ночь"}                     # разгадка (НОЧЬ: Н=15, О=16, Ч=25, Ь=30)

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================

def inline_kb(labels, cbs):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=l, callback_data=c) for l, c in zip(labels, cbs)]])

SORT_CB = ["danger", "recycle", "trash"]
SORT_KB = inline_kb(["Опасное", "Переработка", "Не переработать"], SORT_CB)
BONUS_KB = inline_kb(["Цвет краски", "Тип пластика для переработки",
                      "Срок годности", "Штрих-код"],
                     ["b_color", "b_plastic", "b_exp", "b_bar"])
L3_KB = inline_kb(["Задание из «Другого Дела»", "Звонок близкому"],
                  ["l3_task", "l3_call"])
L4_KB = inline_kb(["Бестиарий Теней", "Хоррор-катрен", "Викторина"],
                  ["l4_best", "l4_poem", "l4_quiz"])
QUIZ_KB = inline_kb(["Марло", "Булгаков", "Гоголь"],
                    ["q_marlo", "q_bulgakov", "q_gogol"])

# ============================================================
#  КАРТИНКИ КВЕСТА
# ============================================================

IMG_INTRO = "img_intro.png"
IMG_TASKS = {1: "img_task1.png", 2: "img_task2.png", 3: "img_task3.png",
             4: "img_task4.png", 5: "img_task5.png"}
IMG_FINAL = "img_final.png"

async def send_img(chat_id: int, fname: str):
    """Шлёт иллюстрацию, если файл есть. Нет файла — молча пропускаем."""
    try:
        await bot.send_photo(chat_id, FSInputFile(fname))
    except Exception:
        pass

# ============================================================
#  ВАЛИДАЦИЯ РЕГИСТРАЦИИ
# ============================================================

def valid_rus_name(t: str) -> bool:
    """Русское слово с заглавной: Иван, Мария-Анна, Дюма."""
    return bool(re.fullmatch(r"[А-ЯЁ][а-яё]+(?:[-\s][А-ЯЁ][а-яё]+)*",
                             (t or "").strip()))

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

class Seen(BaseMiddleware):
    """Лёгкая версия: один UPDATE на сообщение вместо четырёх запросов.
    Регистрация игрока происходит в save() во время сценария регистрации."""
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
                   f"🔑 Кодовое слово уровня: <b>{code}</b> — запомни, без него не зажечь лампы.",
                   parse_mode="HTML")

async def reward_c(c: CallbackQuery, state: FSMContext, code: str, text: str):
    sparks = await _grant(state, code, c.from_user.id)
    await c.message.answer(f"{text}\n\n🔥 +{sparks} огонька.\n"
                           f"🔑 Кодовое слово уровня: <b>{code}</b> — запомни, без него не зажечь лампы.",
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
    "Зеркальный зал пуст. Тени забрали твоё отражение — верни его.\n\n"
    "🗺 Карта зала: из стартовой залы — только <b>вправо</b>; в коридоре —\n"
    "<b>лестница вверх</b>, ещё одна <b>лестница вверх</b>, затем дверь\n"
    "<b>вправо</b> и <b>спуск вниз</b>.\n"
    "Запиши маршрут буквами без пробелов (П — вправо, В — вверх, Н — вниз).")

L5_ENTRY = "\n\n🕯 <b>Дело №5: «Зеркало без отражения»</b>\n" + L5_MAZE_TEXT

L3_CHOICE_TEXT = (
    "🕯 <b>Дело №3: «Тень без имени»</b>\n"
    "У этого дела нет имени — его не завершил никто и никогда.\n"
    "Тени нужен человек, который сделает доброе дело прямо сейчас.\n"
    "Выбери путь:")

L4_CHOICE_TEXT = (
    "🕯 <b>Дело №4: «Портрет в скетчбуке»</b>\n"
    "В Архиве стоит мольберт с пустым холстом. Тень, которую коснётся\n"
    "картина, перестанет быть тенью. Выбери, чем заполнить полотно:")

# ============================================================
#  КОМАНДЫ
# ============================================================

@dp.message(Command("start"))
async def start_cmd(m: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT nickname, vk_id, email FROM players WHERE user_id=?", (m.from_user.id,))
        row = await cur.fetchone()
    if row and row[0] and row[1] and row[2]:
        await quest_cmd(m, state)
        return
    await state.set_state(Quest.intro)
    await send_img(m.from_user.id, IMG_INTRO)
    await m.answer(LORE_INTRO, parse_mode="HTML")
    await m.answer("Назови своё имя, Ночной Секретарь.")

@dp.message(Command("quest"))
async def quest_cmd(m: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT level FROM players WHERE user_id=?", (m.from_user.id,))
        row = await cur.fetchone()
    if not row or not (row[0] if row else 0):
        await start_cmd(m, state)
        return
    lvl = row[0]
    if lvl <= 1:
        await state.set_state(Quest.riddle)
        await state.set_data({"r": 0})
        await send_img(m.from_user.id, IMG_TASKS[1])
        await m.answer("Дело №1: «Тень на таблицах».\n\n" + RIDDLES[0][0])
        return
    if lvl == 2:
        await state.set_state(Quest.sort_item)
        await state.set_data({"idx": 0})
        await send_img(m.from_user.id, IMG_TASKS[2])
        await m.answer(f"Куда отправить: <b>{SORT_ITEMS[0][0]}</b>?",
                       reply_markup=SORT_KB, parse_mode="HTML")
        return
    if lvl == 3:
        await state.set_state(Quest.l3_choice)
        await state.set_data({})
        await send_img(m.from_user.id, IMG_TASKS[3])
        await m.answer("Тень привела тебя обратно. " + L3_CHOICE_TEXT,
                       reply_markup=L3_KB, parse_mode="HTML")
        return
    if lvl == 4:
        await state.set_state(Quest.l4_choice)
        await state.set_data({})
        await send_img(m.from_user.id, IMG_TASKS[4])
        await m.answer("Тень привела тебя обратно. " + L4_CHOICE_TEXT,
                       reply_markup=L4_KB, parse_mode="HTML")
        return
    if lvl == 5:
        await state.set_state(Quest.l5_maze)
        await state.set_data({})
        await send_img(m.from_user.id, IMG_TASKS[5])
        await m.answer("Тень привела тебя обратно. " + L5_MAZE_TEXT, parse_mode="HTML")
        return
    await state.set_state(Quest.done)
    await m.answer("Архив закрыт. Хранитель тихонько полирует лампу 🕯")

@dp.message(Command("progress"))
async def progress_cmd(m: Message):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT nickname, level, sparks, codes FROM players WHERE user_id=?", (m.from_user.id,))
        row = await cur.fetchone()
    if not row or not row[0]:
        await m.answer("Книга Архива пока не знает тебя. Начни с /start")
        return
    nick, lvl, sparks, codes = row
    got = (codes or "").replace(";", " ").split()
    chain = " ".join("✅" if c in got else "⬜" for c in CODES)
    await m.answer(f"🕯 Секретарь <b>{nick}</b>\n"
                   f"Дела: {chain}\n"
                   f"Огоньки: {sparks}🔥\n"
                   + (LORE_PLEDGE if lvl < 6 else "Ты довёл дело до конца. Тени гордятся тобой."),
                   parse_mode="HTML")

# ============================================================
#  РЕГИСТРАЦИЯ: имя → фамилия → ВК → почта
# ============================================================

@dp.message(Quest.intro)
async def intro(m: Message, state: FSMContext):
    name = (m.text or "").strip().title()
    if not valid_rus_name(name):
        await m.answer("Имя должно быть по-русски и с большой буквы.\n"
                       "Перепиши его пером, как в древних книгах.")
        return
    await state.update_data(name=name)
    await state.set_state(Quest.surname)
    await m.answer("Имя записано. Теперь фамилия — книга Архива требует её без пропусков.")

@dp.message(Quest.surname)
async def surname_input(m: Message, state: FSMContext):
    surname = (m.text or "").strip().title()
    if not valid_rus_name(surname):
        await m.answer("Фамилия должна быть по-русски и с большой буквы.\n"
                       "Перепиши её пером, как в древних книгах.")
        return
    d = await state.get_data()
    full = f"{surname} {d.get('name', '')}".strip()
    await save(m.from_user.id, nickname=full)
    await state.set_state(Quest.vk_id)
    await m.answer(LORE_REG, parse_mode="HTML")
    await m.answer("Оставь отметку ВКонтакте:\nссылку (vk.com/…), ID (например id123456789) или короткое имя страницы.")

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
    await save(m.from_user.id, email=email)
    await state.set_state(Quest.riddle)
    await state.set_data({"r": 0})
    await m.answer("✅ Реестр подписан. Двери Архива скрипят и открываются…")
    await asyncio.sleep(PAUSE)
    await send_img(m.from_user.id, IMG_TASKS[1])
    await m.answer("🕯 <b>Дело №1: «Тень на таблицах»</b>\n"
                   "Один студент оставил незакрытый конспект — и теперь цифры шепчут по ночам.\n\n"
                   + RIDDLES[0][0], parse_mode="HTML")

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
            await send_img(m.from_user.id, IMG_TASKS[2])
            await m.answer("🕯 <b>Дело №2: «Мусор, который не призрак»</b>\n"
                           "На чердаке Архива завёлся призрак. Присмотрись: это не призрак —\n"
                           "это пластиковая бутылка 1997 года, которую забыли рассортировать.\n"
                           "Разберём чердак!\n\n"
                           f"Куда отправить: <b>{SORT_ITEMS[0][0]}</b>?",
                           reply_markup=SORT_KB, parse_mode="HTML")
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
    await send_img(c.from_user.id, IMG_TASKS[3])
    await c.message.answer(L3_CHOICE_TEXT, reply_markup=L3_KB, parse_mode="HTML")

@dp.callback_query(Quest.sort_bonus_q)
async def bonus_wrong(c: CallbackQuery):
    await c.answer("❌ Не то. Цифра — это материал, из которого сделан пластик.",
                   show_alert=False)
    await c.message.answer("❌ Тень качает головой. Попробуй другую кнопку.")

# ============================================================
#  УРОВЕНЬ 3. Волонтёрство
# ============================================================

@dp.message(Quest.l3_choice)
async def l3_choice(m: Message, state: FSMContext):
    await m.answer("Выбери путь кнопкой под сообщением 🔘")

@dp.callback_query(Quest.l3_choice, F.data == "l3_task")
async def l3_task_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Quest.l3_task)
    await c.message.edit_text(
        "Открой мини-приложение «Другого Дела», раздел «Волонтёрство»,\n"
        f"и найди задание «{SECRET_TASK_NAME}».\n"
        "Выполни его — баллы платформа начислит на почту из реестра.\n\n"
        "А в описании задания Тень спрятала шифр: строка чисел через дефис.\n"
        "Каждое число — номер буквы в русском алфавите\n"
        "(считая Ё: А — 1, Я — 33). Расшифруй слово и пришли его мне.")

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
        await send_img(m.from_user.id, IMG_TASKS[4])
        await m.answer(L4_CHOICE_TEXT, reply_markup=L4_KB, parse_mode="HTML")
    else:
        await wrong(m, state,
                    "Каждое число — номер буквы алфавита (с Ё). Открой описание задания «Ночной переписчик».",
                    f"числа из описания: {CIPHER_LINE} — это слово НОЧЬ")

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
        await send_img(m.from_user.id, IMG_TASKS[4])
        await m.answer(L4_CHOICE_TEXT, reply_markup=L4_KB, parse_mode="HTML")
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
    await send_img(c.from_user.id, IMG_TASKS[5])
    await c.message.answer("🕯 <b>Дело №5: «Зеркало без отражения»</b>\n" + L5_MAZE_TEXT,
                           parse_mode="HTML")

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
        await send_img(m.from_user.id, IMG_TASKS[5])
        await m.answer("🕯 <b>Дело №5: «Зеркало без отражения»</b>\n" + L5_MAZE_TEXT,
                       parse_mode="HTML")
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
        await send_img(m.from_user.id, IMG_TASKS[5])
        await m.answer("🕯 <b>Дело №5: «Зеркало без отражения»</b>\n" + L5_MAZE_TEXT,
                       parse_mode="HTML")
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
        await send_img(m.from_user.id, IMG_FINAL)
        await m.answer("Введи все пять кодовых слов одной строкой, через пробел,\n"
                       "в порядке дел 1–5.")
    else:
        await wrong(m, state, "Из 8:30 вычти дорогу, сборы и запас.", "07:10")

# ============================================================
#  АДМИН-КОМАНДЫ (зарегистрированы ДО финальных обработчиков,
#  чтобы команды доходимы в любом состоянии, включая Quest.done)
# ============================================================

ADMIN_HELP = (
    "🛠 Команды Хранителя:\n"
    "/stats — сводка по участникам\n"
    "/export — выгрузка итогов CSV-файлом\n"
    "/reset <id_игрока> — сброс прогресса игрока\n"
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
        w.writerow(["Telegram ID", "Имя Фамилия", "VK", "Почта", "Дело №", "Огоньки", "Коды"])
        for uid, nick, vk, email, lvl, sparks, codes in rows:
            w.writerow([uid, nick, vk or "", email or "", max(lvl, 1),
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
        await db.execute("""UPDATE players SET level=0, sparks=0, codes='',
                            l3_names='', code_l3=NULL WHERE user_id=?""", (uid,))
        await db.commit()
    try:
        key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await dp.storage.set_state(key, state=None)
        await dp.storage.set_data(key, {})
    except Exception:
        pass
    await m.answer(f"Прогресс «{row[0]}» стёрт. Архив забыл — и снова ждёт.\n"
                   "Напиши /start — двери откроются заново.")

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
#  ФИНАЛ
# ============================================================

@dp.message(Quest.final)
async def final(m: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT nickname, sparks, code_l3 FROM players WHERE user_id=?", (m.from_user.id,))
        row = await cur.fetchone()
    nick, sparks, code_l3 = row if row else ("Ночной Секретарь", 0, None)
    expected = norm(" ".join(CODES))
    said = norm(m.text)
    # Страховка для старых записей: третий код мог сохраниться как год звонка
    ok = said == expected
    if not ok and code_l3:
        alt = norm(" ".join(CODES[:2] + [str(code_l3)] + CODES[3:]))
        ok = said == alt
    if ok:
        await state.set_state(Quest.done)
        await m.answer(LORE_FINAL.format(nick=nick), parse_mode="HTML")
        await m.answer("Отправь сертификат в мини-приложение «Другого Дела» —\n"
                       "там тебе зачтут задание и начислят баллы на почту из реестра.")
        await send_cert(m.from_user.id, nick, sparks)
    else:
        await wrong(m, state, "Пять слов, по одному с каждого уровня, в порядке дел 1–5.",
                    "коды уровней в порядке 1–5 через пробел")

@dp.message(Quest.done)
async def done(m: Message):
    await m.answer(random.choice([
        "Архив закрыт. Хранитель полирует лампу и улыбается 🕯",
        "Тени впервые за год спят спокойно. Спасибо, Секретарь.",
        "Ты уже всё закрыл. Отдыхай — дело доведено до конца."]))

# ============================================================
#  СЕРТИФИКАТ (фон-картинка + рамка, без кодовых слов)
# ============================================================

def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.registerFont(TTFont(
            "DVS", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont(
            "DVS-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        return "DVS", "DVS-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"

def make_cert(uid, nick, sparks):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from datetime import date
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря"]
    t = date.today()
    date_str = f"{t.day} {months[t.month-1]} {t.year}"
    path = f"cert_{uid}.pdf"
    PW, PH = 595, 842
    GOLD = HexColor("#d9a441")
    CREAM = HexColor("#f3e9d2")
    c = canvas.Canvas(path, pagesize=(PW, PH))
    # Фон: картинка Архива с Мией; нет файла — тёмная заливка
    try:
        c.drawImage("img_cert_bg.png", 0, 0, PW, PH,
                    preserveAspectRatio=True, anchor='c', mask='auto')
    except Exception:
        c.setFillColor(HexColor("#1a1030"))
        c.rect(0, 0, PW, PH, fill=1, stroke=0)
    # Затемнение верхней зоны под текст
    c.setFillColor(HexColor("#0c0720"))
    c.setFillAlpha(0.28)
    c.rect(0, PH - 340, PW, 340, fill=1, stroke=0)
    c.setFillAlpha(1)
    # Двойная золотая рамка с ромбами по углам
    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.rect(28, 28, PW - 56, PH - 56)
    c.setLineWidth(1)
    c.rect(38, 38, PW - 76, PH - 76)

    def diamond(x, y, r=7):
        c.setFillColor(GOLD)
        p = c.beginPath()
        p.moveTo(x, y + r); p.lineTo(x + r, y)
        p.lineTo(x, y - r); p.lineTo(x - r, y); p.close()
        c.drawPath(p, fill=1, stroke=0)

    for x, y in [(28, 28), (PW - 28, 28), (28, PH - 28), (PW - 28, PH - 28),
                 (38, 38), (PW - 38, 38), (38, PH - 38), (PW - 38, PH - 38)]:
        diamond(x, y)

    font, font_b = _register_fonts()
    c.setFillColor(GOLD)
    c.setFont(font_b, 34)
    c.drawCentredString(PW / 2, PH - 120, "СЕРТИФИКАТ")
    c.setFont(font, 20)
    c.drawCentredString(PW / 2, PH - 152, "Ночного Секретаря")
    c.setLineWidth(1.4)
    c.line(PW / 2 - 130, PH - 170, PW / 2 + 130, PH - 170)
    diamond(PW / 2, PH - 170, 5)
    c.setFillColor(CREAM)
    c.setFont(font_b, 26)
    c.drawCentredString(PW / 2, PH - 240, nick)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(PW / 2 - 150, PH - 256, PW / 2 + 150, PH - 256)
    c.setFillColor(HexColor("#cfc4a8"))
    c.setFont(font, 12)
    c.drawCentredString(PW / 2, PH - 276, "довел(а) все дела Архива до конца")
    # Пять огоньков (без слов — ответы не светятся)
    n, span = 5, 60
    x0 = PW / 2 - span * (n - 1) / 2
    y0 = PH - 420
    c.setFillColor(HexColor("#ffb347"))
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    for i in range(n):
        cx = x0 + i * span
        c.circle(cx, y0, 16, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(cx, y0 + 12)
        p.curveTo(cx + 8, y0 + 4, cx + 7, y0 - 8, cx, y0 - 11)
        p.curveTo(cx - 7, y0 - 8, cx - 8, y0 + 4, cx, y0 + 12)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(CREAM)
    c.setFont(font, 13)
    c.drawCentredString(PW / 2, y0 - 40, f"{sparks} огоньков за закрытые дела")
    c.setFont(font, 12)
    c.drawCentredString(PW / 2, y0 - 66, "квест «Другая Сторона Дела» — проект «Другое Дело»")
    c.setFillColor(HexColor("#cfc4a8"))
    c.setFont(font, 12)
    c.drawCentredString(PW / 2, 150, "Хранитель Архива Ночных Дел")
    c.setFont(font, 11)
    c.drawCentredString(PW / 2, 128, date_str)
    c.setFillColor(GOLD)
    c.setFont(font, 11)
    c.drawCentredString(PW / 2, 70, "«Дело, доведённое до конца, не боится темноты»")
    c.save()
    return path

async def send_cert(uid, nick, sparks):
    try:
        await bot.send_document(uid, FSInputFile(make_cert(uid, nick, sparks)))
    except Exception:
        await bot.send_message(uid, f"Сертификат Ночного Секретаря: {nick}, {sparks} огоньков 🕯")

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
                        "🕯 Одна Тень уже проснулась. Не заставляй ждать остальных."]))
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
