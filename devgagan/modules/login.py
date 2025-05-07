# ---------------------------------------------------
# File Name: login.py
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

from pyrogram import filters, Client
from devgagan import app
import random
import os
import asyncio
import string
from devgagan.core.mongo import db
from devgagan.core.func import subscribe, chk_user
from devgagan.core.user_log import user_logger
from config import API_ID as api_id, API_HASH as api_hash
from devgagan.modules.rate_limiter import rate_limiter
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))  # Editted ... 

async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)
    
    if memory_file_exists:
        os.remove(memory_file)

    # Delete session from the database
    if session_file_exists or memory_file_exists:
        await db.remove_session(user_id)
        return True  # Files were deleted
    return False  # No files found

@app.on_message(filters.command("logout") & filters.private)
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)
    try:
        await db.remove_session(user_id)
    except Exception:
        pass

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("✅ Logged out with flag -m")

    await user_logger.log_action(message.from_user,"command","logout")
        
    
@app.on_message(filters.command("login") & filters.private)
@rate_limiter.rate_limited
async def generate_session(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return
        
    user_id = message.chat.id   
    
    number = await _.ask(user_id, '请输入你的电话号码,带区号. \n比如: +19876543210', filters=filters.text)   
    phone_number = number.text
    try:
        await message.reply("📲 正在发送验证码...")
        client = Client(f"session_{user_id}", api_id, api_hash)
        
        await client.connect()
    except Exception as e:
        await message.reply(f"❌ 发送验证码失败 {e}. 请稍候重试.")
    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ 系统错误,请联系管理员.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ 请输入正确的电话号码.')
        return
    try:
        otp_code = await _.ask(user_id, "请检查你的telegram账号,如果收到登录验证码,请按照指引操作: \n假如你收到的验证码是 `12345`, 请回复 `1 2 3 4 5`.", filters=filters.text, timeout=600)
    except TimeoutError:
        await message.reply('⏰ 操作超时,请重试.')
        return
    phone_code = otp_code.text.replace(" ", "")
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
                
    except PhoneCodeInvalid:
        await message.reply('❌ 验证码错误.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ 验证码已过期,请重试获取.')
        return
    except SessionPasswordNeeded:
        try:
            two_step_msg = await _.ask(user_id, '你的账号开启了两步验证,请输入密码.', filters=filters.text, timeout=300)
        except TimeoutError:
            await message.reply('⏰ 操作超时,请重试.')
            return
        try:
            password = two_step_msg.text
            await client.check_password(password=password)
        except PasswordHashInvalid:
            await two_step_msg.reply('❌ 密码错误.')
            return
    string_session = await client.export_session_string()
    await db.set_session(user_id, string_session)
    await client.disconnect()
    await otp_code.reply("✅ 登录成功!")
    await user_logger.log_action(message.from_user,"command","login")
