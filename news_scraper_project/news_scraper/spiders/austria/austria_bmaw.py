# 奥地利bmaw爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.austria.base import AustriaBaseSpider


# 奥地利政府类来源
# 站点：BMAW
# 入库表：aut_bmaw
# 语言：德语


class AustriaBmawSpider(AustriaBaseSpider):
    name = "austria_bmaw"

    country_code = 'AUT'

    country = '奥地利'
    allowed_domains = ["bmaw.gv.at", "www.bmaw.gv.at", "bmwet.gv.at", "www.bmwet.gv.at"]
    start_urls = [
        "https://www.bmaw.gv.at/Presse/AktuellePressemeldungen.html",
    ]
    fallback_content_selector = "article, main"
    strict_date_required = False

    MAX_PAGES = 10

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        links = response.css('a[href*="/Presse/AktuellePressemeldungen/"]::attr(href)').getall()
        valid_links = []
        for href in links:
            full_url = response.urljoin(href)
            if full_url.endswith("AktuellePressemeldungen.html") or not self.should_process(full_url):
                continue
            if not full_url.endswith(".html"):
                continue
            valid_links.append(full_url)

        # Extract archive links and sort them descending by year
        archive_links = response.css('a[href*="/Presse/Archiv/"]::attr(href)').getall()
        archive_queue = []
        import re
        for a_href in archive_links:
            a_url = response.urljoin(a_href)
            # Find year in url, e.g. Archiv/2025.html or Archiv-2025.html
            yr_match = re.search(r"(\d{4})", a_url)
            if yr_match:
                year = int(yr_match.group(1))
                archive_queue.append((year, a_url))
        
        # Sort queue descending by year: latest year first
        archive_queue.sort(key=lambda x: x[0], reverse=True)
        queue_urls = [x[1] for x in archive_queue]

        current_page = response.meta.get('page', 1)
        if not valid_links:
            if queue_urls:
                next_archive = queue_urls[0]
                self.logger.info(f"[{self.name}] No valid links on listing page. Moving to first archive: {next_archive}")
                yield scrapy.Request(
                    next_archive,
                    callback=self.parse_archive,
                    meta={'page': current_page + 1, 'archive_queue': queue_urls[1:]}
                )
            else:
                self.logger.info(f"[{self.name}] No valid links and no archives. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'archive_queue': queue_urls
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
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination/archives.")
            return

        queue = state.get('archive_queue', [])
        if queue and page < self.MAX_PAGES:
            next_archive = queue[0]
            self.logger.info(f"[{self.name}] Proceeding to archive page: {next_archive}")
            yield scrapy.Request(
                next_archive,
                callback=self.parse_archive,
                meta={'page': page + 1, 'archive_queue': queue[1:]}
            )

    def _handle_detail_error(self, failure):
        self.logger.error(f"Detail request failed: {failure.value}")
        state = failure.request.meta.get('shared_state')
        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, state['response_url']):
                    yield req

    def parse_archive(self, response):
        links = response.css('a[href*="/Presse/AktuellePressemeldungen/"]::attr(href), a[href*="/Presse/Archiv/"]::attr(href)').getall()
        valid_links = []
        for href in links:
            full_url = response.urljoin(href)
            if not full_url.endswith(".html") or not self.should_process(full_url):
                continue
            if "/Presse/AktuellePressemeldungen/" in full_url:
                valid_links.append(full_url)

        queue = response.meta.get('archive_queue', [])
        current_page = response.meta.get('page', 1)

        if not valid_links:
            if queue and current_page < self.MAX_PAGES:
                next_archive = queue[0]
                self.logger.info(f"[{self.name}] No valid links in archive {response.url}. Moving to next archive: {next_archive}")
                yield scrapy.Request(
                    next_archive,
                    callback=self.parse_archive,
                    meta={'page': current_page + 1, 'archive_queue': queue[1:]}
                )
            else:
                self.logger.info(f"[{self.name}] No valid links in archive and no more archives. Stopping.")
            return

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'archive_queue': queue
        }

        for url in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                meta={'shared_state': state}
            )

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
            or response.re_first(r"(\d{4}-\d{2}-\d{2})"),
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
                    author="BMAW",
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
