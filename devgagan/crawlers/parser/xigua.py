import json
import re

import fake_useragent
import httpx

from .base import BaseParser, VideoAuthor, VideoInfo


class XiGua(BaseParser):
    """
    西瓜视频
    """

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        headers = {
            "User-Agent": fake_useragent.UserAgent(os=["android"]).random,
            "Cookie":"UIFID_TEMP=3c3e9d4a635845249e00419877a3730e2149197a63ddb1d8525033ea2b3354c2f6e6bc63256e365a0278a6c355d49eaf1bdf59db8b019aa5bb001717a391d38a1efe2dab39be713f7b075cfa70b211a5; fpk1=U2FsdGVkX19NBG62qghrKHvdJHsVHbnKsUIdz6FPftFRLO+7XD6pnmeLtWPHn8GV8SLOGcirkSHGIdnmLQcK0Q==; fpk2=f1f6b29a6cc1f79a0fea05b885aa33d0; SEARCH_RESULT_LIST_TYPE=%22single%22; hevc_supported=true; ttwid=1%7CNMMgiT8GGF9pS4MhZBE2oZ-IvpQQxYaj3EgWnt7zc18%7C1741838638%7Cd851c4f45b34345b934059a1035dfc5348c3273e2b23044b0f036462ba37e939; csrf_session_id=cfc30c57d4bddbf1eebf19cb1cfbd84e; UIFID=3c3e9d4a635845249e00419877a3730e2149197a63ddb1d8525033ea2b3354c275ddb6b1f52edb733a18bfd2bbed7904a9aa8fff79246b012e78a4fd34059d1c79ff55aec4295817d83c6cbe180ff02154fc34d768812713e29a9336cedaf017d983c10e53fbe693b9d4508935b20ea57498f7547aaaa97b61f9a3557f966b80ea94d5a9e559636f820a11cd092ab970f556f23a4d9631c1f1bc8f21f3a68ded; s_v_web_id=verify_m8wosgr0_KW54cqr3_NkvN_4sgk_8rRY_jXyYqATcPQyK; douyin.com; passport_csrf_token=f486ce7c809338a996417d3f6b51a5d2; passport_csrf_token_default=f486ce7c809338a996417d3f6b51a5d2; volume_info=%7B%22isUserMute%22%3Afalse%2C%22isMute%22%3Atrue%2C%22volume%22%3A0.5%7D; __security_mc_1_s_sdk_crypt_sdk=07b5e97c-4c1b-bc43; bd_ticket_guard_client_web_domain=2; device_web_cpu_core=24; device_web_memory_size=8; architecture=amd64; passport_mfa_token=Cjd9Q%2FF0gAQp7UNVH%2F8GP8yIAoaKqTpt%2Fo6KxDstyZdAl0YL05GScOZvZwxUURofX2WiVa%2BUalJwGkoKPDd1D3m2Zq5ULwnaJm0tQ71N6tV%2BaMj82xjPz9f675FSKuhMYRfINsh%2F1Ne93s54tbUk8Rlz1XjZIyo5xxC6ve0NGPax0WwgAiIBA1jDEw0%3D; d_ticket=e763a7d07f5490c11a1583ab057cb44a30d2d; passport_assist_user=CkGlq8XapToKUiSGg3XRiJDG7wBRRqDFihFtTlKDmViEBVG3SI_j6viVNSeImT-Skkqf1-7NpVjPCdMr-nxuadVOUxpKCjy00d0_enaFTXUFOGhYIUbnEWdkBn0J3HKX3J5NRyvUPw2vMqCVxT3N1BB4-sWdBq5PPOlI8nmvX2h_b5YQ6LztDRiJr9ZUIAEiAQPwi-fA; n_mh=5sxPl3MC_XoODqKB8uOhqcDoN0NSX4s3m1ebjwblzO8; sid_guard=77c16c08695da0caa3c98705665cd784%7C1743404492%7C5184000%7CFri%2C+30-May-2025+07%3A01%3A32+GMT; uid_tt=cae7c07c1aa722f351b967c06e05375a; uid_tt_ss=cae7c07c1aa722f351b967c06e05375a; sid_tt=77c16c08695da0caa3c98705665cd784; sessionid=77c16c08695da0caa3c98705665cd784; sessionid_ss=77c16c08695da0caa3c98705665cd784; is_staff_user=false; sid_ucp_v1=1.0.0-KGU4ZmE1ZjcxMTlhYzgxZjI5NmQxM2FlYTJkOGYzYWNlN2U0NjM3NGMKIQibq5C2t82DBxDM-6i_BhjvMSAMMI3Z3b0GOAdA9AdIBBoCaGwiIDc3YzE2YzA4Njk1ZGEwY2FhM2M5ODcwNTY2NWNkNzg0; ssid_ucp_v1=1.0.0-KGU4ZmE1ZjcxMTlhYzgxZjI5NmQxM2FlYTJkOGYzYWNlN2U0NjM3NGMKIQibq5C2t82DBxDM-6i_BhjvMSAMMI3Z3b0GOAdA9AdIBBoCaGwiIDc3YzE2YzA4Njk1ZGEwY2FhM2M5ODcwNTY2NWNkNzg0; login_time=1743404492534; SelfTabRedDotControl=%5B%5D; _bd_ticket_crypt_cookie=6f657f96ae48a480c094e84ad711c12b; __security_mc_1_s_sdk_sign_data_key_web_protect=7d5cbefa-41a6-ad60; __security_mc_1_s_sdk_cert_key=765f508b-4bf7-a368; __security_server_data_status=1; __ac_nonce=067f88f920055f7b236c; __ac_signature=_02B4Z6wo00f01LCICfQAAIDBb9P6uxIdrYywqA1AAEvfbf; theme=%22light%22; dy_swidth=2560; dy_sheight=1440; stream_recommend_feed_params=%22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A2560%2C%5C%22screen_height%5C%22%3A1440%2C%5C%22browser_online%5C%22%3Atrue%2C%5C%22cpu_core_num%5C%22%3A24%2C%5C%22device_memory%5C%22%3A8%2C%5C%22downlink%5C%22%3A10%2C%5C%22effective_type%5C%22%3A%5C%224g%5C%22%2C%5C%22round_trip_time%5C%22%3A50%7D%22; strategyABtestKey=%221744342931.759%22; biz_trace_id=5c9fc388; FOLLOW_NUMBER_YELLOW_POINT_INFO=%22MS4wLjABAAAAQ3tWiPC5ubyJnbl4wOzZPP5l7aVQNmYdXdT8tqRLfH7gs6Vh8NueQ92EZsAFLOqm%2F1744387200000%2F0%2F1744342931991%2F0%22; is_dash_user=1; IsDouyinActive=true; home_can_add_dy_2_desktop=%221%22; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCTDhaOFZqS0h1WUdOcDZYcDgzRGxLdU5uN0pFYTdra0RMY3ViVVBGRnEyM2gwODFxZXBybkZGaUR6YWV4QXFGdkoxbFZYRld0OS81anJxRnl0cFFweEU9IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoyfQ%3D%3D; publish_badge_show_info=%220%2C0%2C0%2C1744343036933%22; passport_fe_beating_status=true; odin_tt=1306e37f833f466e77500daaf1ee36349f8d4413e509c19327cc4943854d59abdda0054f158c8f585bf9fe5ae4d697d3bcaf663521147a05e3942453fef1ccd4; SelectedFeedCache=3; download_guide=%221%2F20250411%2F0%22",
        }
        if share_url.startswith("https://www.ixigua.com/"):
            # 支持电脑网页版链接 https://www.ixigua.com/xxxxxx
            video_id = share_url.strip("/").split("/")[-1]
            return await self.parse_video_id(video_id)

        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(share_url, headers=headers)

        location_url = response.headers.get("location", "")
        video_id = location_url.split("?")[0].strip("/").split("/")[-1]
        if len(video_id) <= 0:
            raise Exception("failed to get video_id from share URL")

        return await self.parse_video_id(video_id)

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        # 注意： url中的 video_id 后面不要有 /， 否则返回格式不一样
        req_url = (
            f"https://m.ixigua.com/douyin/share/video/{video_id}"
            f"?aweme_type=107&schema_type=1&utm_source=copy"
            f"&utm_campaign=client_share&utm_medium=android&app=aweme"
        )

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(req_url, headers=self.get_default_headers())
            response.raise_for_status()

        pattern = re.compile(
            pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
            flags=re.DOTALL,
        )
        find_res = pattern.search(response.text)

        if not find_res or not find_res.group(1):
            raise ValueError("parse video json info from html fail")

        json_data = json.loads(find_res.group(1).strip())
        original_video_info = json_data["loaderData"]["video_(id)/page"]["videoInfoRes"]

        # 如果没有视频信息，获取并抛出异常
        if len(original_video_info["item_list"]) == 0:
            err_detail_msg = "failed to parse video info from HTML"
            if len(filter_list := original_video_info["filter_list"]) > 0:
                err_detail_msg = filter_list[0]["detail_msg"]
            raise Exception(err_detail_msg)

        data = original_video_info["item_list"][0]
        video_url = data["video"]["play_addr"]["url_list"][0].replace("playwm", "play")

        video_info = VideoInfo(
            video_url=video_url,
            cover_url=data["video"]["cover"]["url_list"][0],
            title=data["desc"],
            author=VideoAuthor(
                uid=data["author"]["unique_id"],
                name=data["author"]["nickname"],
                avatar=data["author"]["avatar_thumb"]["url_list"][0],
            ),
        )
        return video_info
