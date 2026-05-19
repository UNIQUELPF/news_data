# 阿根廷economia gov爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿根廷政府类来源
# 站点：Argentina Economia
# 入库表：arg_economia_gov
# 语言：西班牙语


class ArgentinaEconomiaGovSpider(SmartSpider):
    """阿根廷经济部官网爬虫。

    抓取站点：https://www.argentina.gob.ar/economia
    抓取栏目：noticias
    入库表：arg_economia_gov
    语言：西班牙语
    """

    name = "argentina_economia_gov"


    country_code = "ARG"


    country = "阿根廷"
    language = "en"
    source_timezone = "America/Argentina/Buenos_Aires"
    strict_date_required = False
    allowed_domains = ["argentina.gob.ar"]

    fallback_content_selector = "article, main"

    start_urls = [
        "https://www.argentina.gob.ar/economia/noticias",
    ]

    MAX_PAGES = 50

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        article_links = response.css('a[href*="/noticias/"]::attr(href)').getall()

        valid_links = []
        for href in article_links:
            full_url = response.urljoin(href)
            if "/noticias/" not in full_url or not self.should_process(full_url):
                continue
            valid_links.append(full_url)

        current_page = response.meta.get('page', 1)
        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        next_page = response.css("li.pager__item--next a::attr(href), a[rel='next']::attr(href)").get()

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
        item = self.auto_parse_item(response)
        state = response.meta.get('shared_state')
        pub_time = item.get("publish_time") if item else None

        if state:
            state['dates'].append(pub_time)

        if item and item.get("title") and item.get("content_plain") and self.should_process(response.url, pub_time):
            # Spider-specific overrides
            item["author"] = "Ministerio de Economía"
            item["section"] = "noticias"
            item["language"] = "es"

            if len(item.get("content_plain", "")) > 100:
                yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req

def response_urljoin_helper(base_url, relative_url):
    from urllib.parse import urljoin
    return urljoin(base_url, relative_url)

