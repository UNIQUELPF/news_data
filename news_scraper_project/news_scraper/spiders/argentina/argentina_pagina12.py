# 阿根廷pagina12爬虫，负责抓取对应站点、机构或栏目内容。
import json
import re

import scrapy
from bs4 import BeautifulSoup
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷经济类来源
# 站点：Pagina12
# 入库表：arg_pagina12
# 语言：西班牙语


class ArgentinaPagina12Spider(SmartSpider):
    """阿根廷 Pagina 12 爬虫。

    抓取站点：https://www.pagina12.com.ar
    抓取栏目：economia
    入库表：arg_pagina12
    语言：西班牙语
    """

    name = "argentina_pagina12"


    country_code = "ARG"


    country = "阿根廷"
    language = "es"
    source_timezone = "America/Argentina/Buenos_Aires"
    allowed_domains = ["pagina12.com.ar"]
    # 当前 spider 对应的数据库表名。

    # 从经济栏目入口页开始抓取。
    start_urls = [
        "https://www.pagina12.com.ar/economia/",
    ]

    # 首次抓取的默认时间边界；后续优先按数据库里最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        },
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        # Pagina 12 的经济页里会混出其他文章，这里先抓年份型详情链接。
        article_links = response.css('a[href^="/2026/"]::attr(href), a[href^="/2025/"]::attr(href)').getall()

        for href in article_links:
            full_url = response.urljoin(href)
            publish_time = self._parse_date_from_url(full_url)
            if not self.should_process(full_url, publish_time):
                continue
            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={"publish_time_hint": publish_time},
                dont_filter=self.full_scan,
            )

    def parse_detail(self, response):
        if not self._is_economia_article(response):
            return

        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "Pagina 12"
        item["section"] = "economia"
        item["language"] = "es"

        if len(item.get("content_plain", "")) > 100:
            yield item

    def extract_content(self, response):
        data = self._get_fusion_data(response)
        if data:
            elements = data.get("content_elements") or []
            html_parts = []
            images = []
            for element in elements:
                if not isinstance(element, dict):
                    continue
                element_type = element.get("type")
                if element_type == "text" and element.get("content"):
                    html_parts.append(f"<p>{element['content']}</p>")
                elif element_type == "image":
                    image_url = (
                        (element.get("url") or "")
                        or (element.get("promo_items", {}).get("basic", {}).get("url") or "")
                    )
                    if image_url:
                        images.append(response.urljoin(image_url))

            if html_parts:
                content_cleaned = "<article>" + "\n".join(html_parts) + "</article>"
                soup = BeautifulSoup(content_cleaned, "html.parser")
                content_plain = soup.get_text(" ", strip=True)
                return {
                    "content_cleaned": content_cleaned,
                    "content_markdown": "\n\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")),
                    "content_plain": content_plain,
                    "images": images,
                }

        return super().extract_content(response)

    def _get_fusion_data(self, response):
        script = response.css("script#fusion-metadata::text").get()
        marker = "Fusion.globalContent="
        if script and marker in script:
            start = script.find(marker) + len(marker)
            end = script.find(";Fusion.globalContentConfig=", start)
            if end != -1:
                try:
                    return json.loads(script[start:end])
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    def _is_economia_article(self, response):
        data = self._get_fusion_data(response)
        if not data:
            return "/economia/" in response.url
        primary = data.get("taxonomy", {}).get("primary_section", {})
        return primary.get("path") == "/economia"

    def _parse_date_from_url(self, url):
        match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if not match:
            return None
        return self.parse_date("-".join(match.groups()))
