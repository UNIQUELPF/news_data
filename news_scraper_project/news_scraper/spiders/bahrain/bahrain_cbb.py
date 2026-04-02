# 巴林cbb爬虫，负责抓取对应站点、机构或栏目内容。

import json

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.bahrain.base import BahrainBaseSpider


class BahrainCbbSpider(BahrainBaseSpider):
    name = "bahrain_cbb"
    allowed_domains = ["cbb.gov.bh", "www.cbb.gov.bh"]
    target_table = "bhr_cbb"
    ajax_url = "https://www.cbb.gov.bh/wp-admin/admin-ajax.php"

    feeds = [
        {"mf-types[]": "press_release", "section": "press_release"},
        {"mf-categories[]": "treasury-bills", "section": "government_securities"},
    ]

    def start_requests(self):
        for feed in self.feeds:
            formdata = {
                "action": "get_media_posts",
                "mf-page": "1",
                "mf-display": "list",
            }
            formdata.update(feed)
            yield scrapy.FormRequest(
                self.ajax_url,
                formdata=formdata,
                callback=self.parse_listing,
                meta={"feed_section": feed["section"]},
            )

    def parse_listing(self, response):
        try:
            payload = json.loads(response.text)
        except Exception:
            return

        html = (payload or {}).get("html") or ""
        if not html:
            return

        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".cbb-media-list-item"):
            link = item.select_one(".media-item-title a")
            if not link:
                continue

            url = link.get("href")
            if not url:
                continue

            full_url = response.urljoin(url)
            if full_url in self.seen_urls:
                continue
            self.seen_urls.add(full_url)

            title = self._clean_text(link.get_text(" ", strip=True))
            title = title.rsplit("(", 1)[0].strip()
            date_text = self._clean_text(" ".join(item.select_one(".media-item-title-top").stripped_strings)) if item.select_one(".media-item-title-top") else ""
            publish_time = self._parse_datetime(date_text, languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            section = self._clean_text(" ".join(x.get_text(" ", strip=True) for x in item.select(".media-item-category span, .media-item-category"))).lower()
            yield scrapy.Request(
                full_url,
                callback=self.parse_detail,
                meta={
                    "title_hint": title,
                    "publish_time_hint": publish_time,
                    "section_hint": section or response.meta.get("feed_section", "media"),
                },
            )

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("title::text").get()
            or response.meta.get("title_hint")
        )
        title = title.replace("| CBB", "").strip()
        if not title:
            return

        publish_time = (
            self._parse_datetime(
                response.xpath("//meta[@property='article:published_time']/@content").get(),
                languages=["en"],
            )
            or self._parse_datetime(
                self._clean_text(" ".join(response.css("main ::text").getall()[:80])),
                languages=["en"],
            )
            or response.meta.get("publish_time_hint")
        )
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        content = self._extract_content(response, title)
        if not content:
            content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
        if not content:
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="Central Bank of Bahrain",
            language="en",
            section=response.meta.get("section_hint", "media"),
        )

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 25:
                continue
            if text == title_text or text.startswith("Published on "):
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
