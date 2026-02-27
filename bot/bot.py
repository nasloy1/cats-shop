#!/usr/bin/env python3
"""
Telegram Bot для магазина котов.
Запускает HTTP-сервер (aiohttp) для приёма заказов из Mini App
И Telegram Bot polling — одновременно.
"""

import os
import asyncio
import logging
import aiosqlite
from datetime import datetime

from aiohttp import web
from dotenv import load_dotenv
from telegram import (
    Update, WebAppInfo,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, filters, ContextTypes,
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ──────────────── Конфигурация ────────────────
BOT_TOKEN     = os.getenv('BOT_TOKEN', '')
MINI_APP_URL  = os.getenv('MINI_APP_URL', '')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')  # основной (для уведомлений о заказах)
ADMIN_IDS     = set(i.strip() for i in ADMIN_CHAT_ID.split(',') if i.strip())
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID', '')
API_SECRET    = os.getenv('API_SECRET', 'cats-shop-secret')
PORT          = int(os.getenv('PORT', 8080))
DB_PATH       = os.getenv('DB_PATH', 'cats.db')
PUBLIC_URL    = os.getenv('PUBLIC_URL', '').rstrip('/')   # https://cats-shop-production.up.railway.app
PHOTOS_DIR    = os.getenv('PHOTOS_DIR', 'photos')

# Глобальная ссылка на бота
_bot = None

# ──────────────── ConversationHandler states ────────────────
ADD_NAME, ADD_BREED, ADD_AGE, ADD_GENDER, ADD_PRICE, ADD_COLOR, ADD_DESC, ADD_PHOTO = range(8)

# ──────────────── Начальные данные для БД ────────────────
SEED_CATS = [
    {
        'name': 'Амур', 'breed': 'Донской сфинкс', 'age_months': 3, 'gender': 'male',
        'price': 35000, 'color': 'Розово-персиковый',
        'description': 'Обаятельный котёнок с тёплой бархатистой кожей и огромными выразительными глазами. Невероятно ласковый и общительный — обожает сидеть на руках и мурлыкать. Идеально подходит для семей с детьми. Привит, обработан от паразитов, ветпаспорт и родословная WCF.',
        'image': 'https://kot.pet/images/parent-1.jpg', 'available': True,
    },
    {
        'name': 'Василиса', 'breed': 'Донской сфинкс', 'age_months': 4, 'gender': 'female',
        'price': 38000, 'color': 'Кремово-розовый',
        'description': 'Нежная и утончённая кошечка с шёлковистой тёплой кожей. Интерчемпион по стандартам WCF. Ласковая, любит внимание, отлично уживается с другими питомцами. Гипоаллергенная порода — идеальна для людей с аллергией. Полный пакет документов.',
        'image': 'https://kot.pet/images/parent-2.jpg', 'available': True,
    },
    {
        'name': 'Леон', 'breed': 'Донской сфинкс', 'age_months': 5, 'gender': 'male',
        'price': 42000, 'color': 'Загорелый',
        'description': 'Статный кот с гордой осанкой и добрым сердцем. Чемпион WCF с отличной родословной. Несмотря на величественный вид — невероятно нежен с хозяевами. Любит греться на руках и смотреть в окно. Все прививки, ветпаспорт международного образца.',
        'image': 'https://kot.pet/images/parent-3.jpg', 'available': True,
    },
    {
        'name': 'Злата', 'breed': 'Донской сфинкс', 'age_months': 3, 'gender': 'female',
        'price': 45000, 'color': 'Золотистый',
        'description': 'Очаровательная гранд-чемпионка с золотистым оттенком кожи и умным взглядом. Игривая и энергичная, обожает интерактивные игрушки. Донские сфинксы не линяют — никакой шерсти на одежде! Родословная, ветпаспорт WCF.',
        'image': 'https://kot.pet/images/parent-4.jpg', 'available': True,
    },
    {
        'name': 'Барсик', 'breed': 'Донской сфинкс', 'age_months': 2, 'gender': 'male',
        'price': 28000, 'color': 'Розовый',
        'description': 'Милый малыш с большими ушами и бесконечным любопытством. Вырастет в спокойного и преданного компаньона. Тепло его кожи греет лучше любого пледа. Крепкое здоровье, все документы в порядке.',
        'image': 'https://kot.pet/images/review-1-kitten.jpg', 'available': True,
    },
    {
        'name': 'Луна', 'breed': 'Донской сфинкс', 'age_months': 4, 'gender': 'female',
        'price': 32000, 'color': 'Серебристо-розовый',
        'description': 'Нежная лунная принцесса уже нашла свой дом. Если вас интересует похожий котёнок — напишите нам через форму обратной связи, и мы подберём идеального питомца специально для вас!',
        'image': 'https://kot.pet/images/review-2-kitten.jpg', 'available': False,
    },
    {
        'name': 'Милан', 'breed': 'Донской сфинкс', 'age_months': 3, 'gender': 'male',
        'price': 36000, 'color': 'Тёмно-персиковый',
        'description': 'Итальянское имя — итальянский темперамент! Обожает общество людей и никогда не откажется от ласки. Активный и весёлый, превращает каждый день в праздник. Подходит для квартиры любого размера. Привит, документы WCF.',
        'image': 'https://kot.pet/images/review-3-kitten.jpg', 'available': True,
    },
    {
        'name': 'Афина', 'breed': 'Донской сфинкс', 'age_months': 5, 'gender': 'female',
        'price': 40000, 'color': 'Розово-бежевый',
        'description': 'Богиня домашнего уюта с умным взглядом и грациозными движениями. Необычайно интеллектуальна — быстро учит команды, понимает интонации хозяина. Тепло её кожи заменяет грелку в зимние вечера. Международный ветпаспорт, прививки.',
        'image': 'https://kot.pet/images/hero-cat.jpg', 'available': True,
    },
    {
        'name': 'Зефир', 'breed': 'Донской сфинкс', 'age_months': 2, 'gender': 'male',
        'price': 26000, 'color': 'Кремово-белый',
        'description': 'Воздушный и нежный, как его имя. Самый молодой котёнок питомника — полон жизни и игривости. Большие уши-локаторы и бесконечное мурчание. Донские сфинксы не линяют — идеально для чистоплотных хозяев!',
        'image': 'https://kot.pet/images/parent-1.jpg', 'available': True,
    },
    {
        'name': 'Диана', 'breed': 'Донской сфинкс', 'age_months': 6, 'gender': 'female',
        'price': 43000, 'color': 'Персиково-золотой',
        'description': 'В 6 месяцев Диана уже освоила несколько трюков и знает своё имя. Нежная, контактная, легко привыкает к новому дому. Отличный выбор для тех, кто хочет активного и преданного питомца. Ветпаспорт, прививки.',
        'image': 'https://kot.pet/images/parent-2.jpg', 'available': True,
    },
    {
        'name': 'Граф', 'breed': 'Донской сфинкс', 'age_months': 4, 'gender': 'male',
        'price': 39000, 'color': 'Тёмно-коричневый',
        'description': 'Аристократ по происхождению и характеру. Держится с достоинством, но в кругу семьи — нежный и преданный. Любит дремать на тёплом месте рядом с хозяином. Полная родословная, чемпионские предки.',
        'image': 'https://kot.pet/images/parent-3.jpg', 'available': True,
    },
    {
        'name': 'Рица', 'breed': 'Донской сфинкс', 'age_months': 3, 'gender': 'female',
        'price': 37000, 'color': 'Розово-лиловый',
        'description': 'Названа в честь горного озера — такая же чистая и прекрасная. Не боится купания — редкое качество для кошек! Добрый и открытый характер, быстро находит общий язык с детьми и другими животными. Ветпаспорт, родословная WCF.',
        'image': 'https://kot.pet/images/parent-4.jpg', 'available': True,
    },
]


# ──────────────── База данных ────────────────
async def init_db():
    """Инициализирует таблицу cats и заполняет начальными данными если пустая."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS cats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                breed       TEXT    NOT NULL DEFAULT 'Донской сфинкс',
                age_months  INTEGER NOT NULL DEFAULT 3,
                gender      TEXT    NOT NULL DEFAULT 'male',
                price       INTEGER NOT NULL,
                color       TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                image       TEXT    NOT NULL DEFAULT '',
                available   INTEGER NOT NULL DEFAULT 1
            )
        ''')
        cursor = await db.execute('SELECT COUNT(*) FROM cats')
        count = (await cursor.fetchone())[0]
        if count == 0:
            for cat in SEED_CATS:
                await db.execute(
                    'INSERT INTO cats (name,breed,age_months,gender,price,color,description,image,available) '
                    'VALUES (?,?,?,?,?,?,?,?,?)',
                    (cat['name'], cat['breed'], cat['age_months'], cat['gender'],
                     cat['price'], cat['color'], cat['description'], cat['image'],
                     1 if cat['available'] else 0),
                )
        await db.commit()
    logger.info('БД инициализирована: %s', DB_PATH)


async def db_get_cats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM cats ORDER BY id')
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def db_add_cat(name, breed, age_months, gender, price, color, description, image):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO cats (name,breed,age_months,gender,price,color,description,image,available) '
            'VALUES (?,?,?,?,?,?,?,?,1)',
            (name, breed, age_months, gender, price, color, description, image),
        )
        new_id = cursor.lastrowid
        await db.commit()
    return new_id


async def db_remove_cat(cat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM cats WHERE id=?', (cat_id,))
        await db.commit()


async def db_set_available(cat_id, available: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE cats SET available=? WHERE id=?',
                         (1 if available else 0, cat_id))
        await db.commit()


# ──────────────── CORS helpers ───────────────
def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Secret',
    }


async def handle_options(request):
    return web.Response(status=200, headers=cors_headers())


# ──────────────── HTTP: /health ───────────────
async def handle_health(request):
    return web.json_response({'ok': True, 'status': 'running'})


# ──────────────── HTTP: /photos/{filename} ───
async def handle_photo_file(request):
    filename = request.match_info['filename']
    if '/' in filename or '..' in filename:
        raise web.HTTPForbidden()
    filepath = os.path.join(PHOTOS_DIR, filename)
    if not os.path.isfile(filepath):
        raise web.HTTPNotFound()
    return web.FileResponse(filepath)


# ──────────────── HTTP: /cats ─────────────────
async def handle_cats(request):
    cats = await db_get_cats()
    result = []
    for c in cats:
        result.append({
            'id':          c['id'],
            'name':        c['name'],
            'breed':       c['breed'],
            'age_months':  c['age_months'],
            'gender':      c['gender'],
            'category':    c['gender'],   # для фильтра на фронте
            'price':       c['price'],
            'color':       c['color'],
            'description': c['description'],
            'image':       c['image'],
            'available':   bool(c['available']),
            'vaccinated':  True,
            'pedigree':    True,
        })
    return web.json_response(result, headers=cors_headers())


# ──────────────── HTTP: /order ────────────────
async def handle_order(request):
    if request.headers.get('X-Secret') != API_SECRET:
        return web.json_response(
            {'ok': False, 'error': 'Unauthorized'},
            status=401, headers=cors_headers(),
        )
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400, headers=cors_headers(),
        )

    items     = data.get('items', [])
    total     = data.get('total', 0)
    now       = datetime.now().strftime('%d.%m.%Y %H:%M')
    total_str = '{:,}'.format(total).replace(',', ' ')

    lines = [
        '🛍️ <b>НОВЫЙ ЗАКАЗ!</b>',
        '━' * 22,
        '👤 <b>Имя:</b> {}'.format(data.get('name', '—')),
        '📞 <b>Телефон:</b> {}'.format(data.get('phone', '—')),
    ]
    if data.get('address'):
        lines.append('📍 <b>Адрес:</b> {}'.format(data['address']))
    if data.get('comment'):
        lines.append('💬 <b>Комментарий:</b> {}'.format(data['comment']))

    lines.append('\n🐱 <b>Котята ({}):</b>'.format(len(items)))
    for item in items:
        price_str = '{:,}'.format(item['price']).replace(',', ' ')
        lines.append('  • {} ({}) — {} ₽'.format(item['name'], item['breed'], price_str))

    lines += [
        '',
        '💰 <b>Итого: {} ₽</b>'.format(total_str),
        '━' * 22,
        '🕐 {}'.format(now),
    ]
    msg = '\n'.join(lines)

    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await _bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
        except Exception as exc:
            logger.error('Ошибка отправки в %s: %s', chat_id, exc)

    return web.json_response({'ok': True}, headers=cors_headers())


# ──────────────── HTTP: /feedback ─────────────
async def handle_feedback(request):
    if request.headers.get('X-Secret') != API_SECRET:
        return web.json_response(
            {'ok': False, 'error': 'Unauthorized'},
            status=401, headers=cors_headers(),
        )
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400, headers=cors_headers(),
        )

    now = datetime.now().strftime('%d.%m.%Y %H:%M')
    lines = [
        '💬 <b>ОБРАТНАЯ СВЯЗЬ</b>',
        '━' * 22,
        '👤 <b>Имя:</b> {}'.format(data.get('name', '—')),
    ]
    if data.get('contact'):
        lines.append('📞 <b>Контакт:</b> {}'.format(data['contact']))
    lines += [
        '📋 <b>Тема:</b> {}'.format(data.get('subject', '—')),
        '',
        '✉️ <b>Сообщение:</b>',
        data.get('message', '—'),
        '━' * 22,
        '🕐 {}'.format(now),
    ]
    msg = '\n'.join(lines)

    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await _bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
        except Exception as exc:
            logger.error('Ошибка отправки в %s: %s', chat_id, exc)

    return web.json_response({'ok': True}, headers=cors_headers())


# ──────────────── Bot helpers ─────────────────
def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) in ADMIN_IDS


# ──────────────── Bot: /start ─────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[
        KeyboardButton('🐱 Открыть магазин котов', web_app=WebAppInfo(url=MINI_APP_URL))
    ]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Привет, {}! 👋\n\n'
        '🐾 Добро пожаловать в питомник <b>«Мурлыка»</b>!\n\n'
        'Донские сфинксы — тёплые, гипоаллергенные и невероятно ласковые.\n\n'
        'Нажмите кнопку ниже, чтобы открыть каталог:'.format(user.first_name),
        reply_markup=markup,
        parse_mode='HTML',
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        '🐱 <b>Питомник «Мурлыка»</b>\n\n'
        '/start — Открыть магазин\n'
        '/help — Справка'
    )
    if is_admin(update):
        text += (
            '\n\n<b>👑 Управление каталогом:</b>\n'
            '/listcats — Список всех котят\n'
            '/addcat — Добавить котёнка\n'
            '/soldcat &lt;id&gt; — Отметить как проданного\n'
            '/availcat &lt;id&gt; — Отметить как доступного\n'
            '/removecat &lt;id&gt; — Удалить котёнка из каталога'
        )
    await update.message.reply_text(text, parse_mode='HTML')


# ──────────────── Admin: /listcats ────────────
async def cmd_listcats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text('Команда недоступна.')
        return

    cats = await db_get_cats()
    if not cats:
        await update.message.reply_text('Каталог пуст.')
        return

    lines = ['📋 <b>Каталог котят:</b>\n']
    for c in cats:
        status = '✅' if c['available'] else '❌'
        price_str = '{:,}'.format(c['price']).replace(',', ' ')
        lines.append('{} <b>#{}</b> {} — {} ₽ | {} мес. | {}'.format(
            status, c['id'], c['name'], price_str,
            c['age_months'], '♂' if c['gender'] == 'male' else '♀',
        ))

    lines.append('\n<i>/soldcat &lt;id&gt; — продан | /availcat &lt;id&gt; — доступен | /removecat &lt;id&gt; — удалить</i>')
    await update.message.reply_text('\n'.join(lines), parse_mode='HTML')


# ──────────────── Admin: /soldcat, /availcat, /removecat ──
async def cmd_soldcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text('Команда недоступна.')
        return
    if not context.args:
        await update.message.reply_text('Использование: /soldcat <id>')
        return
    try:
        cat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text('ID должен быть числом.')
        return
    await db_set_available(cat_id, False)
    await update.message.reply_text('✅ Котёнок #{} отмечен как проданный.'.format(cat_id))


async def cmd_availcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text('Команда недоступна.')
        return
    if not context.args:
        await update.message.reply_text('Использование: /availcat <id>')
        return
    try:
        cat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text('ID должен быть числом.')
        return
    await db_set_available(cat_id, True)
    await update.message.reply_text('✅ Котёнок #{} снова доступен.'.format(cat_id))


async def cmd_removecat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text('Команда недоступна.')
        return
    if not context.args:
        await update.message.reply_text('Использование: /removecat <id>')
        return
    try:
        cat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text('ID должен быть числом.')
        return
    await db_remove_cat(cat_id)
    await update.message.reply_text('🗑️ Котёнок #{} удалён из каталога.'.format(cat_id))


# ──────────────── Admin: /addcat (диалог) ────────────────
async def addcat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text('Команда недоступна.')
        return ConversationHandler.END

    context.user_data['new_cat'] = {}
    await update.message.reply_text(
        '🐱 <b>Добавление котёнка — шаг 1/8</b>\n\n'
        'Введите <b>имя</b> котёнка:\n\n'
        '<i>Напишите /cancel для отмены</i>',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADD_NAME


async def addcat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_cat']['name'] = update.message.text.strip()
    await update.message.reply_text(
        '<b>Шаг 2/8</b> — Введите <b>породу</b>\n\n'
        'Или отправьте <b>.</b> чтобы использовать «Донской сфинкс»',
        parse_mode='HTML',
    )
    return ADD_BREED


async def addcat_breed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['new_cat']['breed'] = text if text != '.' else 'Донской сфинкс'
    await update.message.reply_text(
        '<b>Шаг 3/8</b> — Введите <b>возраст в месяцах</b> (например: 3)',
        parse_mode='HTML',
    )
    return ADD_AGE


async def addcat_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text('Введите число месяцев (например: 3):')
        return ADD_AGE

    context.user_data['new_cat']['age_months'] = age
    keyboard = [['♂ Кот', '♀ Кошка']]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        '<b>Шаг 4/8</b> — Выберите <b>пол</b>:',
        parse_mode='HTML',
        reply_markup=markup,
    )
    return ADD_GENDER


async def addcat_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['new_cat']['gender'] = 'female' if '♀' in text or 'Кошка' in text else 'male'
    await update.message.reply_text(
        '<b>Шаг 5/8</b> — Введите <b>цену</b> в рублях (например: 35000):',
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADD_PRICE


async def addcat_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.strip().replace(' ', '').replace(',', ''))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text('Введите цену числом (например: 35000):')
        return ADD_PRICE

    context.user_data['new_cat']['price'] = price
    await update.message.reply_text(
        '<b>Шаг 6/8</b> — Введите <b>окрас/цвет</b> (например: Розово-персиковый):',
        parse_mode='HTML',
    )
    return ADD_COLOR


async def addcat_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_cat']['color'] = update.message.text.strip()
    await update.message.reply_text(
        '<b>Шаг 7/8</b> — Введите <b>описание</b> котёнка:',
        parse_mode='HTML',
    )
    return ADD_DESC


async def addcat_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_cat']['description'] = update.message.text.strip()
    await update.message.reply_text(
        '<b>Шаг 8/8</b> — Отправьте <b>фото</b> котёнка 📷\n\n'
        'Или вставьте ссылку на фото (URL)\n'
        'Или напишите <b>.</b> чтобы пропустить.',
        parse_mode='HTML',
    )
    return ADD_PHOTO


async def addcat_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        # Пользователь отправил фото — скачиваем и сохраняем
        tg_photo = update.message.photo[-1]   # берём максимальный размер
        tg_file  = await context.bot.get_file(tg_photo.file_id)
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        filename = '{}.jpg'.format(tg_photo.file_unique_id)
        await tg_file.download_to_drive(os.path.join(PHOTOS_DIR, filename))
        image = '{}/photos/{}'.format(PUBLIC_URL, filename) if PUBLIC_URL else ''
    else:
        text  = update.message.text.strip()
        image = text if text != '.' else ''

    cat = context.user_data['new_cat']
    cat['image'] = image

    price_str  = '{:,}'.format(cat['price']).replace(',', ' ')
    gender_str = '♂ Кот' if cat['gender'] == 'male' else '♀ Кошка'

    new_id = await db_add_cat(
        cat['name'], cat['breed'], cat['age_months'], cat['gender'],
        cat['price'], cat['color'], cat['description'], image,
    )

    await update.message.reply_text(
        '✅ <b>Котёнок добавлен в каталог! ID: #{}</b>\n\n'
        '<b>Имя:</b> {name}\n'
        '<b>Порода:</b> {breed}\n'
        '<b>Возраст:</b> {age} мес.\n'
        '<b>Пол:</b> {gender}\n'
        '<b>Цена:</b> {price} ₽\n'
        '<b>Окрас:</b> {color}\n'
        '<b>Фото:</b> {image}'.format(
            new_id,
            name=cat['name'], breed=cat['breed'], age=cat['age_months'],
            gender=gender_str, price=price_str, color=cat['color'],
            image=image if image else '(не указано)',
        ),
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.pop('new_cat', None)
    return ConversationHandler.END


async def addcat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('new_cat', None)
    await update.message.reply_text('Добавление отменено.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ──────────────── Запуск ─────────────────────
async def run():
    global _bot

    if not BOT_TOKEN:
        print('ОШИБКА: BOT_TOKEN не задан!')
        return

    # Инициализируем БД
    await init_db()

    # ── Telegram bot ──
    tg_app = Application.builder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler('start',     cmd_start))
    tg_app.add_handler(CommandHandler('help',      cmd_help))
    tg_app.add_handler(CommandHandler('listcats',  cmd_listcats))
    tg_app.add_handler(CommandHandler('soldcat',   cmd_soldcat))
    tg_app.add_handler(CommandHandler('availcat',  cmd_availcat))
    tg_app.add_handler(CommandHandler('removecat', cmd_removecat))

    addcat_handler = ConversationHandler(
        entry_points=[CommandHandler('addcat', addcat_start)],
        states={
            ADD_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_name)],
            ADD_BREED:  [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_breed)],
            ADD_AGE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_age)],
            ADD_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_gender)],
            ADD_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_price)],
            ADD_COLOR:  [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_color)],
            ADD_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_desc)],
            ADD_PHOTO:  [
                MessageHandler(filters.PHOTO, addcat_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, addcat_photo),
            ],
        },
        fallbacks=[CommandHandler('cancel', addcat_cancel)],
        allow_reentry=True,
    )
    tg_app.add_handler(addcat_handler)

    _bot = tg_app.bot

    # ── HTTP server ──
    http_app = web.Application()
    http_app.router.add_get('/health',             handle_health)
    http_app.router.add_get('/cats',               handle_cats)
    http_app.router.add_get('/photos/{filename}',  handle_photo_file)
    http_app.router.add_post('/order',    handle_order)
    http_app.router.add_post('/feedback', handle_feedback)
    http_app.router.add_route('OPTIONS', '/cats',     handle_options)
    http_app.router.add_route('OPTIONS', '/order',    handle_options)
    http_app.router.add_route('OPTIONS', '/feedback', handle_options)

    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info('HTTP сервер запущен на порту %d', PORT)

    # ── Start polling ──
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info('Бот запущен!')
    logger.info('Mini App URL: %s', MINI_APP_URL)

    try:
        await asyncio.Event().wait()
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(run())
