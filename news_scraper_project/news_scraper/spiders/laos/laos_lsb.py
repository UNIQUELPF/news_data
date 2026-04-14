# 老挝统计局爬虫，抓取统计局网站文章与统计新闻。
import scrapy
from bs4 import BeautifulSoup

from news_scraper.spiders.laos.base import LaosBaseSpider


class LaosLsbSpider(LaosBaseSpider):
    name = "laos_lsb"

    country_code = 'LAO'

    country = '老挝'
    allowed_domains = ["www.lsb.gov.la", "lsb.gov.la"]
    target_table = "lao_lsb"
    api_url = "https://www.lsb.gov.la/index.php?rest_route=/wp/v2/posts&per_page=12"

    def start_requests(self):
        yield scrapy.Request(self.api_url, callback=self.parse_api)

    def parse_api(self, response):
        try:
            posts = response.json()
        except Exception as exc:
            self.logger.error(f"Failed to decode LSB API response: {exc}")
            return

        for post in posts:
            url = post.get("link")
            if not url or url in self.seen_urls:
                continue

            publish_time = self._parse_datetime(post.get("date"), languages=["en"])
            if publish_time and not self.full_scan and publish_time < self.cutoff_date:
                continue

            self.seen_urls.add(url)
            title = self._clean_html(post.get("title", {}).get("rendered"))
            content = self._clean_html(post.get("content", {}).get("rendered"))
            excerpt = self._clean_html(post.get("excerpt", {}).get("rendered"))
            final_content = content or excerpt

            if not title or not final_content:
                continue

            item = self._build_item(
                response=self._make_response(url, final_content),
                title=title,
                content=final_content,
                publish_time=publish_time,
                author="Lao Statistics Bureau",
                language="lo",
                section="statistics",
            )
            item["url"] = url
            yield item

    def _clean_html(self, html):
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for unwanted in soup.select("script, style"):
            unwanted.decompose()
        return self._clean_text(soup.get_text("\n", strip=True))
