# 奥地利trend爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利经济类来源
# 站点：trend
# 入库表：aut_trend
# 语言：德语


class AustriaTrendSpider(AustriaBaseSpider):
    name = "austria_trend"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["trend.at", "www.trend.at"]
    start_urls = [
        "https://www.trend.at/unternehmen",
    ]
    strict_date_required = False

    MAX_PAGES = 50

    async def start(self):
        self._stop_pagination = False
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        links = response.css('a[href*="trend.at/unternehmen/"]::attr(href), a[href*="trend.at/finanzen/"]::attr(href)').getall()
        valid_links = []
        for href in links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url):
                continue
            if "/unternehmen/" not in full_url and "/finanzen/" not in full_url:
                continue
            valid_links.append(full_url)

        current_page = response.meta.get('page', 1)
        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        next_page = response.css("a[rel='next']::attr(href)").get()

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'next_page_url': next_page
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
            next_page_full = response_urljoin_helper(response_url, next_page)
            self.logger.info(f"[{self.name}] Proceeding to page {page + 1}: {next_page_full}")
            yield scrapy.Request(
                next_page_full,
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
            or response.xpath("//time/text()").get(),
            languages=["de", "en"],
        )

        if state:
            state['dates'].append(publish_time)

        if title and self.should_process(response.url, publish_time):
            content = self._extract_content(response)
            if not content:
                content = self._clean_text(response.xpath("//meta[@name='description']/@content").get())
            
            if content:
                section = "finanzen" if "/finanzen/" in response.url else "unternehmen"
                yield self._build_item(
                    response=response,
                    title=title,
                    content=content,
                    publish_time=publish_time,
                    author="trend",
                    language="de",
                    section=section,
                )

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req

def response_urljoin_helper(base_url, relative_url):
    from urllib.parse import urljoin
    return urljoin(base_url, relative_url)

    def _extract_content(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        root = (
            soup.select_one("article")
            or soup.select_one("[itemprop='articleBody']")
            or soup.select_one("main")
        )
        if not root:
            return ""

        for unwanted in root.select("script, style, nav, footer, header, aside, form, .share, .related, .paywall"):
            unwanted.decompose()

        parts = []
        for node in root.find_all(["p", "h2", "h3", "li"], recursive=True):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not text or len(text) < 30:
                continue
            if text not in parts:
                parts.append(text)
        return "\n\n".join(parts)

