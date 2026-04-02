# 印度economic times爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
from datetime import datetime
from news_scraper.items import NewsItem


class IndiaEconomicTimesSpider(scrapy.Spider):
    """
    Spider for Economic Times India - Economy section.
    Covers 4 sub-sections: agriculture, economy (general/finance),
    policy, and foreign-trade.

    Uses ?curpg=N pagination on articlelist endpoints.
    Each page returns ~16 articles within div.eachStory elements.
    """
    name = "india_economic_times"
    allowed_domains = ["economictimes.indiatimes.com"]
    target_table = "ind_economic_times"

    # Section configurations: (section_name, articlelist_cms_id, url_path_prefix)
    SECTIONS = [
        ("agriculture", "1202099874", "/news/economy/agriculture"),
        ("finance", "1286551815", "/news/economy"),
        ("policy", "1106944246", "/news/economy/policy"),
        ("foreign-trade", "1200949414", "/news/economy/foreign-trade"),
    ]

    custom_settings = {
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    }

    def __init__(self, *args, **kwargs):
        super(IndiaEconomicTimesSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()

        # DB init: create table + get latest publish_time for incremental scraping
        try:
            import psycopg2
            from scrapy.utils.project import get_project_settings
            settings = get_project_settings()
            pg = settings.get('POSTGRES_SETTINGS', {})
            conn = psycopg2.connect(
                host=pg.get('host', 'postgres'),
                database=pg.get('database', 'scrapy_db'),
                user=pg.get('user', 'your_user'),
                password=pg.get('password', 'your_password'),
                port=pg.get('port', 5432)
            )
            cur = conn.cursor()
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self.target_table} ("
                f"id SERIAL PRIMARY KEY, url TEXT UNIQUE, title TEXT, "
                f"content TEXT, publish_time TIMESTAMP, author TEXT, "
                f"language TEXT, section TEXT);"
            )
            conn.commit()

            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            row = cur.fetchone()
            if row and row[0]:
                self.cutoff_date = max(self.cutoff_date, row[0].replace(tzinfo=None))

            # Pre-load existing URLs to avoid refetching detail pages
            cur.execute(f"SELECT url FROM {self.target_table}")
            for r in cur.fetchall():
                self.seen_urls.add(r[0])

            conn.close()
            self.logger.info(f"Cutoff date: {self.cutoff_date}, existing URLs: {len(self.seen_urls)}")
        except Exception as e:
            self.logger.warning(f"DB init error: {e}")

    def start_requests(self):
        for section_name, cms_id, url_prefix in self.SECTIONS:
            list_url = f"https://economictimes.indiatimes.com{url_prefix}/articlelist/{cms_id}.cms?curpg=1"
            yield scrapy.Request(
                list_url,
                callback=self.parse_list,
                meta={
                    'section': section_name,
                    'cms_id': cms_id,
                    'url_prefix': url_prefix,
                    'curpg': 1,
                    'consecutive_old': 0,
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                },
            )

    def parse_list(self, response):
        section = response.meta['section']
        cms_id = response.meta['cms_id']
        url_prefix = response.meta['url_prefix']
        curpg = response.meta['curpg']
        consecutive_old = response.meta.get('consecutive_old', 0)

        articles = response.css('div.eachStory')
        if not articles:
            self.logger.info(f"[{section}] No articles on page {curpg}, stopping section.")
            return

        found_new = False
        for article in articles:
            link = article.css('a::attr(href)').get()
            if not link:
                continue
            url = response.urljoin(link)

            # Skip already seen URLs
            if url in self.seen_urls:
                continue

            # Check date from list page to avoid unnecessary detail requests
            date_el = article.css('time.date-format::attr(data-time)').get()
            if not date_el:
                date_el = article.css('time.date-format::text').get()
            if date_el:
                try:
                    list_date = datetime.strptime(date_el.strip(), "%b %d, %Y, %I:%M %p IST")
                    if list_date < self.cutoff_date:
                        consecutive_old += 1
                        if consecutive_old >= 32:
                            self.logger.info(
                                f"[{section}] 32 consecutive old articles on page {curpg}, stopping."
                            )
                            return
                        continue
                    else:
                        consecutive_old = 0
                        found_new = True
                except ValueError:
                    found_new = True
            else:
                found_new = True

            self.seen_urls.add(url)
            yield scrapy.Request(
                url,
                callback=self.parse_detail,
                meta={'section': section},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                },
            )

        # Paginate: safety cap at 500 pages
        next_pg = curpg + 1
        if next_pg <= 500:
            next_url = (
                f"https://economictimes.indiatimes.com{url_prefix}"
                f"/articlelist/{cms_id}.cms?curpg={next_pg}"
            )
            yield scrapy.Request(
                next_url,
                callback=self.parse_list,
                meta={
                    'section': section,
                    'cms_id': cms_id,
                    'url_prefix': url_prefix,
                    'curpg': next_pg,
                    'consecutive_old': consecutive_old,
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                },
            )

    def parse_detail(self, response):
        section = response.meta.get('section', '')
        item = NewsItem()
        item['url'] = response.url
        item['language'] = 'English'
        item['section'] = section

        # Title
        title = response.css('h1::text').get()
        if not title:
            title = response.css('h1.artTitle::text').get()
        item['title'] = (title or "").strip()

        # Publish time: try time.jsdtTime element first
        pub_time = None
        time_text = response.css('time.jsdtTime::text').get()
        if time_text:
            # Format: "Last Updated: Mar 15, 2026, 03:43:00 PM IST"
            clean = time_text.strip()
            for prefix in ['Last Updated:', 'Updated:', 'Published:']:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):].strip()
                    break
            try:
                pub_time = datetime.strptime(clean, "%b %d, %Y, %I:%M:%S %p IST")
            except ValueError:
                try:
                    pub_time = datetime.strptime(clean, "%b %d, %Y, %I:%M %p IST")
                except ValueError:
                    self.logger.warning(f"Cannot parse date: {clean}")

        # Fallback: date-format element
        if not pub_time:
            date_attr = response.css('time.date-format::attr(data-time)').get()
            if date_attr:
                try:
                    pub_time = datetime.strptime(date_attr.strip(), "%b %d, %Y, %I:%M %p IST")
                except ValueError:
                    pass

        item['publish_time'] = pub_time

        # Skip articles before cutoff
        if pub_time and pub_time < self.cutoff_date:
            return

        # Content: .artText div contains all article content
        content_parts = response.css('.artText ::text').getall()
        if not content_parts:
            # Fallback: some articles use div.article_content or div.Normal
            content_parts = response.css('.article_content ::text, .Normal ::text').getall()
        
        # Clean up whitespace and join
        cleaned_parts = []
        for p in content_parts:
            text = p.strip()
            # Ignore short javascript/css snippets or empty lines
            if text and len(text) > 2 and "{" not in text:
                cleaned_parts.append(text)
                
        item['content'] = "\n".join(cleaned_parts)

        # Author
        author = response.css('.artByline a::text').get(default='').strip()
        if not author:
            author = response.css('.publish_by::text').get(default='').strip()
        item['author'] = author or "Economic Times"

        if not item['title'] or not item['content']:
            return

        yield item
