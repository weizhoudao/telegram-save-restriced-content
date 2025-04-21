# devgagan/utils/__init__.py
import os
import asyncio
import time
import re
import string
import random
import aiofiles
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from typing import Dict, Optional, Union, List
import logging
from config import MONGO_DB

logger = logging.getLogger(__name__)

# --------------------------
# 通用工具函数
# --------------------------
def get_random_string(length: int = 7) -> str:
    """生成随机文件名"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# --------------------------
# 下载任务管理器
# --------------------------
class DownloadTaskManager:
    """异步安全的下载任务管理器"""
    def __init__(self):
        self.tasks: Dict[int, bool] = {}
        self.lock = asyncio.Lock()

    def is_user_busy(self, user_id: int) -> bool:
        """检查用户是否有进行中任务"""
        return self.tasks.get(user_id, False)

    async def add_task(self, user_id: int):
        """添加下载任务"""
        async with self.lock:
            if self.tasks.get(user_id, False):
                raise asyncio.CancelledError("存在进行中的任务")
            self.tasks[user_id] = True

    async def remove_task(self, user_id: int):
        """移除下载任务"""
        async with self.lock:
            self.tasks.pop(user_id, None)

# --------------------------
# Cookie 管理器
# --------------------------
class CookieManager:
    """安全的Cookie存储管理"""
    def __init__(self, storage_path: str = "./data/cookies"):
        self.base_path = Path(storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def _get_cookie_path(self, user_id: int) -> Path:
        """获取用户Cookie存储路径"""
        return self.base_path / f"user_{user_id}.cookie"

    async def get_cookies(self, user_id: int) -> str:
        """异步获取用户Cookie"""
        cookie_path = self._get_cookie_path(user_id)
        if not cookie_path.exists():
            return ""
            
        try:
            async with aiofiles.open(cookie_path, "r") as f:
                return await f.read()
        except Exception as e:
            logging.error(f"读取Cookie失败: {e}")
            return ""

    async def set_cookies(self, user_id: int, cookies: str):
        """异步设置用户Cookie"""
        cookie_path = self._get_cookie_path(user_id)
        async with aiofiles.open(cookie_path, "w") as f:
            await f.write(cookies)

# --------------------------
# 速率限制器
# --------------------------
class RateLimiter:
    """基于滑动窗口的速率限制器"""
    def __init__(self, max_requests: int = 5, period: float = 60.0):
        self.max_requests = max_requests
        self.period = period
        self.access_records: Dict[int, list] = {}
        self.lock = asyncio.Lock()

    async def check_limit(self, user_id: int) -> bool:
        """检查是否允许请求"""
        async with self.lock:
            now = time.time()
            window_start = now - self.period
            
            # 清理过期记录
            records = [
                t for t in self.access_records.get(user_id, [])
                if t > window_start
            ]
            
            if len(records) >= self.max_requests:
                return False
                
            records.append(now)
            self.access_records[user_id] = records
            return True

# --------------------------
# 平台识别工具
# --------------------------
class PlatformDetector:
    """URL平台识别工具"""
    PLATFORM_PATTERNS = {
        "douyin": re.compile(r"(douyin\.com|iesdouyin\.com)"),
        "tiktok": re.compile(r"tiktok\.com"),
        "bilibili": re.compile(r"(bilibili\.com|b23\.tv)"),
        "youtube": re.compile(r"(youtube\.com|youtu\.be)"),
        "kuaishou": re.compile(r"(kuaishou\.com|v\.kuaishou\.com)")
    }

    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """识别URL所属平台"""
        for platform, pattern in cls.PLATFORM_PATTERNS.items():
            if pattern.search(url):
                return platform
        return None

# --------------------------
# 临时文件管理器
# --------------------------
class TempFileManager:
    """安全的临时文件管理"""
    def __init__(self, prefix: str = "temp_", suffix: str = ".tmp"):
        self.files = set()
        self.prefix = prefix
        self.suffix = suffix
        
    async def create_tempfile(self, content: str = "") -> str:
        """创建临时文件"""
        async with aiofiles.tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            prefix=self.prefix,
            suffix=self.suffix
        ) as temp_file:
            if content:
                await temp_file.write(content)
            path = temp_file.name
            self.files.add(path)
            return path

    async def cleanup(self):
        """清理所有临时文件"""
        for path in self.files:
            try:
                os.unlink(path)
            except Exception as e:
                logging.error(f"清理临时文件失败: {path} - {e}")
        self.files.clear()


#-----------------------------------------
# 用mongodb做存储的cookie管理器
#----------------------------------------
class AdvancedCookieManager:
    """支持多格式Cookie存储的MongoDB管理器"""
    VALID_FORMATS = {'header', 'netscape', 'json'}
    DEFAULT_FORMAT = 'header'

    def __init__(
        self,
        mongo_uri: str = MONGO_DB,
        db_name: str = "telegram_bot",
        collection_name: str = "user_cookies"
    ):
        self.mongo_uri = mongo_uri
        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        # 创建索引
        #await self._create_indexes()

    async def _create_indexes(self):
        """创建必要的数据库索引"""
        try:
            await self.collection.create_index("user_id")
            await self.collection.create_index("formats.format")
        except Exception as e:
            logger.error(f"创建索引失败: {e}")

    async def set_cookies(
        self,
        user_id: int,
        cookies: Union[str, dict],
        format_type: str = DEFAULT_FORMAT,
        source: str = "unknown",
        metadata: dict = None
    ) -> bool:
        """
        存储多格式Cookie
        :param user_id: 用户ID
        :param cookies: Cookie数据（字符串或字典）
        :param format_type: 格式类型（header/netscape/json）
        :param source: 来源标识（如浏览器类型）
        :param metadata: 附加元数据
        :return: 是否成功
        """
        if format_type not in self.VALID_FORMATS:
            raise ValueError(f"无效的Cookie格式，支持的格式：{self.VALID_FORMATS}")

        update_data = {
            "$set": {
                "updated_at": datetime.utcnow(),
                f"formats.{format_type}": {
                    "data": cookies,
                    "source": source,
                    "version": 1,
                    "metadata": metadata or {}
                }
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow()
            }
        }

        try:
            result = await self.collection.update_one(
                {"user_id": user_id},
                update_data,
                upsert=True
            )
            return result.acknowledged
        except PyMongoError as e:
            logger.error(f"存储Cookie失败: {user_id} - {e}")
            return False

    async def get_cookies(
        self,
        user_id: int,
        format_type: str = DEFAULT_FORMAT,
        version: int = -1
    ) -> Optional[Union[str, dict]]:
        """
        获取指定格式的Cookie
        :param user_id: 用户ID
        :param format_type: 需要的格式类型
        :param version: 版本号（-1表示最新）
        :return: Cookie数据或None
        """
        projection = {
            f"formats.{format_type}": 1,
            "_id": 0
        }

        try:
            doc = await self.collection.find_one(
                {"user_id": user_id},
                projection=projection
            )

            if not doc or not doc.get('formats', {}).get(format_type):
                return None

            cookie_data = doc['formats'][format_type]
            if version != -1 and cookie_data.get('version') != version:
                return None

            return cookie_data['data']
        except PyMongoError as e:
            logger.error(f"获取Cookie失败: {user_id} - {e}")
            return None

    async def list_formats(self, user_id: int) -> List[Dict]:
        """获取用户所有存储的Cookie格式信息"""
        try:
            doc = await self.collection.find_one(
                {"user_id": user_id},
                projection={"formats": 1, "_id": 0}
            )
            return [
                {
                    "format": fmt,
                    "source": data['source'],
                    "version": data['version'],
                    "last_updated": data.get('metadata', {}).get('timestamp')
                }
                for fmt, data in doc.get('formats', {}).items()
            ] if doc else []
        except Exception as e:
            logger.error(f"获取格式列表失败: {user_id} - {e}")
            return []

    async def migrate_legacy_cookies(self, user_id: int):
        """迁移旧版单格式Cookie数据"""
        try:
            doc = await self.collection.find_one_and_update(
                {"user_id": user_id, "formats": {"$exists": False}},
                [{
                    "$set": {
                        "formats": {
                            self.DEFAULT_FORMAT: {
                                "data": "$cookies",
                                "source": "legacy",
                                "version": 1,
                                "metadata": {
                                    "migrated_at": datetime.utcnow()
                                }
                            }
                        }
                    }
                }],
                return_document=ReturnDocument.AFTER
            )
            return doc is not None
        except Exception as e:
            logger.error(f"迁移旧数据失败: {user_id} - {e}")
            return False

    async def delete_format(self, user_id: int, format_type: str) -> bool:
        """删除指定格式的Cookie"""
        try:
            result = await self.collection.update_one(
                {"user_id": user_id},
                {"$unset": {f"formats.{format_type}": ""}}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"删除格式失败: {user_id} - {e}")
            return False

    async def close(self):
        """关闭数据库连接"""
        self.client.close()
