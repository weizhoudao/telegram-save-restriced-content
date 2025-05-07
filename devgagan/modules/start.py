# ---------------------------------------------------
# File Name: start.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

from pyrogram import filters
from devgagan import app
from config import OWNER_ID
from devgagan.core.func import subscribe
import asyncio
from devgagan.core.func import *
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.functions.bots import SetBotInfo
from pyrogram.raw.types import InputUserSelf

from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from devgagan.core.user_log import user_logger
from devgagan.modules.rate_limiter import rate_limiter
 
@app.on_message(filters.command("set") & filters.user(OWNER_ID) & filters.private)
async def set(_, message):
    if message.from_user.id not in OWNER_ID:
        await message.reply("非认证用户不允许操作")
        return
     
    await app.set_bot_commands([
        BotCommand("batch", "批量下载"),
        BotCommand("login", "登录(下载非公开频道或者群链接需要)"),
        BotCommand("logout", "登出"),
        BotCommand("tryvip", "免费使用30分钟会员功能"),
        BotCommand("single", "/single <视频链接> 下载单个视频"),
        BotCommand("userpost", "/userpost <用户主页地址> <下载数量> 下载指定用户指定数量的视频"),
        BotCommand("transfer", "将会员转给别人"),
        BotCommand("help", "查看机器人功能"),
        BotCommand("cancel", "取消批量计划"),
        BotCommand("setcookie", "设置cookie(下载部分视频需要)"),
        BotCommand("setytcookie", "设置youtube网站cookie")
    ])
    await message.reply("设置成功")
 
help_pages = [
    (
        "📝 **机器人指令大全**:\n\n"
        " **/transfer userID**\n"
        "> 将会员转让给其他用户 (仅会员可操作)\n\n"
        "**/tryvip**\n"
        "> 免费体验30分钟vip权益\n\n"
        " **/single 视频链接**\n"
        "> 下载单个视频\n\n"
        "**/userpost 用户主页地址 下载数量**\n"
        "> 下载指定用户指定数量的视频(仅会员可操作)\n\n"
        "**/setcookie**\n"
        "> 设置cookie\n\n"
        "**/setytcookie**\n"
        "> 设置youtube网站的cookie\n\n"
        " **/login**\n"
        "> 登录。如果要下载的链接是不公开的频道，需要进行登录操作\n\n"
        " **/batch**\n"
        "> 批量下载，指定一个开始的链接，批量下载这个链接后的n条消息 (登录后可操作)\n\n"
        " **/logout**\n"
        "> 登出\n\n"
        " **/cancel**\n"
        "> 取消正在进行的批量操作\n\n"
    )
]
 
async def send_or_edit_help_page(_, message, page_number):
    if page_number < 0 or page_number >= len(help_pages):
        return
 
    await message.delete()
     
    await message.reply(
        help_pages[page_number]
    )
 
@app.on_message(filters.command("help") & filters.private)
@rate_limiter.rate_limited
async def help(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return
 
    await send_or_edit_help_page(client, message, 0)
    await user_logger.log_action(message.from_user,"command", "help")
