import os
import subprocess
from scrapy.utils.project import get_project_settings
from scrapy.spiderloader import SpiderLoader
from datetime import datetime

def run_spiders():
    settings = get_project_settings()
    spider_loader = SpiderLoader(settings)
    spiders = spider_loader.list()
    
    # 我们可以通过过滤器，只跑特定的爬虫（比如印度的，或 iran，ethiopia等）
    # 或者如果不限制，默认跑全部。这里不过滤，和您的根目录runner.py逻辑一样全跑。
    
    print(f"[{datetime.now()}] Starting news_scraper_project spiders...")
    print(f"Found spiders: {spiders}")
    
    for spider in spiders:
        print(f"[{datetime.now()}] Starting news spider: {spider}")
        try:
            # 增量爬取还是全量可以自己传参，这里演示普通调度
            subprocess.run(["scrapy", "crawl", spider], check=True)
            print(f"[{datetime.now()}] Finished news spider: {spider}")
        except subprocess.CalledProcessError as e:
            print(f"[{datetime.now()}] Error running news spider {spider}: {e}")
            
    print(f"[{datetime.now()}] All news spiders finished for this session.")

if __name__ == "__main__":
    # 进入本项目的根目录
    os.chdir("/app/news_scraper_project")
    run_spiders()
