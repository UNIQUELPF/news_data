import scrapy
import json
from news_scraper.spiders.smart_spider import SmartSpider


class PortugalJornalNegociosSpider(SmartSpider):
    name = 'pt_jornaldenegocios'
    country_code = 'PRT'
    country = '葡萄牙'
    language = 'pt'
    source_timezone = 'Europe/Lisbon'
    allowed_domains = ['jornaldenegocios.pt']
    fallback_content_selector = '.texto_noticia'
    dateparser_settings = {"DATE_ORDER": "DMY"}

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Serial: one-by-one detail check
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
            'https': 'scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler',
        },
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }
    }

    async def start(self):
        base_url = 'https://www.jornaldenegocios.pt/economia'
        yield scrapy.Request(base_url, callback=self.parse_list, meta={'index': 0}, dont_filter=True)

    def parse_list(self, response):
        if self._stop_pagination:
            return

        articles = response.xpath('//a[contains(@href, "/detalhe/")]/@href').getall()
        has_valid_item_in_window = False

        for link in articles:
            full_url = response.urljoin(link)
            blocked_paths = (
                '/opiniao/autores/',
                '/institucional/',
                '/cofina-boost-solutions/',
                '/c-studio/',
                '/podcast/',
                '/multimedia/',
            )
            allowed_paths = ('/economia/', '/empresas/', '/mercados/')
            if any(path in full_url for path in blocked_paths):
                continue
            if not any(path in full_url for path in allowed_paths):
                continue
            if self.should_process(full_url):
                has_valid_item_in_window = True
                yield scrapy.Request(full_url, callback=self.parse_article)

        # Dynamic AJAX pagination
        if has_valid_item_in_window:
            current_index = response.meta.get('index', 0)
            next_index = current_index + 12
            next_url = f"https://www.jornaldenegocios.pt/economia/loadmore?friendlyUrl=economia&contentStartIndex={next_index}"
            yield scrapy.Request(
                next_url, callback=self.parse_list,
                meta={'index': next_index}, dont_filter=True
            )

    def _extract_article_schema(self, response):
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if candidate.get('@type') in ('NewsArticle', 'Article'):
                    return candidate
                graph = candidate.get('@graph')
                if isinstance(graph, list):
                    for entry in graph:
                        if isinstance(entry, dict) and entry.get('@type') in ('NewsArticle', 'Article'):
                            return entry
        return None

    def parse_article(self, response):
        schema = self._extract_article_schema(response) or {}
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
            publish_time_xpath=(
                "//meta[@property='article:published_time']/@content | "
                "//meta[@property='article: published_time']/@content"
            ),
        )
        if schema.get('headline'):
            item['title'] = schema['headline']
        raw_publish_time = (
            schema.get('datePublished')
            or schema.get('dateCreated')
            or schema.get('dateModified')
        )
        if raw_publish_time and not item.get('publish_time'):
            item['publish_time'] = self.parse_date(raw_publish_time)
        if not item.get('publish_time'):
            return
        if not self.should_process(response.url, item.get('publish_time')):
            self._stop_pagination = True
            return
        item['author'] = 'Jornal de Negócios'
        item['section'] = 'Economia/Empresas'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            yield item
