import scrapy
from datetime import datetime
import re
import json
from news_scraper.spiders.smart_spider import SmartSpider


class SgZaobaoSpider(SmartSpider):
    name = 'sg_zaobao'
    country_code = 'SGP'
    country = '新加坡'
    language = 'zh'
    source_timezone = 'Asia/Singapore'
    start_date = '2024-01-01'
    allowed_domains = ['zaobao.com.sg']
    fallback_content_selector = 'article'

    # 联合早报 API 接口
    api_url = 'https://www.zaobao.com.sg/_plat/api/v2/page-content/finance/singapore?page={}'
    start_urls = [api_url.format(1)]

    use_curl_cffi = True

    custom_settings = {
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.CurlCffiMiddleware': 543,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'CURLL_CFFI_IMPERSONATE': 'chrome120',
        'DEFAULT_REQUEST_HEADERS': {
            'referer': 'https://www.zaobao.com.sg/finance/singapore',
            'x-requested-with': 'XMLHttpRequest'
        },
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2
    }

    def parse(self, response):
        # 直接处理 JSON 响应
        try:
            data = json.loads(response.text)
            resp_node = data.get('response', {})
            articles = resp_node.get('articles', [])

            self.logger.info(f"API Response: Found {len(articles)} articles in JSON.")
        except Exception as e:
            self.logger.error(f"Failed to parse API JSON on {response.url}: {e}")
            return

        if not articles:
            return

        current_page = response.meta.get('page', 1)
        valid_items = 0

        for art in articles:
            href = art.get('href')
            ts = art.get('timestamp')

            if not href or not ts:
                continue

            pub_date = datetime.fromtimestamp(int(ts))
            # V2: 使用 should_process 替代 filter_date
            if not self.should_process(href, pub_date):
                continue

            valid_items += 1
            full_url = response.urljoin(href)
            yield response.follow(full_url, self.parse_article)

        # 继续翻页 API
        if valid_items > 0 and current_page < 200:
            next_page = current_page + 1
            yield scrapy.Request(
                self.api_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
                dont_filter=True
            )

    def parse_article(self, response):
        item = self.auto_parse_item(
            response,
            title_xpath="//h1/text()",
        )
        # 保留原有 LD+JSON 日期解析作为补充
        pub_time = item.get('publish_time')
        if not pub_time:
            ld_json_scripts = response.css('script[type="application/ld+json"]::text').getall()
            for raw in ld_json_scripts:
                try:
                    data_list = json.loads(raw)
                    if not isinstance(data_list, list):
                        data_list = [data_list]
                    for data in data_list:
                        dp = data.get('datePublished', data.get('dateModified'))
                        if dp:
                            pub_time = datetime.fromisoformat(dp.replace('Z', '+00:00'))
                            break
                    if pub_time:
                        break
                except:
                    continue

            if not pub_time:
                dm = re.search(r'story(\d{4})(\d{2})(\d{2})', response.url)
                if dm:
                    y, m, d = dm.groups()
                    pub_time = datetime(int(y), int(m), int(d))
                else:
                    return

            item['publish_time'] = pub_time

        item['author'] = 'Lianhe Zaobao API'
        item['section'] = 'Finance/Singapore'
        if item.get('content_plain') and len(item['content_plain']) > 50:
            if self.should_process(response.url, item.get('publish_time')):
                yield item
