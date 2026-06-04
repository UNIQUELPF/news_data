import re

import scrapy

from news_scraper.spiders.usa.business_media_base import USABusinessMediaSpider


class USABEAReleasesSpider(USABusinessMediaSpider):
    name = "usa_bea_releases"
    source_name = "Bureau of Economic Analysis Current Releases"
    organization = "Bureau of Economic Analysis"
    allowed_domains = ["bea.gov"]
    fallback_content_selector = "main, article, .field--name-body, .region-content"
    section_name = "Economic Releases"
    start_urls = ["https://www.bea.gov/news/current-releases"]
    include_url_patterns = ("/news/20",)
    start_date = "2026-01-01"

    custom_settings = {
        **USABusinessMediaSpider.custom_settings,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    def parse(self, response):
        has_valid_item_in_window = False
        for row in response.css("tr"):
            href = row.css("a[href*='/news/20']::attr(href)").get()
            title = row.css("a[href*='/news/20']::text").get()
            if not href:
                continue
            text = " ".join(row.css("::text").getall())
            date_match = re.search(
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
                text,
            )
            publish_time = self.parse_date(date_match.group(0)) if date_match else None
            if not publish_time:
                continue

            url = response.urljoin(href)
            if not self.should_process(url, publish_time):
                continue

            has_valid_item_in_window = True
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={
                    "title_hint": title,
                    "publish_time_hint": publish_time,
                    "section_hint": self.section_name,
                },
            )

        if has_valid_item_in_window:
            next_url = response.css("a[rel='next']::attr(href), .pager__item--next a::attr(href)").get()
            if next_url:
                yield response.follow(next_url, callback=self.parse)
