import json
import logging
import re
from datetime import datetime

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
from pipeline.content_engine import ContentEngine

logger = logging.getLogger(__name__)

ARABIC_MONTHS = {
    'كانون الثاني': 1, 'شباط': 2, 'آذار': 3, 'نيسان': 4,
    'أيار': 5, 'حزيران': 6, 'تموز': 7, 'آب': 8,
    'أيلول': 9, 'تشرين الأول': 10, 'تشرين الثاني': 11, 'كانون الأول': 12
}


class LPGovSpider(SmartSpider):
    """Scrapes the Lebanese Parliament news section via its backend JSON API."""
    name = "lpgov"

    country_code = 'LBN'
    country = '黎巴嫩'
    source_timezone = 'Asia/Beirut'
    language = 'ar'
    start_date = '2024-01-01'

    allowed_domains = ["lp.gov.lb"]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 5,
        'DOWNLOADER_CLIENT_TLS_METHOD': "TLSv1.2",
    }

    @staticmethod
    def parse_arabic_date(d_str):
        if not d_str:
            return None
        d_str = d_str.replace('\xa0', ' ')
        m = None
        for ar_m, num_m in ARABIC_MONTHS.items():
            if ar_m in d_str:
                m = num_m
                break
        nums = re.findall(r'\d+', d_str)
        if m and len(nums) >= 2:
            try:
                return datetime(int(nums[-1]), m, int(nums[0]))
            except ValueError:
                pass
        return None

    def start_requests(self):
        yield scrapy.FormRequest(
            url="https://www.lp.gov.lb/Webservice.asmx/GetNews",
            formdata={"pageNumber": "1"},
            callback=self.parse_api_list,
            cb_kwargs={"page_num": 1},
            meta={'dont_verify_ssl': True},
            dont_filter=True,
        )

    def parse_api_list(self, response, page_num):
        try:
            items = json.loads(response.text)
        except Exception as e:
            logger.error(f"Failed to parse JSON on page {page_num}: {e}")
            return

        if not items:
            logger.info(f"Page {page_num} returned empty JSON. Stopping pagination.")
            return

        has_valid_item_in_window = False

        for record in items:
            date_str = record.get('PublishDate') or record.get('CreationDate')
            pub_time = self.parse_arabic_date(date_str)
            if pub_time:
                pub_time = self.parse_to_utc(pub_time)

            detail_url = f"https://www.lp.gov.lb/ContentRecordDetails?Id={record.get('Id')}"

            if not self.should_process(detail_url, pub_time):
                continue

            has_valid_item_in_window = True

            raw_html = record.get('Description') or record.get('Summary') or ""
            # Strip HTML tags to estimate text length for detail-page decision
            text_only = re.sub(r'<[^>]+>', ' ', raw_html).strip()
            title = record.get('Title', 'No Title').strip()

            if len(text_only) < 50 and record.get('Id'):
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_detail,
                    meta={
                        'dont_verify_ssl': True,
                        'publish_time_hint': pub_time,
                        'title_hint': title,
                    },
                    dont_filter=self.full_scan,
                )
            else:
                content_data = ContentEngine.process(
                    raw_html=raw_html, base_url=detail_url
                )
                item = {
                    **content_data,
                    "url": detail_url,
                    "title": title,
                    "raw_html": raw_html,
                    "publish_time": pub_time,
                    "language": self.language,
                    "section": record.get('CategoryName') or "News",
                    "country_code": self.country_code,
                    "country": self.country,
                    "author": "LP.gov",
                }
                yield item

        if has_valid_item_in_window:
            next_page = page_num + 1
            yield scrapy.FormRequest(
                url="https://www.lp.gov.lb/Webservice.asmx/GetNews",
                formdata={"pageNumber": str(next_page)},
                callback=self.parse_api_list,
                cb_kwargs={"page_num": next_page},
                meta={'dont_verify_ssl': True},
                dont_filter=True,
            )
        else:
            logger.info(
                f"Reached cutoff date or all items filtered on page {page_num}. Stopping."
            )

    def parse_detail(self, response):
        item = self.auto_parse_item(response)
        item['author'] = "LP.gov"
        item['section'] = "News"
        yield item
