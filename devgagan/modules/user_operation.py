import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from config import FREE_PER_DAY

class AsyncOperationTracker:
    def __init__(self, mongo_uri: str, db_name: str = "telegram_bot"):
        """
        初始化异步MongoDB连接
        :param mongo_uri: MongoDB连接URI
        :param db_name: 数据库名称，默认为telegram_bot
        """
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db['user_operations']
        self._index_created = False

    async def initialize(self):
        """异步初始化索引"""
        if not self._index_created:
            try:
                await self.collection.create_index(
                    [("user_id", 1), ("date", 1)],
                    name="user_date_index",
                    unique=True
                )
            except DuplicateKeyError:
                pass
            self._index_created = True

    async def check_user_quota(self, user_id: int) -> Dict[str, Any]:
        """
        检查用户当日剩余配额（带并发控制）
        :param user_id: 用户Telegram ID
        :return: 包含配额状态的字典
        """
        await self.initialize()
        today = datetime.utcnow().date().isoformat()
        
        result = await self.collection.find_one({"user_id":user_id,"date":today})
        if result:
            new_count = result.get("count") + 1
            if new_count > FREE_PER_DAY:
                return False
            await self.collection.update_one({"user_id":user_id,"date":today},{"$set":{"count":new_count}})
            return True
        else:
            await self.collection.insert_one({"user_id":user_id,"date":today,"count":1})
            return True

    async def log_operation(self, user_id: int, metadata: Dict[str, Any]) -> str:
        """
        记录操作详情（带自动过期）
        :param user_id: 用户Telegram ID
        :param metadata: 操作元数据
        :return: 操作记录ID
        """
        await self.initialize()
        record = {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "metadata": metadata,
            "expire_at": datetime.utcnow() + timedelta(days=30)
        }
        result = await self.collection.insert_one(record)
        return str(result.inserted_id)

    async def get_daily_usage(self, user_id: int) -> Dict[str, Any]:
        """
        获取当日详细使用情况
        :param user_id: 用户Telegram ID
        :return: 使用情况统计
        """
        await self.initialize()
        today = datetime.utcnow().date().isoformat()
        pipeline = [
            {"$match": {"user_id": user_id, "date": today}},
            {"$project": {
                "count": 1,
                "operations": {"$slice": ["$operations", -10]}  # 返回最近10条
            }}
        ]
        cursor = self.collection.aggregate(pipeline)
        return await cursor.next() if await cursor.fetch_next else None

    async def reset_user_quota(self, user_id: int) -> bool:
        """
        重置用户配额（管理员功能）
        :param user_id: 用户Telegram ID
        :return: 是否重置成功
        """
        await self.initialize()
        today = datetime.utcnow().date().isoformat()
        debug = await self.collection.find_one({"user_id":user_id,"date":today})
        print(debug)
        result = await self.collection.update_one(
            {"user_id": user_id, "date": today},
            {"$set": {"count": 0}}
        )
        return result.modified_count > 0
