import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider


class TrTbmmSpider(SmartSpider):
    name = "tr_tbmm"
    source_timezone = 'Europe/Istanbul'

    country_code = 'TUR'
    country = '土耳其'
    language = 'tr'

    allowed_domains = ['tbmm.gov.tr']

    # 土耳其大国民议会新闻列表
    base_url = 'https://www.tbmm.gov.tr/meclis-haber/meclis?pageIndex={}'

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 1,
        'ROBOTSTXT_OBEY': False,
    }

    use_curl_cffi = True
    strict_date_required = True
    fallback_content_selector = "div#haber-detay-aciklama"

    async def start(self):
        yield scrapy.Request(self.base_url.format(0), callback=self.parse, meta={'page': 0})

    def parse(self, response):
        # 精准匹配含有 Haber/Detay (新闻详情) 的 Id 链接
        links = response.css("a[href*='/Haber/Detay?Id=']::attr(href)").getall()
        current_page = response.meta.get('page', 0)
        self.logger.info(f"Page {current_page} - Captured {len(links)} links.")

        has_valid_item_in_window = False

        for link in set(links):
            has_valid_item_in_window = True
            yield response.follow(link, self.parse_detail)

        # Pagination breaker: 只要当前页有数据且未翻过头，就继续翻页
        if has_valid_item_in_window:
            next_page = current_page + 1
            yield scrapy.Request(
                self.base_url.format(next_page),
                callback=self.parse,
                meta={'page': next_page},
            )

    def parse_detail(self, response):
        # 1. 自定义标题提取 (TBMM 使用独特的 HTML 布局，无 JSON-LD)
        title = response.css('meta[property="og:title"]::attr(content)').get()

        if not title or len(title.strip()) < 2:
            raw_text = response.xpath('string(//div[@id="haber-detay-baslik"])').get()
            if raw_text:
                lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                if lines:
                    title = max(lines, key=len)

        if not title:
            title = response.css('title::text').get('').split('-')[0].strip()

        # 2. 自定义日期提取 (格式: 2026-03-31 - 15:42)
        pub_time = None
        pub_time_str = response.css('div#haber-detay-saat-dakika::text').get('').strip()

        if pub_time_str:
            try:
                clean_date = pub_time_str.split('-')
                if len(clean_date) >= 3:
                    date_part = "-".join(clean_date[:3]).strip()
                    time_part = clean_date[-1].strip()
                    pub_time = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
            except Exception:
                self.logger.warning(f"Failed to parse date string: {pub_time_str}")

        pub_time_utc = self.parse_to_utc(pub_time) if pub_time else self.parse_to_utc(datetime.now())

        self.logger.info(f"Checking article: {title} | Date: {pub_time_utc} | URL: {response.url}")

        # 3. SmartSpider 日期窗口 + 去重过滤
        if not self.should_process(response.url, pub_time_utc):
            self.logger.info(f"Filtered (Old/No date): {pub_time_utc} for {response.url}")
            return

        # 4. 自动提取 (ContentEngine)
        item = self.auto_parse_item(response)

        # 5. 用自定义提取值覆盖
        item['title'] = title
        item['publish_time'] = pub_time_utc
        item['author'] = 'TBMM Official'
        item['section'] = 'Official News'

        self.logger.info(f"Yielding Valid Item: {title}")
        yield item
