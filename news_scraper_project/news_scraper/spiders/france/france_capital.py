import scrapy
from news_scraper.spiders.france.base import FranceBaseSpider

class FranceCapitalSpider(FranceBaseSpider):
    name = "france_capital"
    allowed_domains = ['capital.fr']
    start_urls = ['https://www.capital.fr/economie-politique']

    fallback_content_selector = "article, main, .article-content, .content"
    strict_date_required = False
    use_curl_cffi = True

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        seen = set()
        all_links = response.css("a[href]")
        for a_sel in all_links:
            href = a_sel.attrib.get("href", "").strip()
            if not href or any(x in href for x in ["javascript:", "mailto:", "#"]):
                continue

            url = response.urljoin(href).split("#")[0]

            # Limit to allowed domains
            if not any(dom in url for dom in self.allowed_domains):
                continue

            # Skip obvious static non-article resources
            if url.rstrip("/") == response.url.rstrip("/"):
                continue
            if any(url.lower().endswith(ext) for ext in [".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]):
                continue

            if url in seen:
                continue
            seen.add(url)

            if not self.should_process(url, None):
                continue

            yield scrapy.Request(url, callback=self.parse_detail)

    def parse_detail(self, response):
        if not isinstance(response, scrapy.http.TextResponse):
            return

        title = self._clean_text(
            response.xpath("//meta[@property='og:title']/@content").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
        )
        if not title:
            return

        publish_time = self._parse_datetime(
            response.xpath("//meta[@property='article:published_time']/@content").get()
            or response.xpath("//meta[@name='publication_date']/@content").get()
            or response.xpath("//meta[@name='date']/@content").get()
            or response.xpath("//time/@datetime").get()
            or response.css("time::attr(datetime)").get(),
            languages=["fr", "en"],
        )

        if not self.should_process(response.url, publish_time):
            return

        yield self._build_item(
            response=response,
            title=title,
            content="",
            publish_time=publish_time,
            author="Capital",
            language="fr",
            section="Economy",
        )
