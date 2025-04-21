from config import API_ID, API_HASH, PREMIUM_LIMIT, OWNER_ID, DEFAULT_SESSION,KS_GRAPHQL_QUERY, KS_GRAPHQL_URL, MONGO_DB
import yt_dlp
import requests
import os
import time
import tempfile
import string
from typing import List
from devgagan import app, userrbot
from pyrogram import Client, filters, enums
from pyrogram.types import MessageEntity
from devgagan.modules.shrink import is_user_verified
from devgagan.modules.user_operation import AsyncOperationTracker
from devgagan.modules.main import set_interval, check_interval
import random
import asyncio
import json
import logging
import re
from typing import Dict, Optional, Callable
from dataclasses import dataclass

from devgagan.crawlers.douyin.web.web_crawler import DouyinWebCrawler
from devgagan.crawlers.hybrid.hybrid_crawler import HybridCrawler
from devgagan.crawlers.bilibili.web.web_crawler import BilibiliWebCrawler
from devgagan.crawlers.parser import parse_video_share_url, parse_video_id, VideoSource
from devgagan.core.func import chk_user, subscribe
from devgagan.utils import (
    get_random_string,
    DownloadTaskManager,
    AdvancedCookieManager
)
from devgagan.core.mongo import vip_db

logger = logging.getLogger(__name__)

# 初始化全局组件
task_manager = DownloadTaskManager()
cookie_manager = AdvancedCookieManager()

# 数据类定义
@dataclass
class PlatformHandler:
    pattern: re.Pattern
    processor: Callable
    need_cookie: bool = False

@dataclass
class VideoInfo:
    title: str
    download_url: str
    resolution: str
    size: int

# 平台处理器配置
PLATFORM_HANDLERS = [
    PlatformHandler(
        pattern=re.compile(r"(douyin\.com|tiktok\.com)"),
        processor="process_short_video"
    ),
    PlatformHandler(
        pattern=re.compile(r"(bilibili\.com|b23\.tv)"),
        processor="process_bilibili"
    ),
    PlatformHandler(
        pattern=re.compile(r"(youtube\.com|youtu\.be)"),
        processor="process_youtube",
        need_cookie=True
    ),
    PlatformHandler(
        pattern=re.compile(r"(.)"),
        processor="process_common"
    )
]

BATCH_PLATFORM_HANDLERS = [
    PlatformHandler(
        pattern=re.compile(r"(douyin\.com|tiktok\.com)"),
        processor="batch_process_douyin"
    ),
    PlatformHandler(
         pattern=re.compile(r"(kuaishou\.com|v\.kuaishou\.com)"),
        processor="batch_process_kuaishou"
    ),
    PlatformHandler(
        pattern=re.compile(r"(.)"),
        processor="batch_process_common",
        need_cookie=True
        ),
    ]

