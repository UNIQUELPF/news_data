# 荷兰企业局爬虫，抓取英文产业、投资与政策支持新闻。

import json
import urllib.parse

from bs4 import BeautifulSoup

import scrapy

from news_scraper.spiders.netherlands.base import NetherlandsBaseSpider


class NetherlandsRvoSpider(NetherlandsBaseSpider):
    name = "netherlands_rvo"

    country_code = 'NLD'

    country = '荷兰'
    allowed_domains = ["english.rvo.nl", "rvo.nl", "www.rvo.nl"]
    start_urls = ["https://english.rvo.nl/news"]

    # The listing page is a Next.js SPA; we use the internal JSON API
    # (https://english.rvo.nl/api/rvo/v1/search) which serves the same
    # article list that the client-side JS renders.  Detail pages are
    # server-rendered and can be fetched with _fetch_html.
    use_curl_cffi = True

    fallback_content_selector = "article, main"

    API_URL = (
        "https://english.rvo.nl/api/rvo/v1/search"
        "?sort_by=created&sort_order=DESC"
        "&f[0]=content_type%3Aarticle&items_per_page=50"
    )

    async def start(self):
        yield scrapy.Request(self.API_URL, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        if self._stop_pagination:
            return

        try:
            data = json.loads(response.text)
        except Exception as e:
            self.logger.error(f"Failed to parse API response: {e}")
            self._stop_pagination = True
            return

        results = data.get("searchResults") or []
        self.logger.info(f"API returned {len(results)} articles")

        if not results:
            self._stop_pagination = True
            return

        has_valid_item_in_window = False
        for entry in results:
            if self._stop_pagination:
                break

            url_path = entry.get("urlAlias") or ""
            if not url_path:
                continue
            full_url = response.urljoin(url_path)

            if not self.should_process(full_url):
                continue

            has_valid_item_in_window = True

            try:
                detail_html = self._fetch_html(full_url)
            except Exception as e:
                self.logger.warning(f"_fetch_html failed for {full_url}: {e}")
                continue

            fake_resp = self._make_response(full_url, detail_html)
            try:
                item = next(self.parse_detail(fake_resp))
                if item:
                    yield item
            except StopIteration:
                continue

        if not has_valid_item_in_window:
            self._stop_pagination = True

    def parse_detail(self, response):
        title = None
        publish_time = None
        content = None

        # Prefer __NEXT_DATA__ (clean, structured content embedded by Drupal SSR)
        page_data = self._extract_next_data_page(response)
        if page_data:
            title = self._clean_text(page_data.get("title"))
            created = page_data.get("created")
            if created:
                publish_time = self._parse_datetime(created, languages=["en"])
            content = self._extract_content_from_json(page_data)

        # Fall back to HTML-based extraction
        if not title:
            title = self._clean_text(
                response.xpath("//meta[@property='og:title']/@content").get()
                or response.css("h1::text").get()
                or response.css("title::text").get()
            )
        if not publish_time:
            publish_time = self._parse_datetime(
                response.xpath("//meta[@property='article:published_time']/@content").get()
                or self._clean_text(" ".join(response.css("body ::text").getall()[:100])),
                languages=["en"],
            )
        if not content:
            content = self._extract_content(response, ["article", "main", ".page-content", ".content"])

        if not title:
            self.logger.warning(f"No title for {response.url}")
            return

        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        if not content:
            self.logger.warning(f"No content for {response.url}")
            return

        yield self._build_item(
            response=response,
            title=title,
            content=content,
            publish_time=publish_time,
            author="RVO",
            language="en",
            section="economy",
        )

    # ------------------------------------------------------------------
    #  __NEXT_DATA__ helpers
    # ------------------------------------------------------------------

    def _extract_next_data_page(self, response):
        raw = response.css('script#__NEXT_DATA__::text').get()
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data.get("props", {}).get("pageProps", {}).get("page", {})
        except Exception as e:
            self.logger.warning(f"Failed to parse __NEXT_DATA__: {e}")
            return None

    def _extract_content_from_json(self, page_data):
        content_elements = page_data.get("contentElements") or []
        if not content_elements:
            return ""
        parts = []
        for ce in content_elements:
            if ce.get("type") == "wysiwyg" and ce.get("text"):
                text = self._clean_text(
                    BeautifulSoup(ce["text"], "html.parser").get_text(" ", strip=True)
                )
                if len(text) > 50:
                    parts.append(text)
            for child in ce.get("childElements") or []:
                if child.get("type") == "wysiwyg" and child.get("text"):
                    text = self._clean_text(
                        BeautifulSoup(child["text"], "html.parser").get_text(" ", strip=True)
                    )
                    if len(text) > 50:
                        parts.append(text)
        return "\n\n".join(parts)
