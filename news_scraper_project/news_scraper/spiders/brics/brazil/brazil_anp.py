import datetime

import dateparser
import scrapy

from news_scraper.spiders.smart_spider import SmartSpider


class BrazilANPSpider(SmartSpider):
    name = "brazil_anp"
    country_code = "BRA"
    country = "巴西"
    language = "pt"
    source_timezone = "America/Sao_Paulo"
    start_date = "2026-01-01"
    allowed_domains = ["gov.br"]

    use_curl_cffi = True
    fallback_content_selector = "div#content"

    def start_requests(self):
        url = "https://www.gov.br/anp/pt-br/canais_atendimento/imprensa/noticias-comunicados?b_start:int=0"
        yield scrapy.Request(url=url, callback=self.parse_list, dont_filter=True, meta={"start_index": 0})

    def parse_list(self, response):
        items = response.css("div.conteudo")
        if not items:
            self.logger.info("No more items found on list page.")
            return

        has_valid_item_in_window = False

        for item in items:
            link = item.css("h2.titulo a::attr(href)").get()
            if not link:
                continue

            url = response.urljoin(link)
            raw_time = item.css("span.data::text").get()
            if not raw_time:
                self.logger.warning(f"Missing date in listing for {url}")
                continue

            parsed_date = dateparser.parse(raw_time.strip(), settings={"DATE_ORDER": "DMY"})
            if not parsed_date:
                self.logger.error(f"STRICT STOP: Could not parse date {raw_time}. Breaking to avoid backfill.")
                break

            publish_time = self.parse_to_utc(parsed_date)
            if self.should_process(url, publish_time):
                has_valid_item_in_window = True
                yield scrapy.Request(url, callback=self.parse_detail, meta={"publish_time_hint": publish_time})

        if has_valid_item_in_window:
            start_index = response.meta.get("start_index", 0) + 30
            if start_index < 3000:
                next_url = (
                    "https://www.gov.br/anp/pt-br/canais_atendimento/imprensa/"
                    f"noticias-comunicados?b_start:int={start_index}"
                )
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse_list,
                    dont_filter=True,
                    meta={"start_index": start_index},
                )

    def parse_detail(self, response):
        item = self.auto_parse_item(
            response,
            publish_time_xpath="//span[@class='documentPublished']//span[@class='value']/text()",
        )
        if not item:
            return

        if not response.css("script[type='application/ld+json']"):
            raw_time = response.css(".documentPublished .value::text").get()
            if raw_time:
                try:
                    date_text = raw_time.replace("h", ":").strip()
                    dt = datetime.datetime.strptime(date_text, "%d/%m/%Y %H:%M")
                    item["publish_time"] = self.parse_to_utc(dt)
                except ValueError:
                    pass

        item["country"] = self.country
        item["country_code"] = self.country_code
        item["author"] = "ANP Imprensa"
        yield item
