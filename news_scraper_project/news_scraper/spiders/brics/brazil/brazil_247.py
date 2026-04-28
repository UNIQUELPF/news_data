# 巴西247爬虫，负责抓取对应站点、机构或栏目内容。

from datetime import datetime

from news_scraper.items import NewsItem
from scrapy.spiders import SitemapSpider


class Brazil247Spider(SitemapSpider):
    name = "brazil_247"

    country_code = "BRA"

    country = "巴西"
    language = "en"
    source_timezone = "America/Sao_Paulo"
    start_date = "2026-01-01"
    allowed_domains = ["brasil247.com"]
    
    sitemap_urls = ['https://www.brasil247.com/sitemaps/sitemap.xml']
    sitemap_rules = [
        # Catch typical article paths, excluding irrelevant sections
        (r'https://www.brasil247.com/(?!sitemaps|author|video|tv|blog|cultura|esportes)[a-z0-9-]+/.+', 'parse_detail'),
    ]


    def sitemap_filter(self, entries):
        """
        Intercepts sitemap entries and skips any that are older than our cutoff.
        This prevents Scrapy from blindly sending millions of HTTP GETs for 10-year-old articles.
        """
        cutoff_iso = self.cutoff_date.isoformat()
        for entry in entries:
            lastmod = entry.get('lastmod')
            if lastmod:
                # String comparison is highly efficient and works perfectly for ISO-8601
                if lastmod >= cutoff_iso:
                    yield entry
            else:
                yield entry

    def parse_detail(self, response):
        item = NewsItem()
        item['url'] = response.url
        item['title'] = (response.css("h1.article__headline::text").get() or "").strip()
        
        paragraphs = response.css("article.article__full p::text").getall()
        # Fallback if structure changes
        if not paragraphs:
            paragraphs = response.css("div.article__content p::text").getall()

        item['content'] = "\n".join([p.strip() for p in paragraphs if p.strip()])
        
        item['author'] = ""
        item['language'] = 'Portuguese'
        
        # More reliable extraction from meta tag
        date_str = response.xpath('//meta[@property="article:published_time"]/@content').get()
        if date_str:
            try:
                # e.g. 2026-03-11T21:32:11Z
                pub_time = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                item['publish_time'] = pub_time
                if pub_time < self.cutoff_date:
                    return
            except ValueError:
                item['publish_time'] = None
        else:
            item['publish_time'] = None

        author_tag = response.css("div.article__meta strong::text").get()
        if author_tag:
            item['author'] = author_tag.strip()
        
        # Validate critical fields
        if not item['title'] or not item['content']:
            return

        yield item
