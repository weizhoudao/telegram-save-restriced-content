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
 
@app.on_message(filters.command("set"))
async def set(_, message):
    if message.from_user.id not in OWNER_ID:
        await message.reply("非认证用户不允许操作")
        return
     
    await app.set_bot_commands([
        BotCommand("batch", "批量下载"),
        BotCommand("login", "登录(下载非公开频道或者群链接需要)"),
        BotCommand("logout", "登出"),
        BotCommand("token", "免费使用30分钟会员功能"),
        BotCommand("adl", "下载音频"),
        BotCommand("dl", "下载视频"),
        BotCommand("transfer", "将会员转给别人"),
        BotCommand("help", "查看机器人功能"),
        BotCommand("cancel", "取消批量计划"),
        BotCommand("setcookie", "设置cookie(下载youtube或者ins视频需要)")
    ])
    await message.reply("设置成功")
 
 
 
 
help_pages = [
    (
        "📝 **机器人指令大全**:\n\n"
        " **/transfer userID**\n"
        "> 将会员转让给其他用户 (仅会员可操作)\n\n"
        " **/dl link**\n"
        "> 下载视频\n\n"
        " **/adl link**\n"
        "> 下载音频\n\n"
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
 
@app.on_message(filters.command("help"))
async def help(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return
 
     
    await send_or_edit_help_page(client, message, 0)
 
 
@app.on_callback_query(filters.regex(r"help_(prev|next)_(\d+)"))
async def on_help_navigation(client, callback_query):
    action, page_number = callback_query.data.split("_")[1], int(callback_query.data.split("_")[2])
 
    if action == "prev":
        page_number -= 1
    elif action == "next":
        page_number += 1
 
     
    await send_or_edit_help_page(client, callback_query.message, page_number)
 
     
    await callback_query.answer()
 
 
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
 
@app.on_message(filters.command("terms") & filters.private)
async def terms(client, message):
    terms_text = (
        "> 📜 **条款及细则** 📜\n\n"
        "✨ We are not responsible for user deeds, and we do not promote copyrighted content. If any user engages in such activities, it is solely their responsibility.\n"
        "✨ Upon purchase, we do not guarantee the uptime, downtime, or the validity of the plan. __Authorization and banning of users are at our discretion; we reserve the right to ban or authorize users at any time.__\n"
        "✨ Payment to us **__does not guarantee__** authorization for the /batch command. All decisions regarding authorization are made at our discretion and mood.\n"
    )
     
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 查看会员计划", callback_data="see_plan")],
            [InlineKeyboardButton("💬 联系管理员", url="https://t.me/dldoghelper_bot")],
        ]
    )
    await message.reply_text(terms_text, reply_markup=buttons)
 
 
@app.on_message(filters.command("plan") & filters.private)
async def plan(client, message):
    plan_text = (
        "> 💰 **会员价格**:\n\n 100元一年\n"
        "📥 **下载限制**: 会员可以一次下载最多100000个文件\n"
        "🛑 **批量下载**: 批量下载包括两种模式 /bulk 和 /batch.\n"
        "   - 建议等任务自动结束再开始其他的上传或者下载任务\n\n"
        "📜 **条款及细则**: 查看更多条款及细则，请输入/terms.\n"
    )
     
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 查看条款及细则", callback_data="see_terms")],
            [InlineKeyboardButton("💬 联系管理员", url="https://t.me/dldoghelper_bot")],
        ]
    )
    await message.reply_text(plan_text, reply_markup=buttons)
 
 
@app.on_callback_query(filters.regex("see_plan"))
async def see_plan(client, callback_query):
    plan_text = (
        "> 💰 **会员价格**:\n\n 100元一年\n"
        "📥 **下载限制**: 会员可以一次下载最多100000个文件\n"
        "🛑 **批量下载**: 批量下载包括两种模式 /bulk 和 /batch.\n"
        "   - 建议等任务自动结束再开始其他的上传或者下载任务\n\n"
        "📜 **条款及细则**: 查看更多条款及细则，请输入/terms.\n"
    )
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 查看条款", callback_data="see_terms")],
            [InlineKeyboardButton("💬 联系管理员", url="https://t.me/dldoghelper_bot")],
        ]
    )
    await callback_query.message.edit_text(plan_text, reply_markup=buttons)
 
 
@app.on_callback_query(filters.regex("see_terms"))
async def see_terms(client, callback_query):
    terms_text = (
        "> 📜 **条款及细则** 📜\n\n"
        "✨ We are not responsible for user deeds, and we do not promote copyrighted content. If any user engages in such activities, it is solely their responsibility.\n"
        "✨ Upon purchase, we do not guarantee the uptime, downtime, or the validity of the plan. __Authorization and banning of users are at our discretion; we reserve the right to ban or authorize users at any time.__\n"
        "✨ Payment to us **__does not guarantee__** authorization for the /batch command. All decisions regarding authorization are made at our discretion and mood.\n"
    )
     
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 查看会员计划", callback_data="see_plan")],
            [InlineKeyboardButton("💬 联系管理员", url="https://t.me/dldoghelper_bot")],
        ]
    )
    await callback_query.message.edit_text(terms_text, reply_markup=buttons)
 
 
