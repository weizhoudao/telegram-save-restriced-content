# ---------------------------------------------------
# File Name: main.py
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
# More readable 
# ---------------------------------------------------

import time
import random
import string
import asyncio
from pyrogram import filters, Client
from devgagan import app, userrbot
from config import API_ID, API_HASH, FREEMIUM_LIMIT, PREMIUM_LIMIT, OWNER_ID, DEFAULT_SESSION, MONGO_DB, OPER_INTERNAL
from devgagan.core.get_func import get_msg
from devgagan.core.func import *
from devgagan.core.mongo import db
from devgagan.core.user_log import user_logger
from pyrogram.errors import FloodWait
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
from devgagan.modules.shrink import is_user_verified
from devgagan.modules.user_operation import AsyncOperationTracker
from devgagan.modules.rate_limiter import rate_limiter

async def generate_random_name(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

users_loop = {}
interval_set = {}
batch_mode = {}

async def process_and_upload_link(userbot, user_id, msg_id, link, retry_count, message):
    try:
        await get_msg(userbot, user_id, msg_id, link, retry_count, message)
        try:
            await app.delete_messages(user_id, msg_id)
        except Exception:
            pass
        await asyncio.sleep(15)
    finally:
        pass

# Function to check if the user can proceed
async def check_interval(user_id, freecheck):
    if freecheck != 1 or await is_user_verified(user_id):  # Premium or owner users can always proceed
        return True, None

    now = datetime.now()

    # Check if the user is on cooldown
    if user_id in interval_set:
        cooldown_end = interval_set[user_id]
        if now < cooldown_end:
            remaining_time = (cooldown_end - now).seconds
            return False, f"请等待{remaining_time}秒后再尝试下载. 购买会员可以跳过等待限制.\n\n> 你也可以通过/tryvip指令来获取半个小时的免费体验资格"
        else:
            del interval_set[user_id]  # Cooldown expired, remove user from interval set

    return True, None

async def set_interval(user_id, interval_minutes=OPER_INTERNAL):
    now = datetime.now()
    # Set the cooldown interval for the user
    interval_set[user_id] = now + timedelta(seconds=interval_minutes)
    

@app.on_message(
    filters.regex(r'https?://(?:www\.)?t\.me/[^\s]+|tg://openmessage\?user_id=\w+&message_id=\d+')
    & filters.private
)
@rate_limiter.rate_limited
async def single_link(_, message):
    user_id = message.chat.id

    # Check subscription and batch mode
    if await subscribe(_, message) == 1 or user_id in batch_mode:
        return


    # Check if user is already in a loop
    if users_loop.get(user_id, False):
        await message.reply(
            "你有一个正在进行中的任务,请等待其结束或者通过/cancel指令取消"
        )
        return

    # Check freemium limits
    if await chk_user(message, user_id) == 1 and user_id not in OWNER_ID and not await is_user_verified(user_id):
        if not await AsyncOperationTracker(MONGO_DB).check_user_quota(user_id):
            await message.reply("今日免费次数已用完,请购买会员或者通过/tryvip指令获取免费体验资格")
            return

    # Check cooldown
    can_proceed, response_message = await check_interval(user_id, await chk_user(message, user_id))
    if not can_proceed:
        await message.reply(response_message)
        return

    # Add user to the loop
    users_loop[user_id] = True

    link = message.text if "tg://openmessage" in message.text else get_link(message.text)
    msg = await message.reply("处理中...")
    userbot = await initialize_userbot(user_id)
    try:
        if await is_normal_tg_link(link):
            await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
            await set_interval(user_id, interval_minutes=45)
        else:
            await process_special_links(userbot, user_id, msg, link)
            
    except FloodWait as fw:
        await msg.edit_text(f'请过{fw.x}秒后重试')
    except Exception as e:
        await msg.edit_text(f"Link: `{link}`\n\n**Error:** {str(e)}")
    finally:
        users_loop[user_id] = False
        try:
            await msg.delete()
        except Exception:
            pass

    await user_logger.log_action(message.from_user,"message",message.text)


async def initialize_userbot(user_id): # this ensure the single startup .. even if logged in or not
    data = await db.get_data(user_id)
    if data and data.get("session"):
        try:
            device = 'iPhone 16 Pro' # added gareebi text
            userbot = Client(
                "userbot",
                api_id=API_ID,
                api_hash=API_HASH,
                device_model=device,
                session_string=data.get("session")
            )
            await userbot.start()
            return userbot
        except Exception:
            await app.send_message(user_id, "登录态失效请重新登录")
            return None
    else:
        if DEFAULT_SESSION:
            return userrbot
        else:
            return None


async def is_normal_tg_link(link: str) -> bool:
    """Check if the link is a standard Telegram link."""
    special_identifiers = ['t.me/+', 't.me/c/', 't.me/b/', 'tg://openmessage']
    return 't.me/' in link and not any(x in link for x in special_identifiers)
    
async def process_special_links(userbot, user_id, msg, link):
    if userbot is None:
        return await msg.edit_text("请先登录后再尝试下载")
    if 't.me/+' in link:
        result = await userbot_join(userbot, link)
        await msg.edit_text(result)
        return
    special_patterns = ['t.me/c/', 't.me/b/', '/s/', 'tg://openmessage']
    if any(sub in link for sub in special_patterns):
        await process_and_upload_link(userbot, user_id, msg.id, link, 0, msg)
        await set_interval(user_id, interval_minutes=45)
        return
    await msg.edit_text("非法链接...")

@app.on_message(filters.command("batch") & filters.private)
@rate_limiter.rate_limited
async def batch_link(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return
    user_id = message.chat.id
    # Check if a batch process is already running
    if users_loop.get(user_id, False):
        await app.send_message(
            message.chat.id,
            "你有一个批量任务正在进行中,请等待其结束后再操作"
        )
        return

    freecheck = await chk_user(message, user_id)
    if freecheck == 1 and user_id not in OWNER_ID and not await is_user_verified(user_id):
        await message.reply("请购买会员或者通过/tryvip指令获得免费体验资格")
        return

    max_batch_size = FREEMIUM_LIMIT if freecheck == 1 else PREMIUM_LIMIT

    # Start link input
    for attempt in range(3):
        start = await app.ask(message.chat.id, "请输入第一个链接\n\n> 最多重试三次")
        start_id = start.text.strip()
        s = start_id.split("/")[-1]
        if s.isdigit():
            cs = int(s)
            break
        await app.send_message(message.chat.id, "非法链接,请重新输入 ...")
    else:
        await app.send_message(message.chat.id, "超过最大重试次数了,请稍后再试...")
        return

    # Number of messages input
    for attempt in range(3):
        num_messages = await app.ask(message.chat.id, f"你想下载多少条消息?\n> 请输入不超过 {max_batch_size}的数字")
        try:
            cl = int(num_messages.text.strip())
            if 1 <= cl <= max_batch_size:
                break
            raise ValueError()
        except ValueError:
            await app.send_message(
                message.chat.id, 
                f"输入错误,请输入 1 到 {max_batch_size}的数字."
            )
    else:
        await app.send_message(message.chat.id, "超过最大重试次数,请稍候再试...")
        return

    # Validate and interval check
    can_proceed, response_message = await check_interval(user_id, freecheck)
    if not can_proceed:
        await message.reply(response_message)
        return
        
    join_button = InlineKeyboardButton("关注频道", url="https://t.me/savedogpub")
    keyboard = InlineKeyboardMarkup([[join_button]])
    pin_msg = await app.send_message(
        user_id,
        f"批量下载开始 ⚡\n处理中: 0/{cl}\n\n**__下载神器为你提供服务__**",
        reply_markup=keyboard
    )
    await pin_msg.pin(both_sides=True)

    users_loop[user_id] = True
    try:
        normal_links_handled = False
        userbot = await initialize_userbot(user_id)
        # Handle normal links first
        for i in range(cs, cs + cl):
            if user_id in users_loop and users_loop[user_id]:
                url = f"{'/'.join(start_id.split('/')[:-1])}/{i}"
                link = get_link(url)
                # Process t.me links (normal) without userbot
                if 't.me/' in link and not any(x in link for x in ['t.me/b/', 't.me/c/', 'tg://openmessage']):
                    msg = await app.send_message(message.chat.id, f"处理中...")
                    await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
                    await pin_msg.edit_text(
                        f"批量下载开始 ⚡\n处理中: {i - cs + 1}/{cl}\n\n**__下载神器为你提供服务__**",
                        reply_markup=keyboard
                    )
                    normal_links_handled = True
        if normal_links_handled:
            await set_interval(user_id, interval_minutes=300)
            await pin_msg.edit_text(
                f"成功处理 {cl} 条消息 🎉\n\n**__下载神器为你提供服务__**",
                reply_markup=keyboard
            )
            await app.send_message(message.chat.id, "批量处理成功! 🎉")
            return
            
        # Handle special links with userbot
        for i in range(cs, cs + cl):
            if not userbot:
                await app.send_message(message.chat.id, "你需要先进行登录操作,请输入/login指令,然后按照指引登录 ...")
                users_loop[user_id] = False
                return
            if user_id in users_loop and users_loop[user_id]:
                url = f"{'/'.join(start_id.split('/')[:-1])}/{i}"
                link = get_link(url)
                if any(x in link for x in ['t.me/b/', 't.me/c/']):
                    msg = await app.send_message(message.chat.id, f"处理中...")
                    await process_and_upload_link(userbot, user_id, msg.id, link, 0, message)
                    await pin_msg.edit_text(
                        f"批量处理开始 ⚡\n处理中: {i - cs + 1}/{cl}\n\n**__下载神器为你提供服务__**",
                        reply_markup=keyboard
                    )

        await set_interval(user_id, interval_minutes=300)
        await pin_msg.edit_text(
            f"成功处理 {cl} 条消息 🎉\n\n**__下载神器为你提供服务__**",
            reply_markup=keyboard
        )
        await app.send_message(message.chat.id, "批量处理成功! 🎉")

    except Exception as e:
        await app.send_message(message.chat.id, f"Error: {e}")
    finally:
        users_loop.pop(user_id, None)

    await user_logger.log_action(message.from_user,"command","batch")

@app.on_message(filters.command("cancel") & filters.private)
async def stop_batch(_, message):
    user_id = message.chat.id

    # Check if there is an active batch process for the user
    if user_id in users_loop:
        users_loop[user_id] = False  # Set the loop status to False
        await app.send_message(
            message.chat.id, 
            "批量任务已终止."
        )
    else:
        await app.send_message(
            message.chat.id, 
            "当前没有正在进行中的批量任务."
        )

    async with rate_limiter.lock:
        if user_id in rate_limiter.active_users:
            # 从队列中移除
            new_queue = [t for t in rate_limiter.waiting_queue if t[0] != user_id]
            rate_limiter.waiting_queue = deque(new_queue)

            # 更新队列位置
            for idx, (uid, *_ ) in enumerate(rate_limiter.waiting_queue):
                rate_limiter.queue_positions[uid] = idx + 1

            rate_limiter.queue_positions.pop(user_id, None)
            rate_limiter.active_users.discard(user_id)

    await user_logger.log_action(message.from_user,"command", "cancel")