class BaseProcessor:
    def __init__(self, message, vip_only=False, cookie_type="header"):
        self.message = message
        self.user_id = message.chat.id
        self.only_vip = vip_only
        self.cookie_type = cookie_type

    async def _base_check(self):
        """基础检查"""
        if await subscribe(app, self.message) == 1:
            return False
        if not await self._check_privilege():
            return False
        if task_manager.is_user_busy(self.user_id):
            await self.message.reply("已有进行中的下载任务，请等待完成")
            return False

        can_proceed, response_message = await check_interval(self.user_id, await chk_user(self.message, self.user_id))
        if not can_proceed:
            await self.message.reply(response_message)
            return False
        return True

    async def _check_privilege(self):
        """用户权限验证"""
        if self.user_id in OWNER_ID:
            logger.info(f"owner {self.user_id}")
            return True
        vip = await vip_db.check_vip(self.user_id)
        if vip and vip.get("user_id") and vip.get("user_id") == self.user_id:
            logger.info(f"vip user {self.user_id}")
            return True
        if await is_user_verified(self.user_id):
            logger.info(f"trial user {self.user_id}")
            return True
        if self.only_vip:
            await self.message.reply("请购买会员或使用/tryvip获取体验资格")
            return False
        else:
            quota = await AsyncOperationTracker(MONGO_DB).check_user_quota(self.user_id)
            if not quota:
                await self.message.reply("今天免费下载次数已用完，请明天再试或者购买会员享受无限制下载")
                return False
        return True

    def _match_platform_handler(self, url: str) -> Optional[PlatformHandler]:
        """匹配平台处理器"""
        for handler in PLATFORM_HANDLERS:
            if handler.pattern.search(url):
                return handler
        return None

    async def _send_resultx(self, video_infos: List[VideoInfo]):
        if len(video_infos) == 0:
            return

        clean_title = video_infos[0].title
        header = f"🎬️ {clean_title}\n\n为您找到了以下下载资源：\n\n"
        message_chunks = [header]
        entities = []
        current_offset = self._utf16_len(header)  # 从header之后开始计数

        uniq = {}
        count = 1
        for idx, video in enumerate(video_infos, 1):
            if video.resolution in uniq:
                continue
            uniq[video.resolution] = 1
            size_str = self._format_size(video.size)
            # 构建每部分文本
            number_line = f"{count}. "
            info_line = f"📺 {video.resolution}  📦 {size_str} "
            link_line = " ⬇️下载链接\n\n"
            full_block = number_line + info_line + link_line

            link_prefix = " ⬇️"
            link_start = (
                current_offset 
                + self._utf16_len(number_line) 
                + self._utf16_len(info_line) 
                + self._utf16_len(link_prefix)
            )
            entities.append(MessageEntity(
                type=enums.MessageEntityType.TEXT_LINK,
                offset=link_start,
                length=4,  # "下载链接"固定4字符
                url=video.download_url
            ))

            message_chunks.append(full_block)
            current_offset += self._utf16_len(full_block)
            count += 1

        full_text = "".join(message_chunks).strip()

        await self.message.reply(
            text=full_text,
            entities=entities,
            parse_mode=enums.ParseMode.DISABLED
        ) 

    def _utf16_len(self, s: str) -> int:
        """计算字符串的 UTF-16 代码单元数量（Telegram 实体计算标准）"""
        return len(s.encode('utf-16-le')) // 2

    def _format_size(self, size_bytes: int) -> str:
        """智能转换文件大小单位"""
        if size_bytes < 1024**2:  # <1MB
            return f"{size_bytes/1024:.1f}KB"
        if size_bytes < 1024**3:  # <1GB
            return f"{size_bytes/(1024**2):.1f}MB"
        return f"{size_bytes/(1024**3):.1f}GB"

    async def process(self, url: str):
        """主处理流程"""
        if not await self._base_check():
            return
        try:
            await task_manager.add_task(self.user_id)
            handler = self._match_platform_handler(url)
            if not handler:
                return await self.message.reply("暂不支持该平台")

            await getattr(self, handler.processor)(url)
            await set_interval(self.user_id)
        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)
            await self.message.reply(f"处理失败: {str(e)}")
        finally:
            await task_manager.remove_task(self.user_id)

