# 韩国银行爬虫，抓取英文新闻发布与新闻稿内容。
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup
from curl_cffi import requests

from news_scraper.spiders.korea.base import KoreaBaseSpider


class KoreaBokSpider(KoreaBaseSpider):
    name = "korea_bok"
    allowed_domains = ["www.bok.or.kr", "bok.or.kr"]
    target_table = "kor_bok"
    list_url = "https://www.bok.or.kr/eng/singl/newsDataEng/listCont.do"
    start_urls = ["https://www.bok.or.kr/eng/singl/newsDataEng/list.do?menuNo=400423"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        for page_index in range(1, 6):
            html = self._fetch_listing(page_index)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("li.bbsRowCls")
            if not rows:
                break

            page_has_new = False
            for row in rows:
                category = self._clean_text(
                    row.select_one(".i .t1").get_text(" ", strip=True)
                    if row.select_one(".i .t1")
                    else ""
                )
                if category != "Press Releases":
                    continue

                link = row.select_one("a.title")
                date_text = self._clean_text(
                    row.select_one(".dataInfo .date").get_text(" ", strip=True)
                    if row.select_one(".dataInfo .date")
                    else ""
                )
                title = self._clean_text(link.get_text(" ", strip=True) if link else "")
                href = link.get("href", "").strip() if link else ""
                if not title or not href:
                    continue

                publish_time = self._parse_datetime(date_text, languages=["en"])
                if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                    continue

                page_has_new = True
                url = urljoin("https://www.bok.or.kr", href)
                if url in self.seen_urls:
                    continue
                self.seen_urls.add(url)
                content = self._fetch_detail_content(url)
                if not content:
                    continue
                yield self._build_item(
                    response=response.replace(url=url),
                    title=title,
                    content=content,
                    publish_time=publish_time,
                    author="Bank of Korea",
                    language="en",
                    section="economy",
                )

            if not page_has_new and not self.full_scan:
                break

    def _fetch_detail_content(self, url):
        detail_response = requests.get(
            url,
            impersonate="chrome124",
            timeout=30,
            headers={"User-Agent": self.settings.get("USER_AGENT")},
        )
        detail_response.raise_for_status()
        soup = BeautifulSoup(detail_response.text, "html.parser")

        content_node = soup.select_one(".bd-view .content")
        content = self._html_to_text(str(content_node)) if content_node else ""
        if not content:
            content = self._clean_text(
                soup.select_one("meta[property='og:description']").get("content", "")
                if soup.select_one("meta[property='og:description']")
                else ""
            )
        return content

    def _fetch_listing(self, page_index):
        response = requests.post(
            self.list_url,
            data={
                "siteId": "eng",
                "menuNo": "400423",
                "targetDepth": "3",
                "syncMenuChekKey": "1",
                "pageIndex": str(page_index),
                "searchCnd": "1",
                "searchKwd": "",
                "sort": "1",
                "pageUnit": "10",
            },
            impersonate="chrome124",
            timeout=30,
            headers={"User-Agent": self.settings.get("USER_AGENT")},
        )
        response.raise_for_status()
        return response.text
