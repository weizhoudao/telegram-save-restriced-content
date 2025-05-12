# ---------------------------------------------------
# File Name: users_db.py
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

from config import MONGO_DB
from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
from pymongo import ReturnDocument

mongo = MongoCli(MONGO_DB)
db = mongo.users
db = db.users_db
download_channel = mongo.users.download_channel


# 函数1：查询 user_id 对应的 channel_id
async def get_channel_id(user_id):
    """查询 user_id 对应的 channel_id，若存在则返回，否则返回 None"""
    document = await download_channel.find_one({"user_id": user_id})
    return document.get("channel_id") if document else None

# 函数2：设置或更新 user_id 对应的 channel_id
async def set_channel_id(user_id, channel_id):
    """设置或更新 user_id 对应的 channel_id，返回操作后的 channel_id"""
    result = await download_channel.find_one_and_update(
        {"user_id": user_id},
        {"$set": {"channel_id": channel_id}},
        upsert=True,  # 如果不存在则插入新文档
        return_document=ReturnDocument.AFTER  # 返回更新后的文档
    )
    return result["channel_id"]


async def get_users():
  user_list = []
  async for user in db.users.find({"user": {"$gt": 0}}):
    user_list.append(user['user'])
  return user_list


async def get_user(user):
  users = await get_users()
  if user in users:
    return True
  else:
    return False

async def add_user(user):
  users = await get_users()
  if user in users:
    return
  else:
    await db.users.insert_one({"user": user})


async def del_user(user):
  users = await get_users()
  if not user in users:
    return
  else:
    await db.users.delete_one({"user": user})
    