class BatchProcessor(BaseProcessor):
    def __init__(self, message, vip_only=True, cookie_type="header"):
        self.message = message
        self.user_id = message.chat.id
        self.only_vip = vip_only
        self.cookie_type = cookie_type

    def _match_platform_handler(self, url: str) -> Optional[PlatformHandler]:
        """匹配平台处理器"""
        for handler in BATCH_PLATFORM_HANDLERS:
            if handler.pattern.search(url):
                return handler
        return None

    async def process(self, url: str, download_count: int):
        """主处理流程"""
        if not await self._base_check():
            return
        try:
            await task_manager.add_task(self.user_id)
            handler = self._match_platform_handler(url)
            if not handler:
                return await self.message.reply("暂不支持该平台")

            await getattr(self, handler.processor)(url, download_count)
            await set_interval(self.user_id)
        except Exception as e:
            logger.error(f"处理失败: {e}", exc_info=True)
            await self.message.reply(f"处理失败: {str(e)}")
        finally:
            await task_manager.remove_task(self.user_id)

    async def batch_process_douyin(self, input_url: str, download_count: int):
        douyin_id = await DouyinWebCrawler().get_sec_user_id(input_url)
        if douyin_id == None or len(douyin_id) == 0:
            logger.error(f"input url is invalid: {input_url}")
            return await self.message.reply("非法url，请重新输入")
        current_count = 0
        page_size = 10
        cursor = 0
        while current_count < download_count:
            query_size = download_count - current_count
            if query_size > page_size:
                query_size = page_size
            api_data = await DouyinWebCrawler().fetch_user_post_videos(douyin_id, cursor, query_size)
            cursor = api_data['max_cursor']
            has_more = api_data['has_more']
            logger.info(f"cursor: {cursor}, hasmore:{has_more}")
            for video_data in api_data['aweme_list']:
                if current_count >= download_count:
                    break
                if 'video' in video_data:
                    videos = []
                    for item in video_data['video']['bit_rate']:
                        res = f"{item['play_addr']['width']}x{item['play_addr']['height']}"
                        v = VideoInfo(title=video_data['desc'],download_url=item['play_addr']['url_list'][2],size=item['play_addr']['data_size'],resolution=res)
                        videos.append(v)
                    await self._send_resultx(videos)
                    current_count += 1
                    time.sleep(0.5)
            if has_more != 1:
                break
            time.sleep(1)

    def get_kuaishou_userid(self, url: str) -> str:
        # 匹配两种常见URL格式（含PC端和移动端）
        patterns = [
            r'profile/([a-zA-Z0-9]+)',  # PC端示例：https://live.kuaishou.com/profile/xxx[9](@ref)
            r'short-video/([a-zA-Z0-9]+)'  # 移动端示例：https://v.kuaishou.com/xxx
            ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        logger.error(f"invalid kuaishou homepage url: {url}")
        return ""

    async def batch_process_kuaishou(self, input_url: str, download_count: int):
        user_id = self.get_kuaishou_userid(input_url)
        if len(user_id) == 0:
            return await self.message.reply(message.chat.id, "请输入正确的主页url")

        cookies = await cookie_manager.get_cookies(self.user_id, self.cookie_type)
        logger.info(cookies)
        if not cookies:
            cookies = ''
        logger.info(cookies)
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Cookie': cookies,
            'Host': 'www.kuaishou.com',
            'Origin': 'https://www.kuaishou.com',
            'Referer': f'https://www.kuaishou.com/profile/{user_id}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
            }

        current_count = 0
        pcursor = None
        while current_count < download_count:
            payload = {
                "operationName": "visionProfilePhotoList",
                "variables": {
                    "userId": user_id,
                    "pcursor": pcursor if pcursor else None,
                    "page": "profile"
                    },
                "query": KS_GRAPHQL_QUERY
            }
            response = requests.post(
                KS_GRAPHQL_URL,
                headers=headers,
                json=payload  # 自动处理Content-Type和JSON序列化
            )
            response.raise_for_status()
            data = response.json()
            if data.get('data'):
                for feed in data['data']['visionProfilePhotoList']['feeds']:
                    if current_count >= download_count:
                        break
                    videos = []
                    for item in feed['photo']['manifestH265']['adaptationSet']:
                        for info in item['representation']:
                            res = f"{info['width']}x{info['height']}"
                            v = VideoInfo(title=feed['photo']['caption'],download_url=info['url'],size=info['fileSize'],resolution=res)
                            videos.append(v)
                    await self._send_resultx(videos)
                    time.sleep(0.5)
                    current_count += 1
                pcursor = data['data']['visionProfilePhotoList']['pcursor']
            time.sleep(1)

    async def batch_process_common(self, input_url: str, download_count: int):
        cookies = await cookie_manager.get_cookies(self.user_id, "netscape")
        temp_cookie_path = None
        if cookies:
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
                temp_cookie_file.write(cookies)
                temp_cookie_path = temp_cookie_file.name
            logger.info(f"Created temporary cookie file at: {temp_cookie_path}")

        try:
        # 第一阶段：获取视频列表
            list_opts = {
                'noplaylist': False,
                'extract_flat': 'in_playlist',
                'playlist_items': f'1-{download_count}',
                'quiet': True,
                'no_warnings': True,
                'cookiefile': temp_cookie_path if temp_cookie_path else None,
            }

            with yt_dlp.YoutubeDL(list_opts) as ydl:
            # 获取用户主页视频列表
                list_info = ydl.extract_info(input_url, download=False)
                if not list_info or 'entries' not in list_info:
                    logger.error("❌ 未找到视频列表，请检查链接是否正确")
                    return await self.message.reply("❌ 未找到视频列表，请检查链接是否正确")

                videos = list_info['entries'][:download_count]
                logger.info(f"🎬 共找到 {len(videos)} 个视频\n")

            # 第二阶段：逐个获取视频详情
            detail_opts = {
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'cookiefile': temp_cookie_path if temp_cookie_path else None,
            }
            with yt_dlp.YoutubeDL(detail_opts) as detail_ydl:
                for idx, video in enumerate(videos, 1):
                    if not video.get('url'):
                        continue
                    try:
                        # 获取单个视频详情
                        video_info = detail_ydl.extract_info(video['url'], download=False)
                        if 'formats' in video_info:
                            best_url = next(
                                    (f['url'] for f in reversed(video_info['formats'])
                                        if f.get('url')),
                                    None
                            )
                            if best_url:
                                #await reply_dowload_url(message, best_url)
                                await self._send_result(download_url=best_url)
                            else:
                                logger.error("⚠️ 未找到有效下载地址")
                        else:
                            logger.error("⚠️ 该视频可能受访问限制")

                    except yt_dlp.utils.DownloadError as e:
                        logger.error(f"❌ 获取失败：{str(e)}")
                        continue
        except Exception as e:
            logger.error(f"发生严重错误：{str(e)}")
            return await self.message.reply(f"发生严重错误：{str(e)}")

