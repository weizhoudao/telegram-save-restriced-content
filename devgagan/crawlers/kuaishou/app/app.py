from asyncio import gather
from devgagan.crawlers.kuaishou.config import Config, Parameter
from devgagan.crawlers.kuaishou.extract import APIExtractor, HTMLExtractor
from devgagan.crawlers.kuaishou.link import DetailPage, Examiner
from devgagan.crawlers.kuaishou.manager import Manager
from devgagan.crawlers.kuaishou.request import Detail
from devgagan.crawlers.kuaishou.tools import ColorConsole,Cleaner

class KS:

    WIDTH = 50
    LINE = ">" * WIDTH

    cleaner = Cleaner()

    def __init__(self):
        self.console = ColorConsole()
        self.config_obj = Config(self.console)
        self.params = Parameter(
            console=self.console,
            cleaner=self.cleaner,
            **self.config_obj.read(),
        )
        self.config = None
        self.option = None
        self.manager = Manager(**self.params.run())
        self.examiner = Examiner(self.manager)
        self.detail_html = DetailPage(self.manager)
        self.extractor_api = APIExtractor(self.manager)
        self.extractor_html = HTMLExtractor(self.manager)
        self.running = True
        self.__function = None

    async def set_cookie(self, cookie: str):
        self.config_obj.write(self.config_obj.read() | {"cookie": cookie})

    async def extract_info(self, detail: str):
        urls = await self.examiner.run(detail)
        if not urls:
            self.console.warning(("提取作品链接失败"))
            return {}
        for url in urls:
            web, user_id, detail_id = self.examiner.extract_params(
                url,
            )
            if not detail_id:
                self.console.warning(("URL 解析失败：{url}").format(url=url))
                continue
            data = await self.__handle_detail_html(
                detail_id,
                url,
                web,
            )
            if not any(data):
                continue
            return data
        return {}

    async def __handle_detail_html(
        self,
        detail_id: str,
        url: str,
        web: bool,
    ) -> list[dict] | None:
        if html := await self.detail_html.run(url):
            return [
                self.extractor_html.run(
                    html,
                    detail_id,
                    web,
                )
            ]
