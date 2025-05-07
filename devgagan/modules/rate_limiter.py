import asyncio
from functools import wraps
from collections import deque
from typing import Deque, Dict, Set
from pyrogram import Client, filters
from pyrogram.types import Message
from config import MAX_CONCURRENT_TASKS
from devgagan import app

class RateLimiter:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.waiting_queue: Deque[tuple] = deque()
        self.active_users: Set[int] = set()  # 跟踪活跃用户
        self.queue_positions: Dict[int, int] = {}
        self.notification_tasks: Dict[int, asyncio.Task] = {}
        self.lock = asyncio.Lock()

    def rate_limited(self, func):
        @wraps(func)
        async def wrapper(client: Client, message: Message):
            user_id = message.from_user.id
            chat_id = message.chat.id

            async with self.lock:
                # 检查用户是否已有任务
                if user_id in self.active_users:
                    await message.reply("⚠️ 您已有任务在处理中，请等待完成")
                    return

                # 标记用户为活跃状态
                self.active_users.add(user_id)

            try:
                # 尝试立即获取信号量
                if self.semaphore.locked() and self.semaphore._value == 0:
                    # 加入队列
                    async with self.lock:
                        position = len(self.waiting_queue) + 1
                        self.queue_positions[user_id] = position
                        future = asyncio.Future()
                        self.waiting_queue.append((user_id, chat_id, future))
                    
                    # 发送队列通知并启动通知任务
                    await message.reply(f"⏳ 您已被加入队列，当前位置：第{position}位")
                    self.notification_tasks[user_id] = asyncio.create_task(
                        self._send_queue_updates(user_id, chat_id)
                    )

                    # 等待直到获得执行权限
                    try:
                        await future
                    finally:
                        async with self.lock:
                            self.queue_positions.pop(user_id, None)
                            if task := self.notification_tasks.pop(user_id, None):
                                task.cancel()

                # 实际执行逻辑
                async with self.semaphore:
                    await message.reply("🚀 开始处理您的请求...")
                    try:
                        return await func(client, message)
                    finally:
                        # 触发下一个任务
                        await self._trigger_next()
            finally:
                async with self.lock:
                    self.active_users.discard(user_id)

        return wrapper

    async def _send_queue_updates(self, user_id: int, chat_id: int):
        """定时发送队列位置更新"""
        try:
            last_position = self.queue_positions.get(user_id, 0)
            while True:
                await asyncio.sleep(10)
                current_position = self.queue_positions.get(user_id)
                if not current_position:
                    return
                if current_position < last_position:
                    await app.send_message(
                        chat_id,
                        f"📈 队列更新：您当前的位置是第{current_position}位"
                    )
                    last_position = current_position
        except asyncio.CancelledError:
            pass

    async def _trigger_next(self):
        """触发下一个等待任务"""
        async with self.lock:
            if self.waiting_queue:
                user_id, chat_id, future = self.waiting_queue.popleft()
                
                # 更新队列位置
                for idx, (uid, *_ ) in enumerate(self.waiting_queue):
                    self.queue_positions[uid] = idx + 1
                
                # 唤醒等待的任务
                future.set_result(True)

# 初始化限流器
rate_limiter = RateLimiter(MAX_CONCURRENT_TASKS)
