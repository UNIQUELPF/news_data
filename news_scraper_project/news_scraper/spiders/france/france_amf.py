# 法国AMF爬虫，使用站点地图发现文章 URL。
# 列表页文章列表由 JavaScript 渲染，curl_cffi 无法抓取，
# 因此改用 sitemap.xml 发现文章链接。

import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from news_scraper.spiders.france.base import FranceBaseSpider

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class FranceAmfSpider(FranceBaseSpider):
    name = "france_amf"

    country_code = 'FRA'

    country = '法国'
    allowed_domains = ["amf-france.org", "www.amf-france.org"]
    start_urls = ["https://www.amf-france.org/fr/sitemap.xml"]

    fallback_content_selector = "article, main"
    strict_date_required = False

    def parse(self, response):
        root = ET.fromstring(response.text.encode())
        # 站点地图按 lastmod 升序排列（旧到新），从末尾开始处理（最新优先）
        url_elems = root.findall(f"{{{SITEMAP_NS}}}url")
        for url_elem in reversed(url_elems):
            loc = url_elem.find(f"{{{SITEMAP_NS}}}loc")
            lastmod = url_elem.find(f"{{{SITEMAP_NS}}}lastmod")
            if loc is None:
                continue
            url = loc.text.strip()
            # 只处理新闻稿和动态栏目
            if "/communiques-de-lamf/" not in url and "/actualites/" not in url:
                continue
            # 过滤掉栏目页自身，只保留具体文章
            if url.rstrip("/").endswith("/communiques-de-lamf") or url.rstrip("/").endswith("/actualites"):
                continue
            # 跳过 commission des sanctions 栏目
            if "/communiques-de-la-commission-des-sanctions" in url:
                continue

            publish_time = None
            if lastmod is not None and lastmod.text:
                publish_time = self._parse_datetime(lastmod.text.strip(), languages=["fr", "en"])
            if not self.should_process(url, publish_time):
                if publish_time and publish_time < self.cutoff_date:
                    break
                continue

            try:
                detail_html = self._fetch_html(url)
            except Exception as e:
                self.logger.warning(f"Failed to fetch {url}: {e}")
                continue

            item = next(self.parse_detail(self._make_response(url, detail_html)), None)
            if item:
                yield item

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or self._extract_publish_text(response),
            languages=["fr", "en"],
        )
        if not self.should_process(response.url, publish_time):
            return

        content = self._extract_content(response, ["article", "main"])
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        section = "press_release" if "/communiques/" in response.url else "news"
        yield self._build_item(
            response=response,
            title=title.replace("| AMF", "").strip(),
            content=content,
            publish_time=publish_time,
            author="AMF France",
            language="fr",
            section=section,
        )

    def _extract_publish_text(self, response):
        text = self._clean_text(" ".join(response.css("article ::text, main ::text").getall()[:160]))
        match = re.search(
            r"Publié le\s+(\d{1,2}\s+[A-Za-zéûôîàèùç]+\s+\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return text
