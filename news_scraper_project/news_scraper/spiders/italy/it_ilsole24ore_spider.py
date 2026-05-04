import scrapy
from scrapy_playwright.page import PageMethod
from news_scraper.spiders.smart_spider import SmartSpider


class ItIlsole24oreSpider(SmartSpider):
    name = "it_ilsole24ore"
    source_timezone = 'Europe/Rome'
    language = 'it'
    strict_date_required = False

    country_code = 'ITA'
    country = '意大利'

    allowed_domains = ["ilsole24ore.com"]

    start_urls = [
        "https://www.ilsole24ore.com/sez/economia/fondi-ue",
        "https://www.ilsole24ore.com/sez/economia/industria",
        "https://www.ilsole24ore.com/sez/economia/energia-e-ambiente",
    ]

    use_curl_cffi = True
    fallback_content_selector = '.atxt'

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "news_scraper.middlewares.CurlCffiMiddleware": 543,
            "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
        },
        "CURLL_CFFI_IMPERSONATE": "chrome120",
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True, "timeout": 60000},
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000 * 5,
    }

    def start_requests(self):
        """Launch listing pages with JS 'Load More' pagination controlled by cutoff_date."""
        if self.cutoff_date:
            target_date_str = self.cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            target_date_str = '2026-01-01'

        js_scroll = f"""
        async () => {{
            let cb = document.querySelector('#iubenda-cs-banner');
            if(cb) cb.remove();
            let nora = document.querySelector('.onesignal-customlink-container');
            if(nora) nora.remove();

            let targetDate = new Date('{target_date_str}');
            for(let i = 0; i < 50; i++) {{
                let times = document.querySelectorAll('time[datetime]');
                if(times.length > 0) {{
                    let lastTimeEl = times[times.length - 1];
                    let dateStr = lastTimeEl.getAttribute('datetime');
                    if(dateStr && new Date(dateStr) < targetDate) {{
                        break;
                    }}
                }}
                let btn = document.querySelector('.btn--collapse');
                if(btn) {{
                    btn.click();
                    await new Promise(r => setTimeout(r, 2000));
                }} else {{
                    break;
                }}
            }}
        }}
        """

        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("evaluate", js_scroll),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                callback=self.parse,
                dont_filter=True,
            )

    def parse(self, response):
        """Parse listing page after JS expansion. Extract links with approximate date pairing."""
        section_hint = self._get_section(response.url)

        # Extract article links (deduplicated, DOM-order preserved)
        raw_links = response.css('a[href^="/art/"]::attr(href)').getall()
        links = list(dict.fromkeys(raw_links))

        # Extract datetime values for approximate date pairing by DOM order.
        # Try XPath first (broader engine), then CSS, then any element with datetime.
        times = response.xpath('//time[@datetime]/@datetime').getall()
        if not times:
            times = response.css('time[datetime]::attr(datetime)').getall()
        if not times:
            times = response.xpath('//*[@datetime]/@datetime').getall()

        self.logger.info(
            f"Listing {response.url}: {len(links)} links, {len(times)} datetime attrs after expansion."
        )

        has_valid_item_in_window = False

        for i, link in enumerate(links):
            abs_url = response.urljoin(link)

            # Approximate date pairing by DOM position
            date_str = times[i] if i < len(times) else None
            publish_time = self.parse_date(date_str) if date_str else None

            if not self.should_process(abs_url, publish_time):
                continue

            has_valid_item_in_window = True

            yield scrapy.Request(
                abs_url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                    ],
                    "publish_time_hint": publish_time,
                    "section_hint": section_hint,
                },
                callback=self.parse_detail,
                dont_filter=self.full_scan,
            )

        if not has_valid_item_in_window:
            self.logger.info(
                f"No new articles in window for {response.url}; stopping this section."
            )

    @staticmethod
    def _get_section(url):
        """Derive a human-readable section label from the category URL."""
        if "fondi-ue" in url:
            return "Fondi UE"
        elif "industria" in url:
            return "Industria"
        elif "energia-e-ambiente" in url:
            return "Energia e Ambiente"
        return "Economia"

    def parse_detail(self, response):
        """Parse article detail page using SmartSpider's auto_parse_item."""
        item = self.auto_parse_item(
            response,
            title_xpath="//h1[contains(@class,'atitle')]/text()",
            publish_time_xpath="//time[@datetime]/@datetime",
        )

        item['author'] = item.get('author') or "Il Sole 24 Ore"
        item['section'] = response.meta.get('section_hint', 'Economia')

        yield item
