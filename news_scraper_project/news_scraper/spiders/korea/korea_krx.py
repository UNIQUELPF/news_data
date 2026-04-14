# 韩国交易所爬虫，负责抓取对应站点、机构或栏目内容。

from html import unescape

import requests
import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.korea.base import KoreaBaseSpider


class KoreaKrxSpider(KoreaBaseSpider):
    name = "korea_krx"

    country_code = 'KOR'

    country = '韩国'
    allowed_domains = ["global.krx.co.kr"]
    target_table = "kor_krx"
    board_id = "GLB0501070000"
    start_urls = ["http://global.krx.co.kr/board/GLB0501070000/bbs"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        list_response = requests.post(
            f"http://global.krx.co.kr/board/{self.board_id}/list",
            data={
                "bbsId": self.board_id,
                "bbsUrl": self.board_id,
                "curPage": "1",
                "searchType": "",
                "bbsSeq": "",
                "boardStyle": "blog",
                "listOrder": "new",
            },
            headers={"User-Agent": self.settings.get("USER_AGENT")},
            timeout=30,
        )
        list_response.raise_for_status()
        soup = BeautifulSoup(list_response.text, "html.parser")
        for link in soup.select("ul.datalist a[data-view]"):
            seq = self._clean_text(link.get("data-view"))
            title = self._clean_text(link.get_text(" ", strip=True))
            card = link.find_parent("li")
            date_text = self._clean_text(card.select_one(".blog-write-date").get_text(" ", strip=True) if card and card.select_one(".blog-write-date") else "")
            summary = self._clean_text(card.select_one(".blog-content").get_text(" ", strip=True) if card and card.select_one(".blog-content") else "")
            if not seq or not title:
                continue
            publish_time = self._parse_datetime(date_text, languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue
            url = f"http://global.krx.co.kr/board/{self.board_id}/view?bbsSeq={seq}"
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={"bbs_seq": seq, "list_title": title, "list_date": publish_time, "list_summary": summary},
                dont_filter=True,
            )

    def parse_detail(self, response):
        seq = response.meta["bbs_seq"]
        detail_response = requests.post(
            f"http://global.krx.co.kr/board/{self.board_id}/view",
            data={
                "bbsId": self.board_id,
                "bbsUrl": self.board_id,
                "bbsSeq": seq,
                "boardStyle": "blog",
                "listOrder": "new",
                "language": "en",
            },
            headers={"User-Agent": self.settings.get("USER_AGENT")},
            timeout=30,
        )
        detail_response.raise_for_status()
        detail_html = detail_response.text
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        title = self._clean_text(
            response.meta.get("list_title")
            or detail_soup.select_one("strong").get_text(" ", strip=True)
            if detail_soup.select_one("strong")
            else ""
        )
        if not title:
            return

        publish_time = response.meta.get("list_date")
        if publish_time and not self.full_scan and publish_time < self.cutoff_date:
            return

        textarea = detail_soup.select_one("textarea[name='contn']")
        content = self._clean_text(unescape(textarea.get_text("\n", strip=True)) if textarea else "")
        if not content:
            content = self._clean_text(response.meta.get("list_summary"))
        if not content:
            return

        yield self._build_item(
            response=response.replace(url=f"http://global.krx.co.kr/board/{self.board_id}/view?bbsSeq={seq}"),
            title=title,
            content=content,
            publish_time=publish_time,
            author="Korea Exchange",
            language="en",
            section="market",
        )
