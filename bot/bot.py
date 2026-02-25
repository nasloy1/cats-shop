#!/usr/bin/env python3
"""
Telegram Bot для магазина котов
Получает заказы и обратную связь из Mini App,
уведомляет администратора.
"""

import os
import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from telegram import (
    Update,
    WebAppInfo,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
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
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID', '')  # ID группы Telegram для уведомлений


# ──────────────── /start ─────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Кнопка для открытия Mini App
    keyboard = [[
        KeyboardButton(
            '🐱 Открыть магазин котов',
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
    ]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f'Привет, {user.first_name}! 👋\n\n'
        '🐾 Добро пожаловать в питомник <b>«Мурлыка»</b>!\n\n'
        'У нас есть котята лучших пород:\n'
        '• Британские 🇬🇧\n'
        '• Персидские 👑\n'
        '• Мейн-куны 🦁\n'
        '• Шотландские 🏴󠁧󠁢󠁳󠁣󠁴󠁿\n'
        '• Рэгдоллы 💙\n'
        '• Сибирские ❄️\n\n'
        'Нажмите кнопку ниже, чтобы открыть каталог:',
        reply_markup=markup,
        parse_mode='HTML',
    )


# ──────────────── /help ──────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '🐱 <b>Питомник «Мурлыка»</b> — помощь\n\n'
        '/start — Открыть магазин\n'
        '/catalog — Краткий список котов\n'
        '/help — Эта справка\n\n'
        'По всем вопросам используйте форму обратной связи в приложении.',
        parse_mode='HTML',
    )


# ──────────────── /catalog ───────────────────
async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton(
            '🐱 Открыть каталог',
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
    ]]
    await update.message.reply_text(
        '📋 Нажмите кнопку ниже, чтобы просмотреть каталог котят:',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ──────────────── Web App Data ───────────────
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные, отправленные из Mini App через sendData()"""
    user = update.effective_user
    raw  = update.message.web_app_data.data

    logger.info(f'WebApp data from {user.id}: {raw[:200]}')

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f'Invalid JSON: {raw}')
        await update.message.reply_text('❌ Ошибка обработки данных.')
        return

    data_type = data.get('type')

    if data_type == 'order':
        await process_order(update, context, data, user)
    elif data_type == 'feedback':
        await process_feedback(update, context, data, user)
    else:
        logger.warning(f'Unknown data type: {data_type}')


async def process_order(update, context, data, user):
    """Обработка нового заказа"""
    items = data.get('items', [])
    total = data.get('total', 0)
    now   = datetime.now().strftime('%d.%m.%Y %H:%M')

    # ── Сообщение для администратора
    admin_lines = [
        '🛍️ <b>НОВЫЙ ЗАКАЗ!</b>',
        '━' * 24,
        f'👤 <b>Имя:</b> {data.get("name", "—")}',
        f'📞 <b>Телефон:</b> {data.get("phone", "—")}',
    ]
    if data.get('address'):
        admin_lines.append(f'📍 <b>Адрес:</b> {data["address"]}')
    if data.get('comment'):
        admin_lines.append(f'💬 <b>Комментарий:</b> {data["comment"]}')

    admin_lines.append('')
    admin_lines.append(f'🐱 <b>Котята ({len(items)}):</b>')
    for item in items:
        price_str = f'{item["price"]:,}'.replace(',', ' ')
        admin_lines.append(f'  • {item["name"]} ({item["breed"]}) — {price_str} ₽')

    total_str = f'{total:,}'.replace(',', ' ')
    admin_lines += [
        '',
        f'💰 <b>Итого: {total_str} ₽</b>',
        '━' * 24,
        f'👤 Telegram: {user.mention_html()}',
        f'🕐 {now}',
    ]
    admin_msg = '\n'.join(admin_lines)

    # Отправляем администратору и в группу
    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=admin_msg,
                parse_mode='HTML',
            )
        except Exception as exc:
            logger.error(f'Failed to notify {chat_id}: {exc}')

    # ── Подтверждение пользователю
    items_text = '\n'.join(
        '  🐱 {} — {} ₽'.format(i['name'], '{:,}'.format(i['price']).replace(',', ' '))
        for i in items
    )
    await update.message.reply_text(
        '✅ <b>Ваш заказ принят!</b>\n\n'
        f'<b>Котята:</b>\n{items_text}\n\n'
        f'<b>Итого: {total_str} ₽</b>\n\n'
        f'Мы свяжемся с вами по номеру <code>{data.get("phone", "")}</code> '
        'в течение рабочего дня для подтверждения. 🐾',
        parse_mode='HTML',
    )


async def process_feedback(update, context, data, user):
    """Обработка обратной связи"""
    now = datetime.now().strftime('%d.%m.%Y %H:%M')

    admin_lines = [
        '💬 <b>ОБРАТНАЯ СВЯЗЬ</b>',
        '━' * 24,
        f'👤 <b>Имя:</b> {data.get("name", "—")}',
    ]
    if data.get('contact'):
        admin_lines.append(f'📞 <b>Контакт:</b> {data["contact"]}')

    admin_lines += [
        f'📋 <b>Тема:</b> {data.get("subject", "—")}',
        '',
        f'✉️ <b>Сообщение:</b>',
        data.get('message', '—'),
        '━' * 24,
        f'👤 Telegram: {user.mention_html()}',
        f'🕐 {now}',
    ]
    admin_msg = '\n'.join(admin_lines)

    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=admin_msg,
                parse_mode='HTML',
            )
        except Exception as exc:
            logger.error(f'Failed to notify {chat_id}: {exc}')

    await update.message.reply_text(
        '✅ <b>Спасибо за ваше сообщение!</b>\n\n'
        'Мы ответим вам в ближайшее время. 🐾',
        parse_mode='HTML',
    )


# ──────────────── Запуск ─────────────────────
def main():
    if not BOT_TOKEN:
        print('ОШИБКА: Не задан BOT_TOKEN в файле .env!')
        return
    if not MINI_APP_URL:
        print('ПРЕДУПРЕЖДЕНИЕ: MINI_APP_URL не задан — кнопка Mini App не будет работать!')

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start',   cmd_start))
    app.add_handler(CommandHandler('help',    cmd_help))
    app.add_handler(CommandHandler('catalog', cmd_catalog))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.WEB_APP_DATA,
        handle_web_app_data,
    ))

    print('🐱 Cat Shop Bot запущен!')
    print(f'   Mini App URL: {MINI_APP_URL or "(не задан)"}')
    print(f'   Admin Chat:   {ADMIN_CHAT_ID or "(не задан)"}')
    print('   Нажмите Ctrl+C для остановки.\n')

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
