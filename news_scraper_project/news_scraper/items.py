import scrapy

class NewsItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    publish_time = scrapy.Field()
    scrape_time = scrapy.Field()
    author = scrapy.Field()
    language = scrapy.Field()
    section = scrapy.Field()


class CaixinHeadlineItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    crawl_time = scrapy.Field()


class NewsHeadlineItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    publish_date = scrapy.Field()
    content = scrapy.Field()
    channel = scrapy.Field()
    module = scrapy.Field()
    crawl_time = scrapy.Field()


class CaixinMarketIndexItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    time = scrapy.Field()
    detail = scrapy.Field()
    crawl_time = scrapy.Field()


class ZakonItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_date = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class InformburoItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class InformKzItem(scrapy.Item):
    type = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_date = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class KapitalItem(scrapy.Item):
    type = scrapy.Field()
    category = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class PortalItem(scrapy.Item):
    type = scrapy.Field()
    site_domain = scrapy.Field()
    category = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class LSMItem(scrapy.Item):
    type = scrapy.Field()
    category = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class InBusinessItem(scrapy.Item):
    type = scrapy.Field()
    category = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()


class DigitalBusinessItem(scrapy.Item):
    type = scrapy.Field()
    category = scrapy.Field()
    title = scrapy.Field()
    url = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    crawl_time = scrapy.Field()
