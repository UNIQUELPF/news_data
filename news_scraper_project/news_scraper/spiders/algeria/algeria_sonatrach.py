# 阿尔及利亚sonatrach爬虫，负责抓取对应站点、机构或栏目内容。

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

# 阿尔及利亚官方企业类来源
# 站点：Sonatrach
# 入库表：dza_sonatrach
# 语言：英语


class AlgeriaSonatrachSpider(SmartSpider):
    """阿尔及利亚国家石油公司 Sonatrach 爬虫。 国有企业官方来源

    抓取站点：https://sonatrach.com
    抓取栏目：Press Releases
    入库表：dza_sonatrach
    语言：英语
    """

    name = "algeria_sonatrach"


    country_code = "DZA"


    country = "阿尔及利亚"
    language = "en"
    source_timezone = "Africa/Algiers"
    allowed_domains = ["sonatrach.com"]

    fallback_content_selector = ".entry-content, article, main"

    start_urls = [
        "https://sonatrach.com/en/category/press-releases/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }
    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_listing, dont_filter=True)

    def parse_listing(self, response):
        article_links = response.css("article a::attr(href), .entry-title a::attr(href), h2 a::attr(href)").getall()

        has_valid_item_in_window = False
        for href in article_links:
            full_url = response.urljoin(href)
            if not self.should_process(full_url) or "/category/" in full_url or "/wp-content/uploads/" in full_url:
                continue
            has_valid_item_in_window = True
            yield scrapy.Request(full_url, callback=self.parse_detail, dont_filter=self.full_scan)

        if self._stop_pagination:
            return

        if has_valid_item_in_window:
            next_page = response.css("a.next.page-numbers::attr(href), a[rel='next']::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_listing)

    def extract_content(self, response):
        """Custom BS4 extraction: sonatrach uses .entry-content.clear with astra theme."""
        soup = BeautifulSoup(response.text, "lxml")
        content_area = soup.select_one(".entry-content.clear")
        if not content_area:
            return super().extract_content(response)

        for tag in content_area.find_all(
            ["script", "style", "nav", "footer", "header", "aside", "form", "button", "iframe"]
        ):
            tag.decompose()

        # Collect images
        images = []
        for img in content_area.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy-src")
            if src:
                alt = img.get("alt", "")
                images.append({"url": urljoin(response.url, src), "alt": alt})

        # Normalize images
        for img in content_area.find_all("img"):
            src = img.get("src")
            if src:
                img["src"] = urljoin(response.url, src)
            alt = img.get("alt", "")
            img.attrs = {"src": img.get("src", ""), "alt": alt}

        # Normalize links
        for a in content_area.find_all("a"):
            href = a.get("href")
            if href:
                a["href"] = urljoin(response.url, href)
            a.attrs = {"href": a.get("href", "#")}

        content_cleaned = str(content_area)
        content_markdown = md(content_cleaned, strip=["script", "style", "iframe", "object", "embed"])
        content_plain = content_area.get_text(separator=" ", strip=True)

        return {
            "content_cleaned": content_cleaned.strip(),
            "content_markdown": content_markdown.strip(),
            "content_plain": content_plain.strip(),
            "images": images,
        }

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        if not item.get("title") or not item.get("content_plain"):
            return

        publish_time = item.get("publish_time")
        if not self.should_process(response.url, publish_time):
            self._stop_pagination = True
            return

        # Spider-specific overrides
        item["author"] = "Sonatrach"
        item["section"] = "press-releases"
        item["language"] = "en"

        if len(item.get("content_plain", "")) > 100:
            yield item

