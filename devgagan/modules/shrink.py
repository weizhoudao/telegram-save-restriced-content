 
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
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP  
 
 
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
trial_user = tdb["trial_users"]
 
 
async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)
 
 
Param = {}
 
 
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
 
 
@app.on_message(filters.command("start"))
async def token_handler(client, message):
    """Handle the /token command."""
    join = await subscribe(client, message)
    if join == 1:
        return
    chat_id = "save_restricted_content_bots"
    msg = await app.get_messages(chat_id, 796)
    user_id = message.chat.id
    if len(message.command) <= 1:
        image_url = "https://i.ibb.co/rKMQt1S3/20250330-112212-2x.png"
        join_button = InlineKeyboardButton("加入群聊", url="https://t.me/savedogpub")
        premium = InlineKeyboardButton("购买会员", url="https://t.me/kingofpatal")   
        keyboard = InlineKeyboardMarkup([
            [join_button],   
            [premium]    
        ])
         
        await message.reply_photo(
            msg.photo.file_id,
            caption=(
                "hello, 欢迎使用下载神器!\n"
                "我可以帮你下载那些限制下载视频,图片,音频的频道或者群组的内容,也可以帮你下载Youtube, INSTA等社交媒体上的视频和音频. "
                "/help 查看使用教程"
            ),
            reply_markup=keyboard
        )
        return  
 
    param = message.command[1] if len(message.command) > 1 else None
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("你已经是会员了,不需要使用token哦 😉")
        return
 
     
    if param:
        if user_id in Param and Param[user_id] == param:
             
            await token.insert_one({
                "user_id": user_id,
                "param": param,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=3),
            })
            await trial_user.insert_one({
                "user_id": user_id,
                "param": param,
                "created_at": datetime.utcnow(),
            })
            del Param[user_id]   
            await message.reply("✅ 30分钟体验资格已激活")
            return
        else:
            await message.reply("❌ 验证码无效,请输入/token 重试申请一次")
            return
 
@app.on_message(filters.command("token"))
async def smart_handler(client, message):
    user_id = message.chat.id
     
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("你已经是会员了,不需要申请token哦 😉")
        return
    if await is_already_trial(user_id):
        await message.reply("你已经试用过了哦, 可以购买会员享受更多无限制功能.")
        return
    if await is_user_verified(user_id):
        await message.reply("✅ token已经生效了!")
        return
    else:
        param = await generate_random_param()
        Param[user_id] = param   
 
        msg_text = "验证码: "
        msg_text += param
        msg_text += '\n复制这个验证码,然后输入指令/start 验证码,体验资格即生效.\n\n>生效后你将可以体验\n1. 30分钟不限制使用\n2.批量下载,最高支持一次性下载20个视频或者音频'
        await message.reply(msg_text)
 
