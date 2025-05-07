import os
import csv
import logging
from io import StringIO
from datetime import datetime
from typing import Union
from pyrogram import Client, filters, types
from motor.motor_asyncio import AsyncIOMotorClient
from devgagan import app
from config import MONGO_DB, USER_LOG_GROUP
from devgagan.core.mongo import vip_db

DB_NAME = "telegram_bot"
COLLECTION_NAME = "user_log"

class ActionLogger:
    def __init__(self, app: Client):
        self.app = app
        self.buffer = []
        self.buffer_size = 0
        self.max_buffer = 4096  # Telegram消息长度限制
        
        # 初始化MongoDB
        self.mongo = AsyncIOMotorClient(MONGO_DB)
        self.db = self.mongo[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

    async def log_action(
        self,
        user: Union[types.User, types.Chat],
        action_type: str,
        content: str
    ):
        """记录用户操作"""
        try:
            # 生成CSV格式日志条目
            timestamp = datetime.now().isoformat()
            username = user.username or "N/A"
            vip = await vip_db.check_vip(user.id)
            is_premium = False
            if vip:
                is_premium = True
            
            # 清理内容中的换行符
            cleaned_content = content.replace("\n", " ").replace("\r", " ")[:500]
            
            # 生成CSV行
            with StringIO() as output:
                writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
                writer.writerow([
                    timestamp,
                    user.id,
                    user.first_name,
                    str(is_premium),
                    action_type,
                    cleaned_content
                ])
                log_entry = output.getvalue().strip()
            
            entry_length = len(log_entry) + 1  # 包含换行符
            
            # 检查缓冲区容量
            if self.buffer_size + entry_length >= self.max_buffer:
                await self.flush_buffer()
            
            self.buffer.append(log_entry)
            self.buffer_size += entry_length
            
            # 立即刷新如果接近上限
            if self.buffer_size >= self.max_buffer:
                await self.flush_buffer()
                
        except Exception as e:
            logging.error(f"Logging error: {str(e)}")

    async def flush_buffer(self):
        """发送并清空缓冲区"""
        if not self.buffer:
            return
        
        try:
            # 发送到日志群组
            log_text = "\n".join(self.buffer)
            await self.app.send_message(
                chat_id=USER_LOG_GROUP,
                text=log_text[:4096]  # 确保不超过长度限制
            )
            
            # 存储到MongoDB
            documents = []
            for entry in self.buffer:
                try:
                    # 解析CSV条目
                    reader = csv.reader([entry])
                    data = next(reader)
                    documents.append({
                        "timestamp": datetime.fromisoformat(data[0]),
                        "id": data[1],
                        "user_name": data[2],
                        "is_premium": data[3].lower() == "true",
                        "action_type": data[4],
                        "content": data[5]
                    })
                except Exception as e:
                    logging.error(f"Parse error: {str(e)}")
                    continue
            
            if documents:
                await self.collection.insert_many(documents)
            
        except Exception as e:
            logging.error(f"Flush buffer error: {str(e)}")
        finally:
            self.buffer.clear()
            self.buffer_size = 0

user_logger = ActionLogger(app)
