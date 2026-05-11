# 吉尔吉斯斯坦 Tazabek 财经新闻爬虫，抓取站点首页的经济与投资文章。

import re

import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.kyrgyzstan.base import KyrgyzstanBaseSpider


class KyrgyzstanTazabekSpider(KyrgyzstanBaseSpider):
    name = "kyrgyzstan_tazabek"

    country_code = 'KGZ'

    country = '吉尔吉斯斯坦'
    allowed_domains = []
    start_urls = ["data:,kyrgyzstan_tazabek_start"]
    source_url = "https://www.tazabek.kg/"

    fallback_content_selector = "article, main"

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        html = self._fetch_html(self.source_url)
        has_valid_item_in_window = False
        for href in re.findall(r'href="(/news:\d+[^"]*)"', html):
            full_url = "https://www.tazabek.kg" + href.split("?")[0]
            if not self.should_process(full_url):
                continue
            try:
                detail_html = self._fetch_html(full_url)
            except Exception:
                continue
            item = next(self.parse_detail(self._make_response(full_url, detail_html)), None)
            if self._stop_pagination:
                break
            if item:
                has_valid_item_in_window = True
                yield item

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
        )
        title = re.sub(r"\s*—\s*Tazabek$", "", title).strip()
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._extract_first_match(response.text, r"(\d{2}:\d{2},\s*\d{1,2}\s+[^\s]+\s+\d{4})"),
            languages=["ru"],
        )
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        content = self._extract_content(response, [".content", "main", "article"])
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Tazabek",
            language="ru",
            section="economy",
        )

    def _extract_first_match(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    def _extract_content(self, response, selectors):
        soup = BeautifulSoup(response.text, "html.parser")
        # Use tazabek-specific selectors that target the article body more precisely
        # then fall back to the passed-in selectors
        custom = [".article-text #native-reklama", ".article-text"]
        for selector in custom + list(selectors or []):
            root = soup.select_one(selector)
            if not root:
                continue
            for unwanted in root.select(
                "script, style, nav, footer, header, aside, form, "
                ".share, .breadcrumb, .gc-byline, .pagedetails, .gc-stp-stp"
            ):
                unwanted.decompose()
            parts = []
            for node in root.find_all(["p", "li", "h2", "h3", "td", "th"], recursive=True):
                text = self._clean_text(node.get_text(" ", strip=True))
                if not text or len(text) < 20:
                    continue
                if text not in parts:
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)
        return ""
