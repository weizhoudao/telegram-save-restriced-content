 
# ---------------------------------------------------
# File Name: shrink.py
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

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import random
import requests
import string
import aiohttp
from devgagan import app
from devgagan.core.func import *
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP, OWNER_ID
from devgagan.modules.user_operation import AsyncOperationTracker
 
 
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
trial_user = tdb["trial_users"]
 
async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)
 
async def generate_random_param(length=8):
    """Generate a random parameter."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
 
async def is_user_verified(user_id):
    """Check if a user has an active session."""
    session = await token.find_one({"user_id": user_id})
    return session is not None

async def is_already_trial(user_id):
    session = await trial_user.find_one({"user_id": user_id})
    return session is not None

async def del_trial_user(user_id):
    session = await trial_user.delete_one({"user_id": user_id})
    return session is not None

@app.on_message(filters.command("del_trial") & filters.user(OWNER_ID) & filters.private)
async def del_trial_user_handler(client, message):
    user_id = message.chat.id
    if await del_trial_user(user_id):
        await message.reply("删除成功")
    else:
        await message.reply("操作失败")

@app.on_message(filters.command("reset_user_quota") & filters.user(OWNER_ID) & filters.private)
async def reset_user_quota_handler(client, message):
    if not await AsyncOperationTracker(MONGO_DB).reset_user_quota(int(message.command[1])):
        await message.reply("重置失败")
    else:
        await message.reply("重置成功")
 
@app.on_message(filters.command("start"))
async def token_handler(client, message):
    """Handle the /token command."""
    join = await subscribe(client, message)
    if join == 1:
        return
    chat_id = "save_restricted_content_bots"
    msg = await app.get_messages(chat_id, 796)
    user_id = message.chat.id
    image_url = "https://i.ibb.co/rKMQt1S3/20250330-112212-2x.png"
    join_button = InlineKeyboardButton("加入群聊", url="https://t.me/savedogpub")
    premium = InlineKeyboardButton("购买会员", url="https://t.me/savedogkfbot")   
    keyboard = InlineKeyboardMarkup([
        [join_button],   
        [premium]    
    ])

    await message.reply_photo(
        msg.photo.file_id,
        caption=(
            "hello, 欢迎使用下载神器!\n"
            "我可以帮你下载那些限制下载视频,图片,音频的频道或者群组的内容,也可以帮你下载Youtube/抖音/快手/哔哩哔哩等社交媒体上的视频和音频. \n"
            "/help 查看使用教程"
        ),
        reply_markup=keyboard
    )

@app.on_message(filters.command("tryvip"))
async def smart_handler(client, message):
    user_id = message.chat.id
     
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("你已经是会员了,不需要申请试用哦 😉")
        return

    if await is_user_verified(user_id):
        await message.reply("✅ 试用生效中!")
        return

    if await is_already_trial(user_id):
        await message.reply("你已经试用过了哦, 可以购买会员享受更多无限制功能.")
        return
    else:
        param = await generate_random_param(32)

        await token.insert_one({
            "user_id": user_id,
            "param": param,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=1),
        })
        await trial_user.insert_one({
            "user_id": user_id,
            "param": param,
            "created_at": datetime.utcnow(),
        })
        await message.reply("🚀 30分钟试用已激活！\n\n生效后你将可以体验\n1. 30分钟不限制使用\n2.批量下载,最高支持一次性下载20个视频或者音频")
