import scrapy
from datetime import datetime
from news_scraper.spiders.smart_spider import SmartSpider
import re

class TjAvestaSpider(SmartSpider):
    name = 'tj_avesta'
    source_timezone = 'Asia/Dushanbe'

    country_code = 'TJK'

    country = '塔吉克斯坦'
    language = 'ru'
    allowed_domains = ['avesta.tj']
    strict_date_required = True
    use_curl_cffi = True
    fallback_content_selector = "div.content-inner, div.jeg_inner_content"

    # 俄语月份映射
    RUS_MONTHS = {
        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
        'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
        'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
    }

    async def start(self):
        yield scrapy.Request('https://avesta.tj/news/ekonomika/', callback=self.parse, dont_filter=True)

    def parse(self, response):
        articles = response.css('h3.jeg_post_title a')
        has_valid_item_in_window = False
        for article in articles:
            link = article.css('::attr(href)').get()
            if not link:
                continue

            # Extract date from listing page (JNews .jeg_meta_date)
            publish_time = None
            date_str = (
                article.xpath(
                    './../../div[contains(@class, "jeg_meta_date")]'
                    '//text()'
                ).get()
                or
                article.xpath(
                    './ancestor::article[1]'
                    '//div[contains(@class, "jeg_meta_date")]'
                    '//text()'
                ).get()
            )
            if date_str:
                dt_obj = self._parse_date(date_str.strip())
                if dt_obj:
                    publish_time = self.parse_to_utc(dt_obj)

            if not self.should_process(response.urljoin(link), publish_time):
                continue

            has_valid_item_in_window = True
            yield response.follow(
                link, self.parse_detail,
                meta={"publish_time_hint": publish_time}
            )

        next_page = response.css('a.page_nav.next::attr(href)').get()
        if has_valid_item_in_window and next_page:
            yield response.follow(next_page, self.parse)

    def parse_detail(self, response):
        title = response.css('h1.jeg_post_title::text').get('').strip()
        if not title:
            return

        raw_date = response.css('div.jeg_meta_date a::text').get() or response.css('div.jeg_meta_date::text').get('')
        raw_date = raw_date.strip()
        dt_obj = self._parse_date(raw_date)
        pub_time = self.parse_to_utc(dt_obj) if dt_obj else None

        if pub_time and not self.should_process(response.url, pub_time):
            return

        item = self.auto_parse_item(response)
        if not item.get('content_plain'):
            paragraphs = response.css('div.content-inner p::text').getall()
            if not paragraphs:
                paragraphs = response.css('div.jeg_inner_content p::text').getall()
            content = "\n\n".join([p.strip() for p in paragraphs if p.strip()])
            if content:
                item['content_plain'] = content

        item['author'] = 'Avesta.tj'
        item['section'] = 'Economic'
        item['title'] = title

        yield item

    def _parse_date(self, date_str):
        if not date_str:
            return None
        date_str = date_str.replace('/', ' ')
        for rus_m, num_m in self.RUS_MONTHS.items():
            if rus_m in date_str.lower():
                date_str = re.sub(rus_m, num_m, date_str, flags=re.IGNORECASE)
                break
        date_str = re.sub(r'\s+', ' ', date_str).strip()
        try:
            return datetime.strptime(date_str, "%d %m, %Y %H:%M")
        except Exception:
            return None
