import scrapy
import psycopg2
from datetime import datetime
from news_scraper.settings import POSTGRES_SETTINGS

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
            conn = psycopg2.connect(**POSTGRES_SETTINGS)
            cur = conn.cursor()
            
            # 1. 自动根据 target_table 建表
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.target_table} (
                    url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    publish_time TIMESTAMP NOT NULL,
                    author VARCHAR(255),
                    language VARCHAR(50) DEFAULT 'en',
                    section VARCHAR(100),
                    scraped_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            
            # 2. 增量探测：获取最新发布时间并加载最近的 URL 指纹
            cur.execute(f"SELECT MAX(publish_time) FROM {self.target_table}")
            max_date = cur.fetchone()[0]
            if max_date:
                self.cutoff_date = max_date
                self.logger.info(f"Incremental Detection Enabled: Starting from {self.cutoff_date}")
            
            # 加载最近的 5000 条 URL 到内存中，用于前置过滤
            cur.execute(f"SELECT url FROM {self.target_table} ORDER BY publish_time DESC LIMIT 5000")
            rows = cur.fetchall()
            self.scraped_urls = {row[0] for row in rows}
            self.logger.info(f"Loaded {len(self.scraped_urls)} fingerprint(s) from DB for incremental check.")
            
            cur.close()
            conn.close()
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
