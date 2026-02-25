#!/usr/bin/env python3
"""
Telegram Bot для магазина котов.
Запускает HTTP-сервер (aiohttp) для приёма заказов из Mini App
И Telegram Bot polling — одновременно.
"""

import os
import json
import asyncio
import logging
from datetime import datetime

from aiohttp import web
from dotenv import load_dotenv
from telegram import (
    Update, WebAppInfo,
    KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler,
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
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID', '')
API_SECRET    = os.getenv('API_SECRET', 'cats-shop-secret')
PORT          = int(os.getenv('PORT', 8080))

# Глобальная ссылка на бота (используется в HTTP-обработчиках)
_bot = None


# ──────────────── CORS helpers ───────────────
def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Secret',
    }


async def handle_options(request):
    """Preflight CORS запросы от браузера."""
    return web.Response(status=200, headers=cors_headers())


# ──────────────── HTTP: /health ───────────────
async def handle_health(request):
    return web.json_response({'ok': True, 'status': 'running'})


# ──────────────── HTTP: /order ────────────────
async def handle_order(request):
    if request.headers.get('X-Secret') != API_SECRET:
        return web.json_response(
            {'ok': False, 'error': 'Unauthorized'},
            status=401, headers=cors_headers()
        )

    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400, headers=cors_headers()
        )

    items     = data.get('items', [])
    total     = data.get('total', 0)
    now       = datetime.now().strftime('%d.%m.%Y %H:%M')
    total_str = '{:,}'.format(total).replace(',', ' ')

    lines = [
        '🛍️ <b>НОВЫЙ ЗАКАЗ!</b>',
        '━' * 22,
        f'👤 <b>Имя:</b> {data.get("name", "—")}',
        f'📞 <b>Телефон:</b> {data.get("phone", "—")}',
    ]
    if data.get('address'):
        lines.append(f'📍 <b>Адрес:</b> {data["address"]}')
    if data.get('comment'):
        lines.append(f'💬 <b>Комментарий:</b> {data["comment"]}')

    lines.append(f'\n🐱 <b>Котята ({len(items)}):</b>')
    for item in items:
        price_str = '{:,}'.format(item['price']).replace(',', ' ')
        lines.append(f'  • {item["name"]} ({item["breed"]}) — {price_str} ₽')

    lines += [
        '',
        f'💰 <b>Итого: {total_str} ₽</b>',
        '━' * 22,
        f'🕐 {now}',
    ]
    msg = '\n'.join(lines)

    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await _bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
        except Exception as exc:
            logger.error(f'Ошибка отправки в {chat_id}: {exc}')

    return web.json_response({'ok': True}, headers=cors_headers())


# ──────────────── HTTP: /feedback ─────────────
async def handle_feedback(request):
    if request.headers.get('X-Secret') != API_SECRET:
        return web.json_response(
            {'ok': False, 'error': 'Unauthorized'},
            status=401, headers=cors_headers()
        )

    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {'ok': False, 'error': 'Invalid JSON'},
            status=400, headers=cors_headers()
        )

    now = datetime.now().strftime('%d.%m.%Y %H:%M')

    lines = [
        '💬 <b>ОБРАТНАЯ СВЯЗЬ</b>',
        '━' * 22,
        f'👤 <b>Имя:</b> {data.get("name", "—")}',
    ]
    if data.get('contact'):
        lines.append(f'📞 <b>Контакт:</b> {data["contact"]}')

    lines += [
        f'📋 <b>Тема:</b> {data.get("subject", "—")}',
        '',
        '✉️ <b>Сообщение:</b>',
        data.get('message', '—'),
        '━' * 22,
        f'🕐 {now}',
    ]
    msg = '\n'.join(lines)

    for chat_id in filter(None, [ADMIN_CHAT_ID, GROUP_CHAT_ID]):
        try:
            await _bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
        except Exception as exc:
            logger.error(f'Ошибка отправки в {chat_id}: {exc}')

    return web.json_response({'ok': True}, headers=cors_headers())


# ──────────────── Bot: /start ─────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [[
        KeyboardButton('🐱 Открыть магазин котов', web_app=WebAppInfo(url=MINI_APP_URL))
    ]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f'Привет, {user.first_name}! 👋\n\n'
        '🐾 Добро пожаловать в питомник <b>«Мурлыка»</b>!\n\n'
        'Донские сфинксы — тёплые, гипоаллергенные и невероятно ласковые.\n\n'
        'Нажмите кнопку ниже, чтобы открыть каталог:',
        reply_markup=markup,
        parse_mode='HTML',
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '🐱 <b>Питомник «Мурлыка»</b>\n\n'
        '/start — Открыть магазин\n'
        '/help — Справка',
        parse_mode='HTML',
    )


# ──────────────── Запуск ─────────────────────
async def run():
    global _bot

    if not BOT_TOKEN:
        print('ОШИБКА: BOT_TOKEN не задан!')
        return

    # ── Telegram bot ──
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler('start', cmd_start))
    tg_app.add_handler(CommandHandler('help',  cmd_help))
    _bot = tg_app.bot

    # ── HTTP server ──
    http_app = web.Application()
    http_app.router.add_get('/health', handle_health)
    http_app.router.add_post('/order',    handle_order)
    http_app.router.add_post('/feedback', handle_feedback)
    http_app.router.add_route('OPTIONS', '/order',    handle_options)
    http_app.router.add_route('OPTIONS', '/feedback', handle_options)

    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f'HTTP сервер запущен на порту {PORT}')

    # ── Start polling ──
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info('Бот запущен!')
    logger.info(f'Mini App URL: {MINI_APP_URL}')

    try:
        await asyncio.Event().wait()   # работаем бесконечно
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(run())