class SingleProcessor(BaseProcessor):
    async def process_short_video(self, url: str):
        """处理短视频平台通用逻辑"""
        cookies = await cookie_manager.get_cookies(self.user_id, self.cookie_type)
        if not cookies:
            cookies = ""
        api_data = await HybridCrawler().hybrid_parsing_single_video(
            url, True, cookies
        )
        videos = []
        title = api_data['desc']
        for fm in api_data['video_data']['bit_rate']:
            res = f"{fm['play_addr']['width']}x{fm['play_addr']['height']}"
            v = VideoInfo(title=title,resolution=res,size=fm['play_addr']['data_size'],download_url=fm['play_addr']['url_list'][2])
            videos.append(v)
        #info = VideoInfo(title=api_data['desc'], download_url=api_data['video_data']['nwm_video_url_HQ'])
        await self._send_resultx(videos)

    async def process_common(self, url: str):
        video_info = await parse_video_share_url(url)
        info = VideoInfo(title=video_info.title,download_url=video_info.video_url,resolution="",size=0)
        if len(video_info.res) == 0:
            await self._send_resultx([info])
        else:
            infos = []
            for item in video_info.res:
                info = VideoInfo(title=video_info.title,download_url=item.url,resolution=item.resolution,size=item.size)
                infos.append(info)
            await self._send_resultx(infos)

    async def process_bilibili(self, url: str):
        """处理B站视频"""
        bv_id = await BilibiliWebCrawler().extract_bvid(url)
        if not bv_id:
            raise ValueError("无效的B站链接")

        api_data = await BilibiliWebCrawler().fetch_one_video(bv_id)
        cid = api_data['data']['cid']
        if cid == 0:
            raise ValueError("无效的视频CID")

        result = await BilibiliWebCrawler().fetch_video_playurl(bv_id, str(cid))
        infos = []
        for v in result['data']['dash']['video']:
            if v['width'] == 0 or v['height'] == 0:
                continue
            res = f"{v['width']}x{v['height']}"
            info = VideoInfo(title=api_data['data']['title'],download_url=v['baseUrl'],size=0,resolution=res)
            infos.append(info)
        await self._send_resultx(infos)

    async def process_youtube(self, url: str):
        """处理YouTube视频"""
        cookies = await cookie_manager.get_cookies(self.user_id, "netscape")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            if cookies:
                tmp_file.write(cookies)
                tmp_file.flush()

            ydl_opts = {
                'outtmpl': f"{get_random_string()}.%(ext)s",
                #'format': 'best',
                 'format': 'bestvideo+bestaudio',
                'cookiefile': tmp_file.name if cookies else None,
                'writethumbnail': True,
                'verbose': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                #logger.info(info)
                videos = []
                for fm in info['formats']:
                    if 'video_ext' in fm and fm['video_ext'] != 'none':
                        v = VideoInfo(title=info['title'],download_url=fm['url'],resolution=fm['resolution'],size=fm['filesize'])
                        videos.append(v)
                await self._send_resultx(videos)
    

# 命令处理器
@app.on_message(filters.command("single") & filters.private)
async def handle_single_command(client, message):
    if len(message.command) < 2:
        return await message.reply("用法: /single <视频链接>")
    
    processor = SingleProcessor(message)
    await processor.process(message.command[1])

@app.on_message(filters.command("userpost") & filters.private)
async def handle_multi_command(client, message):
    if len(message.command) < 3:
        return await message.reply("用法： /userpost <主页url> <下载视频数量>")
    processor = BatchProcessor(message)
    await processor.process(message.command[1], int(message.command[2]))

@app.on_message(filters.command("setcookie") & filters.private)
async def handle_set_cookie(client, message):
    cookie = ''
    while True:
        msg = await app.ask(message.chat.id, "请输入或者补充cookie, 没有补充请输入**done**")
        if msg.text == 'done':
            break
        cookie += msg.text
    await cookie_manager.set_cookies(message.chat.id, cookie, "header")
    await app.send_message(message.chat.id, "设置成功")

@app.on_message(filters.command("setytcookie") & filters.private)
async def handle_set_ytcookie(client, message):
    tmp = '' 
    while True:
        cookie = await app.ask(message.chat.id, "请输入或者补充cookie, 没有补充请输入**done**")
        if cookie.text == 'done':
            break
        lines = cookie.text.split('\n')
        if len(lines) < 4:
            return
        tmp += lines[0] + '\n'
        tmp += lines[1] + '\n'
        tmp += lines[2] + '\n'
        for line in lines[3:]:
            new_line = ''
            for col in line.split(' '):
                if len(col) == 0:
                    continue
                if len(new_line) > 0:
                    new_line += '\t'
                new_line += col
            new_line += '\n'
            tmp += new_line
    await cookie_manager.set_cookies(message.chat.id, tmp, "netscape")
    await app.send_message(message.chat.id, "设置成功")
