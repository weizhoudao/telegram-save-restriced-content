from devgagan import app, userrbot
from devgagan.core.func import *
from devgagan.core.mongo import db, users_db
from pyrogram import filters, Client
from config import API_ID, API_HASH, FREEMIUM_LIMIT, PREMIUM_LIMIT, OWNER_ID, DEFAULT_SESSION, MONGO_DB, OPER_INTERNAL
import logging
import os
from devgagan.modules.shrink import is_user_verified
from devgagan.core.func import chk_user, subscribe
from devgagan.core.get_msg import get_msg, extract_message_info, get_replies, copy_message_to_target_chat
from devgagan.modules.main import check_interval, set_interval

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

users_loop = {}

async def initialize_userbot(user_id):
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
            logging.error(f"登录态失效:{user_id}")
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

async def process_and_upload_link(userbot, user_id, msg_id, link, retry_count, message):
    try:
        await get_msg(userbot, user_id, msg_id, link, retry_count, message)
        try:
            await app.delete_messages(user_id, msg_id)
        except Exception:
            logging.error(f"get msg error:{user_id},{msg_id},{link}")
            pass
        await asyncio.sleep(15)
    finally:
        pass

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
        return
    await msg.edit_text("非法链接...")

@app.on_message(filters.command("get_reply") & filters.private)
async def handle_get_reply(client, message):
    join = await subscribe(app, message)
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

    if len(message.text.split()) != 3:
        return await message.reply("输入格式不对, 用法:/get_reply 消息链接 要下载的评论数(数字)")
    url = message.text.split()[1]
    download_count = int(message.text.split()[2])
    max_batch_size = FREEMIUM_LIMIT if freecheck == 1 else PREMIUM_LIMIT
    if download_count > max_batch_size:
        return await message.reply("请输入不超过{max_batch_size}的下载数量")
    user_id = message.chat.id

    logging.info(f"user_id:{user_id},url:{url},count:{download_count}")

    link = url if "tg://openmessage" in url else get_link(url)
    userbot = await initialize_userbot(user_id)
    if not userbot:
        return await message.reply("下载评论区消息需要先登录,请发送 /login 指令后按指引操作.")

    msg_info = extract_message_info(link)
    chat_id = msg_info.get('group_id')
    message_id = msg_info.get('message_id')
    if chat_id.isdigit():
        chat_id = int('-100' + chat_id)

    replies = []
    async for m in userbot.get_discussion_replies(chat_id, message_id):
        replies.append(m)
    count = 1
    try:
        for m in reversed(replies):
            tips = await app.send_message(user_id, f"开始下载第{count}条评论")
            await copy_message_to_target_chat(userbot, m, user_id, tips.id, message)
            count += 1
            if count > download_count:
                break
        await message.reply("下载完成!")
    except FloodWait as fw:
        await msg.edit_text(f'请过{fw.x}秒后重试')
    except Exception as e:
        logging.info(f"error:{e}")
        await msg.edit_text(f"Link: `{link}`\n\n**Error:** {str(e)}")
    finally:
        pass 

async def batch_process_replies(start_url, max_batch_size, message):
    msg_info = extract_message_info(start_url)
    if msg_info.get('group_id') is None or msg_info.get('message_id') is None or msg_info.get('reply_id') is None:
        loggin.info(f"invalid url:{start_url}")
        return await app.send_message(message.chat.id, "非法链接，请重新输入...")

    for attempt in range(3):
        num_messages = await app.ask(message.chat.id, f"你想下载多少条消息?\n> 请输入不超过 {max_batch_size}的数字")
        try:
            download_count = int(num_messages.text.strip())
            if 1 <= download_count <= max_batch_size:
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

    # 需要用户身份操作，必须登录
    userbot = await initialize_userbot(message.chat.id)
    if userbot is None:
        return await app.send_message(message.chat.id, "特殊链接，请先使用/login 指令登录后再操作")

    group_id = msg_info.get('group_id')
    message_id = msg_info.get('message_id')
    reply_id = msg_info.get('reply_id')

    edit_id = message.chat.id
    user_id = message.from_user.id

    tips = await message.reply("正在处理中...")
    try:
        await get_replies(userbot, user_id, tips.id, start_url, group_id, message_id, reply_id, download_count, message)
        await asyncio.sleep(15)
    finally:
        pass


@app.on_message(filters.command("batchx") & filters.private)
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

    start = await app.ask(message.chat.id, "请输入第一个视频的链接")
    start_url = start.text.strip()
    if 'thread' in start_url or 'comment' in start_url:
        return await batch_process_replies(start_url, max_batch_size, message)

    s = start_url.split("/")[-1]
    if s.isdigit():
        cs = int(s)
    else:
        logging.info(f"invalid url:{start_url}")
        return await app.send_message(message.chat.id, "非法链接，请重新输入...")

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

@app.on_message(filters.command("setenv") & filters.private & filters.user(OWNER_ID))
async def handle_setenv(client, message):
    key = message.text.split()[1]
    value = message.text.split()[2]
    os.environ[key] = value

@app.on_message(filters.command("getenv") & filters.private & filters.user(OWNER_ID))
async def handle_setenv(client, message):
    key = message.text.split()[1]
    value = os.getenv(key, 'null')
    return await message.reply(f"{value}")
