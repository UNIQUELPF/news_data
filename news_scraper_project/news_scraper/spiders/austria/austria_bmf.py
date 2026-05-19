# 奥地利bmf爬虫，负责抓取对应站点、机构或栏目内容。

import re

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利政府类来源
# 站点：BMF
# 入库表：aut_bmf
# 语言：德语


class AustriaBmfSpider(AustriaBaseSpider):
    name = "austria_bmf"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["bmf.gv.at", "www.bmf.gv.at"]
    start_urls = [
        "https://www.bmf.gv.at/presse/pressemeldungen/2026.html",
    ]

    fallback_content_selector = "article, main"
    strict_date_required = False

    MAX_PAGES = 10  # Year-based pagination, 10 years is more than enough

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        match = re.search(r"/(\d{4})\.html", response.url)
        current_year = int(match.group(1)) if match else 2026

        links = response.css('a[href*="/presse/pressemeldungen/"]::attr(href)').getall()
        valid_links = []
        next_year_url = None

        for href in links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if not full_url.endswith(".html"):
                continue
            if f"/{current_year}/" in full_url:
                valid_links.append(full_url)
            elif full_url.endswith(f"/{current_year-1}.html"):
                next_year_url = full_url

        # If we have no links for this year, we check if we should stop or try the next year directly.
        # But to be safe, if we don't have links and no next_year_url, we just stop.
        current_page = response.meta.get('page', 1)
        if not valid_links:
            if next_year_url and current_page < self.MAX_PAGES:
                self.logger.info(f"[{self.name}] No valid links on page {current_page} (Year {current_year}). Trying next year: {next_year_url}")
                yield scrapy.Request(
                    next_year_url,
                    callback=self.parse_listing,
                    meta={'page': current_page + 1}
                )
            else:
                self.logger.info(f"[{self.name}] No valid links to process on page {current_page} (Year {current_year}). Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'next_page_url': next_year_url
        }

        for url in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                meta={'shared_state': state}
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        next_page = state.get('next_page_url')
        if next_page and page < self.MAX_PAGES:
            self.logger.info(f"[{self.name}] Proceeding to page {page + 1} (Next Year): {next_page}")
            yield scrapy.Request(
                next_page,
                callback=self.parse_listing,
                meta={'page': page + 1}
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

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//time/@datetime").get()
            or response.xpath("//time/text()").get()
            or re.search(r"(\d{4}-\d{2}-\d{2})", response.text).group(1) if re.search(r"(\d{4}-\d{2}-\d{2})", response.text) else None,
            languages=["de", "en"],
        )

        if state:
            state['dates'].append(publish_time)

        if title and self.should_process(response.url, publish_time):
            content = self._extract_content(response)
            if not content:
                content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
            if content:
                yield self._build_item(
                    response=response,
                    title=title,
                    content=content,
                    publish_time=publish_time,
                    author="BMF",
                    language="de",
                    section="press-release",
                )

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("article") or soup.select_one("main") or soup.select_one("#content")
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)
