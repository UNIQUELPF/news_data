import scrapy
from datetime import datetime
from news_scraper.items import NewsItem
from news_scraper.utils import get_dynamic_cutoff
from bs4 import BeautifulSoup
import urllib3
import re

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BfbSpider(scrapy.Spider):
    name = 'bfb'
    allowed_domains = ['bfb.az']
    start_urls = ['https://www.bfb.az/press-relizler']
    
    target_table = 'aze_bfb'

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    # Azerbaijani month mapping (lowercase for matching)
    AZ_MONTHS = {
        'yanvar': 1, 'fevral': 2, 'mart': 3, 'aprel': 4,
        'may': 5, 'iyun': 6, 'iyul': 7, 'avqust': 8,
        'sentyabr': 9, 'oktyabr': 10, 'noyabr': 11, 'dekabr': 12
    }

    CUTOFF_DATE = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(BfbSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.CUTOFF_DATE = get_dynamic_cutoff(crawler.settings, spider.target_table)
        # Ensure we use 2026-01-01 if it's the first run
        if spider.CUTOFF_DATE > datetime(2026, 1, 1):
             spider.CUTOFF_DATE = datetime(2026, 1, 1)
        return spider

    def parse(self, response):
        """Parses the press release list page."""
        items = response.css('.card')
        
        current_page_match = re.search(r'page=(\d+)', response.url)
        current_page = int(current_page_match.group(1)) if current_page_match else 1

        if not items:
            self.logger.warning(f"No items found on Page {current_page}")
            return

        article_found = False
        reached_cutoff = False

        for item in items:
            title_node = item.css('.post_title')
            date_node = item.css('.card-body .date')
            
            if title_node and date_node:
                title = title_node.xpath('string()').get().strip()
                href = title_node.css('::attr(href)').get()
                date_str = date_node.xpath('string()').get().strip()
                
                publish_time = self.parse_az_date(date_str)
                if not publish_time:
                    continue
                
                if publish_time < self.CUTOFF_DATE:
                    reached_cutoff = True
                    break
                
                article_url = response.urljoin(href)
                yield scrapy.Request(
                    url=article_url,
                    callback=self.parse_detail,
                    meta={'title': title, 'publish_time': publish_time}
                )
                article_found = True

        # Pagination logic
        if not reached_cutoff:
            next_link = response.xpath("//a[contains(text(), 'Sonrakı')]/@href").get()
            
            if next_link:
                yield response.follow(next_link, callback=self.parse)
            else:
                next_page = current_page + 1
                next_page_link = response.css(f'a.page-link[href*="page={next_page}"]::attr(href)').get()
                if next_page_link:
                    yield response.follow(next_page_link, callback=self.parse)
                elif article_found:
                    next_url = f"https://www.bfb.az/press-relizler?page={next_page}"
                    yield scrapy.Request(next_url, callback=self.parse)

    def parse_az_date(self, date_str):
        """Parses Azerbaijani date strings like '5 mart 2026'."""
        try:
            parts = date_str.lower().split()
            if len(parts) >= 3:
                day = int(parts[0])
                month_name = parts[1]
                year = int(parts[2])
                
                month = self.AZ_MONTHS.get(month_name)
                if month:
                    return datetime(year, month, day)
        except Exception as e:
            self.logger.error(f"Error parsing date {date_str}: {e}")
        return None

    def parse_detail(self, response):
        """Parses the article detail page."""
        item = NewsItem()
        item['url'] = response.url
        item['title'] = response.meta['title']
        item['publish_time'] = response.meta['publish_time']
        item['language'] = 'az'
        item['author'] = 'Baku Stock Exchange (BFB)'
        item['scrape_time'] = datetime.now()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        article_body = soup.select_one('.main_press_container') or soup.select_one('.post_content') or soup.select_one('.content-block__text')
        
        if not article_body:
            containers = soup.find_all(['div', 'section', 'article'])
            article_body = max(containers, key=lambda c: len(c.get_text()), default=None)

        item['content'] = self.reconstruct_content_with_tables(article_body)
        yield item

    def reconstruct_content_with_tables(self, root_element):
        """Reconstructs content while converting tables to text."""
        if not root_element:
            return ""
        
        for unwanted in root_element(["script", "style", "nav", "footer", "header", "form"]):
            unwanted.decompose()

        content_parts = []
        for element in root_element.find_all(['p', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'], recursive=True):
            if element.name == 'table':
                table_text = self.extract_table_as_text(element)
                if table_text:
                    content_parts.append("\n" + table_text + "\n")
            else:
                text = element.get_text(strip=True)
                if text and len(text) > 1:
                    if not any(text in existing for existing in content_parts):
                        content_parts.append(text)
        
        if not content_parts:
            return root_element.get_text(separator='\n\n', strip=True)
            
        return "\n\n".join(content_parts)

    def extract_table_as_text(self, table_soup):
        """Converts an HTML table into a Markdown-like text representation."""
        rows = []
        for tr in table_soup.find_all('tr'):
            cells = [td.get_text(separator=' ', strip=True) for td in tr.find_all(['td', 'th'])]
            cells = [re.sub(r'\s+', ' ', c) for c in cells]
            if any(cells):
                rows.append(" | ".join(cells))
        
        if not rows:
            return ""
            
        if len(rows) > 1:
            try:
                col_count = rows[0].count('|') + 1
                rows.insert(1, "|".join(["---"] * col_count))
            except:
                pass
            
        return "\n".join(rows)
