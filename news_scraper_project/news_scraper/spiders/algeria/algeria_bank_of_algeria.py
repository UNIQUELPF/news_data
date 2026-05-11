# 阿尔及利亚bank of algeria爬虫，负责抓取对应站点、机构或栏目内容。

import json
from datetime import datetime, timezone

import dateparser
import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from bs4 import BeautifulSoup

# 阿尔及利亚政府/监管类来源
# 站点：Bank of Algeria
# 入库表：dza_bank_of_algeria
# 语言：阿拉伯语


class AlgeriaBankOfAlgeriaSpider(SmartSpider):
    """阿尔及利亚中央银行爬虫。 政府/官方金融机构

    抓取站点：https://www.bank-of-algeria.dz
    抓取入口：WordPress 分类 API -> Communiqués de presse
    入库表：dza_bank_of_algeria
    语言：法语
    """

    name = "algeria_bank_of_algeria"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    start_date = "2026-01-01"
    allowed_domains = ["bank-of-algeria.dz", "www.bank-of-algeria.dz"]

    fallback_content_selector = ".entry-content, article"

    category_api = "https://www.bank-of-algeria.dz/wp-json/wp/v2/posts?categories=77&per_page=20&page={page}"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        yield scrapy.Request(self.category_api.format(page=1), callback=self.parse_api, meta={"page": 1}, dont_filter=True)

    def parse_api(self, response):
        posts = json.loads(response.text)
        if not posts:
            return

        has_valid_item_in_window = False

        for post in posts:
            title = self._clean_text(post.get("title", {}).get("rendered"))
            url = post.get("link")
            publish_time = self._parse_datetime(post.get("date"))
            if not publish_time and post.get('date_gmt'):
                publish_time = self._parse_datetime(post.get('date_gmt'))
            if not publish_time and post.get('date'):
                try:
                    publish_time = datetime.fromisoformat(post['date'].replace('Z', '+00:00').replace('T', ' ').split('+')[0])
                except (ValueError, TypeError):
                    pass
            content = self._extract_html_content(post.get("content", {}).get("rendered", ""))

            if not self.should_process(url, publish_time):
                continue
            if not title or not url or not content:
                continue

            has_valid_item_in_window = True

            item = {
                "url": url,
                "title": title,
                "content": content,
                "content_plain": content,
                "publish_time": publish_time or datetime.now(),
                "author": "Bank of Algeria",
                "language": "fr",
                "section": "communiques-de-presse",
                "scrape_time": datetime.now(),
            }
            yield item

        if has_valid_item_in_window:
            next_page = response.meta["page"] + 1
            yield scrapy.Request(self.category_api.format(page=next_page), callback=self.parse_api, meta={"page": next_page})

    def _extract_html_content(self, html):
        soup = BeautifulSoup(html, "html.parser")
        parts = []
        for node in soup.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 12:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

    def _parse_datetime(self, value):
        if not value:
            return None
        parsed = dateparser.parse(value, languages=["fr"], settings={"TIMEZONE": "UTC"})
        if not parsed:
            return None
        return parsed.replace(tzinfo=None)

    def _clean_text(self, value):
        if not value:
            return ""
        return " ".join(str(value).split()).strip()
