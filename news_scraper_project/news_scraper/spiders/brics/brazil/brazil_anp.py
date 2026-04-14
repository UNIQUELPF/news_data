# 巴西anp爬虫，负责抓取对应站点、机构或栏目内容。

import json
from datetime import datetime

import scrapy
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state


class BrazilANPSpider(scrapy.Spider):
    name = "brazil_anp"

    country_code = 'BRA'

    country = '巴西'
    allowed_domains = ["gov.br"]
    target_table = "bra_anp"

    def __init__(self, *args, **kwargs):
        super(BrazilANPSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.start_index = 0
        self.base_url = "https://www.gov.br/anp/pt-br/canais_atendimento/imprensa/noticias-comunicados?b_start:int={}"
        
        try:
            state = get_incremental_state(
                self.settings,
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
            )
            self.cutoff_date = max(self.cutoff_date, state["cutoff_date"])
            self.logger.info(f"Using cutoff date: {self.cutoff_date}")
        except Exception as e:
            self.logger.warning(f"Error fetching max date from DB: {e}")

    def start_requests(self):
        yield scrapy.Request(url=self.base_url.format(self.start_index), callback=self.parse_list)

    def parse_list(self, response):
        items = response.css('h2.titulo a')
        if not items:
            self.logger.info("No more items found on list page.")
            return

        parsed_any = False
        
        for item in items:
            link = item.attrib.get('href')
            if link:
                url = response.urljoin(link)
                parsed_any = True
                yield scrapy.Request(url, callback=self.parse_detail)

        # Pagination: the `BatchDelayMiddleware` will limit excessive scraping, but we still need a cutoff condition
        # We rely on the `parse_detail` yielding items and dropping them if too old, but the list pagination must eventually stop.
        # Since we cannot easily extract date accurately from list items without detail visit in this DOM, we increment pagination
        # Note: Scrapy will inherently deduplicate Requests, and the DB will deduplicate Inserts.
        # So we keep paginating as long as there are items (Scrapy will stop when list returns empty or pagination breaks).
        # We rely on the parse_detail returning `None` and raising `CloseSpider` or similar via an Item Pipeline, OR
        # just let it crawl until it hits oldest items. For better cutoff handling, we pass the pagination logic carefully.
        
        if parsed_any and self.start_index < 3000: # Setting upper bound limit as safety fallback
            self.start_index += 30
            yield scrapy.Request(url=self.base_url.format(self.start_index), callback=self.parse_list)

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['language'] = 'Portuguese'
        
        # Title
        item['title'] = (response.css('h1.documentFirstHeading::text').get() or "").strip()
        
        # Publish Time - primarily from JSON-LD
        json_ld = response.css('script[type="application/ld+json"]::text').get()
        pub_time = None
        if json_ld:
            try:
                data = json.loads(json_ld)
                date_str = data.get('datePublished')
                if date_str:
                    pub_time = datetime.fromisoformat(date_str).replace(tzinfo=None)
            except Exception as e:
                self.logger.error(f"Failed to parse JSON-LD date: {e}")
        
        if not pub_time:
            # Fallback Date parsing
            # Format: '13/03/2026 18h15'
            date_text = response.css('.documentPublished .value::text').get()
            if date_text:
                try:
                    date_text = date_text.replace('h', ':')
                    pub_time = datetime.strptime(date_text.strip(), "%d/%m/%Y %H:%M")
                except ValueError:
                    pass

        item['publish_time'] = pub_time
        if pub_time and pub_time < self.cutoff_date:
            # Reached cutoff date in detail items. To avoid traversing pagination infinitely down,
            # this cutoff logic will be matched frequently.
            return

        # Content
        paragraphs = response.css('div[property="rnews:articleBody"] p::text').getall()
        if not paragraphs:
            paragraphs = response.css('.documentDescription::text').getall()
            
        item['content'] = "\n".join([p.strip() for p in paragraphs if p.strip()])
        item['author'] = "ANP Imprensa"

        if not item['title'] or not item['content']:
            return

        yield item
