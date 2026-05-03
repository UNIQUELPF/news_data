# 阿联酋wam爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from news_scraper.spiders.smart_spider import SmartSpider
import json
from datetime import datetime

class UaeWamSpider(SmartSpider):
    name = "uae_wam"

    country_code = 'ARE'
    country = '阿联酋'
    language = 'ar'
    source_timezone = 'Asia/Dubai'
    
    list_url = "https://www.wam.ae/api/app/views/GetViewByUrl"
    section_url = "https://www.wam.ae/api/app/views/GetSectionArticlesFDto"
    detail_url = "https://www.wam.ae/api/app/articles/GetArticleBySlug"

    allowed_domains = ["wam.ae"]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    def start_requests(self):
        # WAM is API-based, so we bypass normal start_urls
        yield scrapy.Request(
            url=f"{self.list_url}?url=ar/list/latest-news",
            callback=self.parse_api_list,
            headers={"Accept": "application/json"},
            meta={'page': 0}
        )

    def parse_api_list(self, response):
        data = json.loads(response.text)
        # Handle the structure of the API response
        section = data.get("sections", [{}])[0].get("articlesResult", {})
        paging = section.get("paging", {})
        section_info = paging.get("sectionInfo")
        items = section.get("items", [])
        
        has_valid_item_in_window = False
        
        for article in items:
            publish_time = self.parse_date(article.get("articleDate"))
            
            slug_param = article.get("shortCode") or article.get("urlSlug") or article.get("slug")
            if not slug_param:
                continue
                
            if not self.should_process(slug_param, publish_time):
                continue
                
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url=f"{self.detail_url}?slug={slug_param}",
                callback=self.parse_api_detail,
                headers={"Accept": "application/json"},
                meta={'list_article': article, 'publish_time': publish_time}
            )

        # Pagination for API
        if has_valid_item_in_window and paging.get("hasNext"):
            current_page = paging.get("pageNumber", 0)
            payload = {
                "sectionInfo": section_info,
                "pageNumber": current_page + 1,
                "pageSize": 20,
            }
            yield scrapy.Request(
                url=self.section_url,
                method="POST",
                body=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                callback=self.parse_api_section_page,
                meta={'page': current_page + 1}
            )

    def parse_api_section_page(self, response):
        data = json.loads(response.text)
        paging = data.get("paging", {})
        items = data.get("items", [])
        section_info = paging.get("sectionInfo")

        has_valid_item_in_window = False
        for article in items:
            publish_time = self.parse_date(article.get("articleDate"))
            slug_param = article.get("shortCode") or article.get("urlSlug") or article.get("slug")
            
            if not self.should_process(slug_param, publish_time):
                continue
            
            has_valid_item_in_window = True
            
            yield scrapy.Request(
                url=f"{self.detail_url}?slug={slug_param}",
                callback=self.parse_api_detail,
                headers={"Accept": "application/json"},
                meta={'list_article': article, 'publish_time': publish_time}
            )

        if has_valid_item_in_window and paging.get("hasNext"):
            current_page = paging.get("pageNumber", 0)
            payload = {
                "sectionInfo": section_info,
                "pageNumber": current_page + 1,
                "pageSize": 20,
            }
            yield scrapy.Request(
                url=self.section_url,
                method="POST",
                body=json.dumps(payload),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                callback=self.parse_api_section_page,
                meta={'page': current_page + 1}
            )

    def parse_api_detail(self, response):
        detail = json.loads(response.text)
        
        # Use SmartSpider's content extraction on the HTML body inside the JSON
        body_html = detail.get("body") or ""
        # Mock a response for extraction
        from scrapy.http import HtmlResponse
        mock_response = HtmlResponse(url=response.url, body=body_html, encoding='utf-8')
        
        content_data = self.extract_content(mock_response)
        
        title = detail.get("title") or ""
        publish_time = response.meta.get('publish_time')
        
        # Construct Item
        short_code = detail.get("shortCode") or response.meta.get("list_article", {}).get("shortCode")
        slug = detail.get("slug") or response.meta.get("list_article", {}).get("slug")
        article_url = f"https://www.wam.ae/ar/article/{short_code}-{slug}" if short_code and slug else response.url

        item = {
            "url": article_url,
            "title": title,
            "publish_time": publish_time,
            "author": ", ".join(detail.get("articleAuthors", [])) or "WAM",
            "section": detail.get("categories", [{}])[0].get("title") or "WAM",
            "language": self.language,
            "country": self.country,
            **content_data
        }
        
        yield item
