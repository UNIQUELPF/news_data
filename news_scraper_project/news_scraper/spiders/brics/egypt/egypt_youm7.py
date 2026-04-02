# 埃及youm7爬虫，负责抓取对应站点、机构或栏目内容。

import scrapy
import psycopg2
import logging
from datetime import datetime
import re
from scrapy.exceptions import CloseSpider
import dateparser

class EgyptYoum7Spider(scrapy.Spider):
    name = 'egypt_youm7'
    allowed_domains = ['youm7.com']
    target_table = 'egy_youm7'

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DOWNLOADER_MIDDLEWARES': {
            'news_scraper.middlewares.BatchDelayMiddleware': 543,
        },
        'BATCH_SIZE': 500,
        'BATCH_DELAY': 20,
        'ITEM_PIPELINES': {
            'news_scraper.pipelines.PostgresPipeline': 300,
        }
    }

    def __init__(self, *args, **kwargs):
        super(EgyptYoum7Spider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime(2026, 1, 1)
        self.seen_urls = set()
        
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EgyptYoum7Spider, cls).from_crawler(crawler, *args, **kwargs)
        spider._init_db()
        return spider
        
    def _init_db(self):
        settings = self.settings.get('POSTGRES_SETTINGS', {})
        if not settings:
            return
            
        try:
            self.conn = psycopg2.connect(
                dbname=settings['dbname'], user=settings['user'],
                password=settings['password'], host=settings['host'], port=settings['port']
            )
            self.cur = self.conn.cursor()
            
            # create table if not exists (since pipeline requires it or creates it but it's safe to ensure reading doesn't throw)
            self.cur.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    publish_time TIMESTAMP,
                    author TEXT,
                    content TEXT,
                    site_name TEXT,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            self.conn.commit()

            self.cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = self.cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
                self.logger.info(f"Incremental scraping starting from cutoff date: {self.cutoff_date}")
            else:
                self.logger.info(f"No existing records found. Starting from default cutoff: {self.cutoff_date}")
                
            self.cur.execute(f"SELECT url FROM {self.target_table}")
            for row in self.cur.fetchall():
                self.seen_urls.add(row[0])
                
        except Exception as e:
            self.logger.error(f"Failed to connect to DB for initialization: {e}")

    def closed(self, reason):
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def start_requests(self):
        url = "https://www.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/1"
        yield scrapy.Request(url, callback=self.parse_list, cb_kwargs={'page': 1})

    def parse_list(self, response, page):
        articles = response.css('.bigOneSec, .secArticle, div[class*=col-xs-12] .secArticle')
        if not articles:
            # wait, maybe it's nested
            articles = response.css('.secArticle')
        
        if not articles:
            self.logger.info(f"No articles found on page {page}. Stopping.")
            return

        all_old = True
        found_new_overall = False
        
        for article in articles:
            a_elem = article.css('a')
            if not a_elem:
                continue
                
            a_elem = a_elem[0]
            link = a_elem.attrib.get('href') or a_elem.css('::attr(href)').get()
            if not link:
                continue
                
            if link.startswith('/'):
                link = "https://www.youm7.com" + link
                
            title_texts = article.css('h3 *::text, h3::text, h2 *::text, h2::text, h4 *::text, h4::text').getall()
            title = " ".join([t.strip() for t in title_texts if t.strip()])
            title = title.strip() if title else ""
            
            date_str = article.css('.strDate::text, .articleDate::text, .time::text').get()
            if date_str:
                date_str = date_str.strip()
            
            publish_time = None
            if date_str:
                try:
                    date_clean = re.sub(r'^[^\،\,]+\،?\s*','', date_str) 
                    parsed = dateparser.parse(date_clean, languages=['ar'], settings={'TIMEZONE': 'UTC'})
                    if parsed:
                        publish_time = parsed.replace(tzinfo=None)
                except Exception as e:
                    self.logger.error(f"Failed to parse article date: {date_str} error: {e}")
            
            if not publish_time:
                publish_time = datetime.now()

            # Optional cutoff check:
            # If the site doesn't order strictly, we might need a looser check or rely entirely on seen_urls
            # since publish_time from list page might not be accurate enough.
            if publish_time >= self.cutoff_date:
                all_old = False

            if link not in self.seen_urls:
                found_new_overall = True
                self.seen_urls.add(link)
                
                yield scrapy.Request(
                    link,
                    callback=self.parse_article,
                    cb_kwargs={'title': title, 'publish_time': publish_time}
                )

        if found_new_overall and len(articles) > 0:
            next_page = page + 1
            next_url = f"https://www.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/{next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})
        elif not found_new_overall and not all_old:
            # We haven't found any new ones on this page, but there're still newer dates than cutoff.
            # This handles duplicates/overlap.
            next_page = page + 1
            next_url = f"https://www.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/{next_page}"
            yield scrapy.Request(next_url, callback=self.parse_list, cb_kwargs={'page': next_page})

    def parse_article(self, response, title, publish_time):
        if not title:
            title_node = response.css('h1 *::text, h1::text').getall()
            title = " ".join([t.strip() for t in title_node if t.strip()])
            if not title:
                title = "Unknown Title"
                
        author = response.css('.writeBy::text, .articleHeader p::text, .editorName::text').get()
        author = author.strip() if author else "Youm7"
        if "كتبت" in author or "كتب" in author:
             author = re.sub(r'كتبت?[\s:-]+', '', author).strip()

        # Better date check from the article
        article_date = response.css('.articleHeader span::text, .articleMeta::text, .newsStoryDate::text, time::attr(datetime), .strDate::text, .newsDate::text').get()
        if article_date:
            article_date = article_date.strip()
            date_clean = re.sub(r'^[^\،\,]+\،?\s*','', article_date) 
            try:
                parsed = dateparser.parse(date_clean, languages=['ar'], settings={'TIMEZONE': 'UTC'})
                if parsed:
                    publish_time = parsed.replace(tzinfo=None)
            except Exception:
                pass

        paragraphs = response.css('#articleBody p, .articleCont p, .article-content p')
        body_text_parts = []
        for p in paragraphs:
            texts = p.xpath('.//text()').getall()
            text = ' '.join(t.strip() for t in texts if t.strip())
            if text:
                body_text_parts.append(text)
        
        if not body_text_parts:
            full_text = response.css('.articleCont *::text').getall()
            content = "\\n".join(t.strip() for t in full_text if t.strip())
        else:
             content = "\\n\\n".join(body_text_parts)

        # In case body is completely empty:
        if not content.strip():
            return
            
        yield {
            'url': response.url,
            'title': title,
            'publish_time': publish_time,
            'author': author,
            'content': content.strip(),
            'site_name': 'youm7',
            'language': 'ar'
        }
