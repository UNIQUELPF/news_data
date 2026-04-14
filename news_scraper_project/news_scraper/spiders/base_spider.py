from datetime import datetime

import scrapy
from news_scraper.utils import get_incremental_state


class BaseNewsSpider(scrapy.Spider):
    """
    通用新闻爬虫基类，包含数据库自动建表和增量探测逻辑。
    """
    target_table = None  # 在子类中定义，例如 'usa_reuters_news'
    
    def __init__(self, start_date='2026-01-01', *args, **kwargs):
        super(BaseNewsSpider, self).__init__(*args, **kwargs)
        self.cutoff_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.scraped_urls = set()
        
        # 只要在子类定义了 target_table，就自动初始化数据库
        if self.target_table:
            self.init_db()

    def init_db(self):
        try:
            state = get_incremental_state(
                getattr(self, "settings", None),
                spider_name=self.name,
                table_name=self.target_table,
                default_cutoff=self.cutoff_date,
                full_scan=False,
                url_limit=5000,
            )
            self.cutoff_date = state["cutoff_date"]
            self.scraped_urls = state["scraped_urls"]
            self.logger.info(
                f"Incremental Detection Enabled via {state['source']}: starting from {self.cutoff_date}"
            )
            self.logger.info(f"Loaded {len(self.scraped_urls)} fingerprint(s) for incremental check.")
        except Exception as e:
            self.logger.error(f"Database sync/init failed for {self.target_table}: {e}")

    def filter_date(self, pub_time):
        """
        通用日期过滤器，兼容 aware 和 naive 比较。
        """
        if not pub_time:
            return True
        
        # 确保 publish_time 是 naive 的，以便和 01-01 进行比较
        if pub_time.tzinfo:
            pub_time = pub_time.replace(tzinfo=None)
            
        return pub_time >= self.cutoff_date
