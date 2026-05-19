# 阿曼daily爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.oman.base import OmanBaseSpider


class OmanDailySpider(OmanBaseSpider):
    """阿曼日报经济栏目。

    站点：https://www.omandaily.om
    栏目：الاقتصادية
    入库表：omn_oman_daily
    """

    name = "oman_daily"

    country_code = 'OMN'

    country = '阿曼'
    allowed_domains = ["omandaily.om", "www.omandaily.om"]
    start_urls = [
        "https://www.omandaily.om/morearticles/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF%D9%8A%D8%A9",
    ]
    strict_date_required = False

    MAX_PAGES = 50

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, meta={"dont_verify_ssl": True}, dont_filter=True)

    def parse_listing(self, response):
        valid_links = []
        for href in response.css("a::attr(href)").getall():
            full_url = response.urljoin(href)
            if "/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF%D9%8A%D8%A9/na/" not in full_url and "/الاقتصادية/na/" not in full_url:
                continue
            if not self.should_process(full_url):
                continue
            valid_links.append(full_url)

        # De-duplicate links while preserving order
        seen = set()
        unique_links = []
        for l in valid_links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)

        current_pgno = int(re.search(r"pgno=(\d+)", response.url).group(1)) if "pgno=" in response.url else 1
        if not unique_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_pgno}. Stopping.")
            return

        next_pgno = current_pgno + 1
        next_page_relative = None
        for a in response.css(".pagination a"):
            href = a.css("::attr(href)").get()
            if href and f"pgno={next_pgno}" in href:
                next_page_relative = href
                break

        state = {
            'pending_count': len(unique_links),
            'dates': [],
            'page': current_pgno,
            'response_url': response.url,
            'next_page_url': next_page_relative
        }

        for url in unique_links:
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                meta={"dont_verify_ssl": True, 'shared_state': state}
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        next_page = state.get('next_page_url')
        if next_page and page < self.MAX_PAGES:
            next_page_full = response_urljoin_helper(response_url, next_page)
            self.logger.info(f"[{self.name}] Proceeding to page {page + 1}: {next_page_full}")
            yield scrapy.Request(
                next_page_full,
                callback=self.parse_listing,
                meta={"dont_verify_ssl": True, 'page': page + 1}
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, state['response_url']):
                    yield req

    def parse_detail(self, response):
        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
        )
        state = response.meta.get('shared_state')

        content = self._extract_content(response, title) if title and "الموقع الرسمي لجريدة عمان" not in title else None
        
        publish_time = self._parse_datetime(
            "".join(response.xpath("//body//text()[contains(., '2026') or contains(., '2025')][1]").getall()),
            languages=["ar"],
        ) if content else None

        if state:
            state['dates'].append(publish_time)

        if content and self.should_process(response.url, publish_time):
            yield self._build_item(
                response=response,
                title=title.replace(" - الموقع الرسمي لجريدة عمان", "").strip(),
                content=content,
                publish_time=publish_time,
                author="Oman Daily",
                language="ar",
                section="economy",
            )

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req

def response_urljoin_helper(base_url, relative_url):
    from urllib.parse import urljoin
    return urljoin(base_url, relative_url)

    def _extract_content(self, response, title):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("main") or soup.select_one("article") or soup.body
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related"):
            unwanted.decompose()

        title_text = self._clean_text(title)
        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 20:
                continue
            if text == title_text or text == "الاقتصادية":
                continue
            if "الموقع الرسمي لجريدة عمان" in text:
                continue
            if text not in parts:
                parts.append(text)

        return "\n\n".join(parts)
