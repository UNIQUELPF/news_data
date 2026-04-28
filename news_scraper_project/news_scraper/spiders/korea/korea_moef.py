# 韩国经济财政部爬虫，抓取英文新闻 RSS 列表并入库。
import re
from html import unescape

import scrapy

from news_scraper.spiders.korea.base import KoreaBaseSpider


class KoreaMoefSpider(KoreaBaseSpider):
    name = "korea_moef"

    country_code = 'KOR'

    country = '韩国'
    allowed_domains = ["english.moef.go.kr"]
    rss_url = "http://english.moef.go.kr/pc/engmosfrss.do?boardCd=N0001"
    start_urls = [rss_url]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_feed, dont_filter=True)

    def parse_feed(self, response):
        item_pattern = re.compile(r"<item>(.*?)</item>", re.S)
        link_pattern = re.compile(r"<link>(.*?)</link>", re.S)
        title_pattern = re.compile(r"<title>(.*?)</title>", re.S)
        desc_pattern = re.compile(r"<description>(.*?)</description>", re.S)
        date_pattern = re.compile(r"<dc:date>(.*?)</dc:date>", re.S)
        pub_pattern = re.compile(r"<pubDate>(.*?)</pubDate>", re.S)

        for item_html in item_pattern.findall(response.text):
            url_match = link_pattern.search(item_html)
            title_match = title_pattern.search(item_html)
            desc_match = desc_pattern.search(item_html)
            date_match = date_pattern.search(item_html)
            pub_match = pub_pattern.search(item_html)

            url = self._clean_text(unescape(url_match.group(1)) if url_match else "")
            title = self._clean_text(unescape(title_match.group(1)) if title_match else "")
            description = self._clean_text(unescape(desc_match.group(1)) if desc_match else "")
            publish_text = (
                unescape(date_match.group(1))
                if date_match
                else unescape(pub_match.group(1)) if pub_match else ""
            )
            publish_time = self._parse_datetime(unescape(publish_text), languages=["en"])
            if not url or not title:
                continue
            if "boardCd=N0001" not in url:
                continue
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            if not self.should_process(url):
                continue
            yield self._build_item(
                response=response.replace(url=url),
                title=title,
                content=description or title,
                publish_time=publish_time,
                author="Ministry of Economy and Finance",
                language="en",
                section="economy",
            )
