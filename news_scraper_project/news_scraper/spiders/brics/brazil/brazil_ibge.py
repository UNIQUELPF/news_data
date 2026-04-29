import scrapy
from news_scraper.spiders.smart_spider import SmartSpider

class BrazilIBGESpider(SmartSpider):
    name = "brazil_ibge"
    country_code = 'BRA'
    country = '巴西'
    allowed_domains = ["agenciadenoticias.ibge.gov.br"]
    target_table = "bra_ibge"

    # SmartSpider Settings
    use_curl_cffi = False
    playwright = True
    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    language = 'pt'
    source_timezone = 'America/Sao_Paulo'
    fallback_content_selector = "article.item-page" # Generic article wrapper

    def start_requests(self):
        url = "https://agenciadenoticias.ibge.gov.br/agencia-noticias.html?start=0"
        yield scrapy.Request(url=url, callback=self.parse_list, dont_filter=True, meta={'start_index': 0})

    def parse_list(self, response):
        items = response.css('.lista-noticias__texto')
        if not items:
            self.logger.info("No more items found on list page.")
            return

        has_valid_item_in_window = False

        for item in items:
            link = item.css('a::attr(href)').get()
            if not link:
                continue
                
            url = response.urljoin(link)
            
            raw_time = item.css('.lista-noticias__data::text').get()
            if not raw_time:
                self.logger.warning(f"Missing date in listing for {url}")
                continue
                
            # Date format: 28/04/2026
            import dateparser
            parsed_date = dateparser.parse(raw_time.strip(), settings={'DATE_ORDER': 'DMY'})
            if not parsed_date:
                self.logger.error(f"STRICT STOP: Could not parse date {raw_time}. Breaking to avoid backfill.")
                break
                
            publish_time = self.parse_to_utc(parsed_date)
            
            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                meta_dict = {'publish_time_hint': publish_time}
                if getattr(self, 'playwright', False):
                    meta_dict['playwright'] = True
                yield scrapy.Request(url, callback=self.parse_detail, meta=meta_dict)

        if has_valid_item_in_window:
            start_index = response.meta.get('start_index', 0) + 20
            next_url = f"https://agenciadenoticias.ibge.gov.br/agencia-noticias.html?start={start_index}"
            yield scrapy.Request(url=next_url, callback=self.parse_list, dont_filter=True, meta={'start_index': start_index})

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//meta[@property='article:published_time']/@content"
        )
        if not item:
            return

        # Ensure correct og:image extraction
        featured_image = response.xpath("//meta[@property='og:image']/@content").get()
        if featured_image:
            current_images = item.get('images') or []
            if featured_image not in current_images:
                item['images'] = [featured_image] + current_images
            elif current_images[0] != featured_image:
                current_images.remove(featured_image)
                item['images'] = [featured_image] + current_images

        # Author refinement
        author_text = response.css('.metadados--single b::text').get()
        if author_text:
            item['author'] = author_text.replace('|', '').strip()
        else:
            item['author'] = item.get('author') or "IBGE"

        yield item
