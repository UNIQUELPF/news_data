# 巴西ibge爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

import scrapy
from news_scraper.items import NewsItem
from news_scraper.utils import get_incremental_state


class BrazilIBGESpider(scrapy.Spider):
    name = "brazil_ibge"

    country_code = 'BRA'

    country = '巴西'
    allowed_domains = ["agenciadenoticias.ibge.gov.br"]
    target_table = "bra_ibge"

    def __init__(self, *args, **kwargs):
        super(BrazilIBGESpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.start_index = 0
        self.base_url = "https://agenciadenoticias.ibge.gov.br/agencia-noticias.html?start={}"
        
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
        items = response.css('.lista-noticias__texto')
        if not items:
            self.logger.info("No more items found on list page.")
            return

        stop_crawling = False
        parsed_any = False
        
        for item in items:
            link = item.css('a::attr(href)').get()
            if link:
                url = response.urljoin(link)
                # date extraction on list page to check cutoff
                date_str = item.css('.lista-noticias__data::text').get()
                if date_str:
                    try:
                        pub_date = datetime.strptime(date_str.strip(), "%d/%m/%Y")
                        if pub_date < self.cutoff_date:
                            self.logger.info(f"Reached cutoff date on list page: {pub_date}")
                            stop_crawling = True
                            continue # Skip yielding request for this old item
                    except Exception as e:
                        self.logger.error(f"Failed to parse list date {date_str}: {e}")

                parsed_any = True
                yield scrapy.Request(url, callback=self.parse_detail)

        # Increment pagination if we didn't hit cutoff and parsed at least one item
        if not stop_crawling and parsed_any:
            self.start_index += 20
            yield scrapy.Request(url=self.base_url.format(self.start_index), callback=self.parse_list)

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['language'] = 'Portuguese'
        
        raw_title = (response.css('meta[property="og:title"]::attr(content)').get() or response.css('h2::text').get() or "").strip()
        item['title'] = raw_title.replace(" | Agência de Notícias", "").strip()
        
        date_str = response.css('meta[property="article:published_time"]::attr(content)').get()
        if date_str:
            try:
                pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                item['publish_time'] = pub_time
                if pub_time < self.cutoff_date:
                    return
            except ValueError:
                item['publish_time'] = None
        else:
            item['publish_time'] = None

        paragraphs = response.css('.texto--single p::text').getall()
        if not paragraphs:
            paragraphs = response.css('.mod-articles-category-introtext::text').getall()
            
        item['content'] = "\n".join([p.strip() for p in paragraphs if p.strip()])
        
        author_text = response.css('.metadados--single b::text').get()
        if author_text:
            item['author'] = author_text.replace('|', '').strip()
        else:
            item['author'] = ""

        if not item['title'] or not item['content']:
            return

        yield item
