import os
import subprocess
from scrapy.utils.project import get_project_settings
from scrapy.spiderloader import SpiderLoader
from datetime import datetime

def build_scrapy_env(project_dir):
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = project_dir if not pythonpath else os.pathsep.join([project_dir, pythonpath])
    return env

def run_project_spiders(project_dir):
    os.chdir(project_dir)
    settings = get_project_settings()
    spider_loader = SpiderLoader(settings)
    spiders = spider_loader.list()
    env = build_scrapy_env(project_dir)
    
    print(f"[{datetime.now()}] Found {len(spiders)} spiders in {project_dir}: {spiders}")
    for spider in spiders:
        print(f"[{datetime.now()}] Starting spider: {spider}")
        try:
            # 增量爬取全放行，如需强制全量需要修改此处的参数
            subprocess.run(["scrapy", "crawl", spider], check=True, cwd=project_dir, env=env)
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
