import scrapy
from news_scraper.spiders.smart_spider import SmartSpider


class ItMefSpider(SmartSpider):
    name = "it_mef"

    country_code = 'ITA'
    country = '意大利'
    language = 'it'
    source_timezone = 'Europe/Rome'
    use_curl_cffi = True

    # List-page dates are "MM/DD/YYYY" (e.g. "04/27/2026")
    dateparser_settings = {'DATE_ORDER': 'MDY'}

    allowed_domains = ["mef.gov.it"]

    list_url = "https://www.mef.gov.it/en/ufficio-stampa/notizie.html"

    fallback_content_selector = "div#pageContent"

    custom_settings = {
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5
    }

    def start_requests(self):
        yield scrapy.Request(
            self.list_url,
            callback=self.parse_list,
            meta={'page': 1},
            dont_filter=True
        )

    def parse_list(self, response):
        # Each article is inside a Bootstrap card:
        #   div.card-wrapper > div.card > div.card-body
        #     p.card-title.h5  -> date  (MM/DD/YYYY)
        #     p.card-text > a  -> link  (/en/inevidenza/...)
        cards = response.css('div.card-body')

        has_valid_item_in_window = False

        for card in cards:
            link_el = card.css('a[href*="/en/inevidenza/"]')
            href = link_el.css('::attr(href)').get()
            if not href or href.endswith('.html'):
                continue

            url = response.urljoin(href)

            title_hint = link_el.css('::attr(aria-label)').get() or link_el.css('::text').get()
            if title_hint:
                title_hint = title_hint.strip()

            date_str = card.css('p.card-title.h5::text').get()
            if date_str:
                date_str = date_str.strip()
            publish_time = self.parse_date(date_str) if date_str else None

            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    'title_hint': title_hint,
                    'publish_time_hint': publish_time,
                    'section_hint': 'Ufficio Stampa',
                }
            )

        # Pagination: only continue when we found items inside the window
        if has_valid_item_in_window:
            next_pages = response.css(
                'a.page-link-precsucc::attr(href), '
                'a[aria-label^="Go to page"]::attr(href)'
            ).getall()
            for np in set(next_pages):
                if 'page=' in np:
                    yield response.follow(np, self.parse_list)

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath=(
                "//h2[contains(@class,'fContent')]//text() "
                "| //h1[contains(@class,'fContent')]//text()"
            ),
            publish_time_xpath="//small[contains(@class,'text-date')]//text()",
        )

        item['author'] = "Ministero dell'Economia e delle Finanze"
        item['section'] = response.meta.get('section_hint', 'Ufficio Stampa')

        yield item
