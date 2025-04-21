import re

import fake_useragent
import httpx
import yaml

from .base import BaseParser, VideoAuthor, VideoInfo, ResolutionInfo


class RedBook(BaseParser):
    """
    小红书
    """

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        headers = {
            "User-Agent": fake_useragent.UserAgent(os=["windows"]).random,
        }
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(share_url, headers=headers)
            response.raise_for_status()

        pattern = re.compile(
            pattern=r"window\.__INITIAL_STATE__\s*=\s*(.*?)</script>",
            flags=re.DOTALL,
        )
        find_res = pattern.search(response.text)

        if not find_res or not find_res.group(1):
            raise ValueError("parse video json info from html fail")

        json_data = yaml.safe_load(find_res.group(1))

        note_id = json_data["note"]["currentNoteId"]
        # 验证返回：小红书的分享链接有有效期，过期后会返回 undefined
        if note_id == "undefined":
            raise Exception("parse fail: note id in response is undefined")
        data = json_data["note"]["noteDetailMap"][note_id]["note"]

        # 视频地址
        video_url = ""
        h264_data = (
            data.get("video", {}).get("media", {}).get("stream", {}).get("h264", [])
        )
        if len(h264_data) > 0:
            video_url = h264_data[0].get("masterUrl", "")

        # 获取图集图片地址
        image_list = []
        if len(video_url) <= 0:
            for img_item in data["imageList"]:
                # 个别图片有水印, 替换图片域名
                image_id = img_item["urlDefault"].split("/")[-1].split("!")[0]
                # 如果链接中带有 spectrum/ , 替换域名时需要带上
                spectrum_str = (
                    "spectrum/" if "spectrum" in img_item["urlDefault"] else ""
                )
                new_url = (
                    f"https://ci.xiaohongshu.com/{spectrum_str}{image_id}"
                    + "?imageView2/2/w/0/format/jpg"
                )
                image_list.append(new_url)

        video_info = VideoInfo(
            video_url=video_url,
            cover_url=data["imageList"][0]["urlDefault"],
            title=data["title"],
            images=image_list,
            author=VideoAuthor(
                uid=data["user"]["userId"],
                name=data["user"]["nickname"],
                avatar=data["user"]["avatar"],
            ),
        )
        for item in h264_data:
            r = ResolutionInfo(url=item['masterUrl'],size=item['size'],resolution=f"{item['width']}x{item['height']}")
            video_info.res.append(r)
        return video_info

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        raise NotImplementedError("小红书暂不支持直接解析视频ID")
