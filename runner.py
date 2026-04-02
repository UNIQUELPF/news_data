import os
import subprocess
from scrapy.utils.project import get_project_settings
from scrapy.spiderloader import SpiderLoader
from datetime import datetime

def run_project_spiders(project_dir):
    os.chdir(project_dir)
    settings = get_project_settings()
    spider_loader = SpiderLoader(settings)
    spiders = spider_loader.list()
    
    # 优先级排序逻辑：定义绿色国家的优先级
    # 数值越小，优先级越高。美国(usa)设为最高。
    priority_map = {
        'usa_': 0,
        'jp_': 0.5,
        'ng_': 1,
        'pt_': 2,
        'mexico_': 3,
        'mm_': 4,
        'malaysia_': 5,
        'lebanon_': 6,
        'luxembourg_': 7,
        'jp_': 8
    }
    
    def get_priority(spider_name):
        for prefix, priority in priority_map.items():
            if spider_name.startswith(prefix):
                return priority
        return 99 # 非重点国家排在最后
    
    # 根据优先级和名称进行排序
    spiders.sort(key=lambda x: (get_priority(x), x))
    
    print(f"[{datetime.now()}] Found {len(spiders)} spiders in {project_dir}. Sorted by priority.")
    for spider in spiders:
        print(f"[{datetime.now()}] Starting spider: {spider}")
        try:
            # 增量爬取全放行
            subprocess.run(["scrapy", "crawl", spider], check=True)
            print(f"[{datetime.now()}] Finished spider: {spider}")
        except subprocess.CalledProcessError as e:
            print(f"[{datetime.now()}] Error running spider {spider}: {e}")

if __name__ == "__main__":
    print(f"[{datetime.now()}] Starting global crawl job...")
    # 执行统一的新闻采集项目 (中国、哈萨克斯坦和其他国家爬虫)
    news_project_dir = "/app/news_scraper_project"
    if os.path.exists(news_project_dir):
        try:
            run_project_spiders(news_project_dir)
        except Exception as e:
            print(f"[{datetime.now()}] Error in news scraper project: {e}")
    else:
        print(f"[{datetime.now()}] Error: {news_project_dir} not found")
            
    print(f"[{datetime.now()}] All spiders finished for this session.")
