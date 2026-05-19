# 阿尔及利亚aps爬虫，负责抓取对应站点、机构或栏目内容。

import re

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚经济类来源
# 站点：APS
# 入库表：dza_aps
# 语言：阿拉伯语


class AlgeriaApsSpider(SmartSpider):
    """阿尔及利亚 APS 爬虫。

    抓取站点：https://www.aps.dz
    抓取栏目：经济 -> 银行与金融
    入库表：dza_aps
    语言：阿拉伯语
    """

    name = "algeria_aps"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    strict_date_required = False
    source_timezone = "Africa/Algiers"
    allowed_domains = ["aps.dz"]
    # 当前 spider 对应的数据库表名。

    # 从 APS 经济栏目入口开始翻页抓取。
    start_urls = [
        "https://www.aps.dz/economie/banque-et-finances",
    ]

    fallback_content_selector = "article, main article, [itemprop='articleBody'], .article-content, .item-content, .entry-content, .post-content, .content, main"

    # 首次抓取的默认时间边界；后续会优先使用数据库里的最新时间做增量。

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    MAX_PAGES = 50

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        valid_links = []
        dates_hint = {}

        cards = response.xpath('//div[contains(@class, "flex-col") and .//a[contains(@href, "/economie/banque-et-finances/")]]')
        if not cards:
            article_links = response.xpath('//a[contains(@href, "/economie/banque-et-finances/")]/@href').getall()
            for href in article_links:
                full_url = response.urljoin(href)
                if self.should_process(full_url):
                    valid_links.append(full_url)
        else:
            for card in cards:
                href = card.xpath('.//a[contains(@href, "/economie/banque-et-finances/")]/@href').get()
                if not href:
                    continue
                full_url = response.urljoin(href)
                date_str = card.xpath('.//span[contains(@class, "text-xs")]/text()').get()
                pub_date = self.parse_date(date_str) if date_str else None
                if self.should_process(full_url, pub_date):
                    valid_links.append(full_url)
                    if pub_date:
                        dates_hint[full_url] = pub_date

        current_offset = self._extract_start_offset(response.url) or 0
        current_page = (current_offset // 10) + 1

        if not valid_links:
            self.logger.info(f"[{self.name}] No valid links to process on page {current_page}. Stopping.")
            return

        next_url = None
        next_page_link = response.xpath('//a[contains(@href, "/economie/banque-et-finances?start=")]/@href').get()
        if next_page_link:
            next_url = response.urljoin(next_page_link)
        else:
            pager_links = response.xpath('//a[contains(@href, "/economie/banque-et-finances")]/@href').getall()
            pick = self._pick_next_page(response.url, pager_links)
            if pick:
                next_url = response.urljoin(pick)

        state = {
            'pending_count': len(valid_links),
            'dates': [],
            'page': current_page,
            'response_url': response.url,
            'next_page_url': next_url
        }

        for url in valid_links:
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                errback=self._handle_detail_error,
                meta={'publish_time_hint': dates_hint.get(url), 'shared_state': state}
            )

    def _check_next_page(self, state, response_url):
        page = state['page']
        parsed_dates = [d for d in state['dates'] if d is not None]

        if parsed_dates and all(d < self.cutoff_date for d in parsed_dates):
            self.logger.info(f"[{self.name}] All articles on page {page} are older than cutoff {self.cutoff_date}. Stopping pagination.")
            return

        next_url = state.get('next_page_url')
        if next_url and page < self.MAX_PAGES:
            self.logger.info(f"[{self.name}] Proceeding to page {page + 1}: {next_url}")
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing
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
        hint_date = response.meta.get("publish_time_hint")
        if hint_date and item and not item.get("publish_time"):
            item["publish_time"] = hint_date

        pub_time = item.get("publish_time") if item else None

        if state:
            state['dates'].append(pub_time)

        if item and item.get("title") and item.get("content_plain") and self.should_process(response.url, pub_time):
            # Spider-specific overrides
            item["author"] = "APS"
            item["section"] = "banque-et-finances"
            item["language"] = "ar"

            if len(item.get("content_plain", "")) > 100:
                yield item

        if state:
            state['pending_count'] -= 1
            if state['pending_count'] == 0:
                for req in self._check_next_page(state, response.url):
                    yield req

    def _pick_next_page(self, current_url, hrefs):
        current_start = self._extract_start_offset(current_url)
        candidates = []

        for href in hrefs:
            start = self._extract_start_offset(href)
            if start is None:
                continue
            if start > current_start:
                candidates.append((start, href))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _extract_start_offset(self, url):
        match = re.search(r"[?&]start=(\d+)", url or "")
        if match:
            return int(match.group(1))
        return 0 if "banque-et-finances" in (url or "") else None

