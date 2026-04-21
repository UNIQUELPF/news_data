import os
from sqlalchemy import create_engine
from celery_sqlalchemy_scheduler.models import ModelBase
from sqlalchemy.orm import sessionmaker
from celery_sqlalchemy_scheduler.models import PeriodicTask, CrontabSchedule
import json

def get_db_uri():
    db_user = os.getenv("POSTGRES_USER", "your_user")
    db_pass = os.getenv("POSTGRES_PASSWORD", "your_password")
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "scrapy_db")
    return f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

def init_scheduler():
    uri = get_db_uri()
    engine = create_engine(uri)
    ModelBase.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()

    # Define our core tasks
    tasks = [
        {
            "name": "全量爬虫巡航 (Crawler Auto-Cruise)",
            "task": "pipeline.tasks.crawl.run_all_spiders_automatic",
            "crontab": "30 * * * *", # Every 30 mins
        },
        {
            "name": "后台自动翻译 (Auto Article Translation)",
            "task": "pipeline.tasks.translate.auto_translate_articles",
            "crontab": "*/5 * * * *", # Every 5 mins
        },
        {
            "name": "后台自动向量 (Auto Article Embedding)",
            "task": "pipeline.tasks.embed.auto_embed_articles",
            "crontab": "*/5 * * * *", # Every 5 mins
        }
    ]

    for t in tasks:
        # Check if task already exists
        existing = session.query(PeriodicTask).filter_by(name=t["name"]).first()
        if not existing:
            minute, hour, day_of_week, day_of_month, month_of_year = t["crontab"].split()
            
            # Create or get crontab
            schedule = session.query(CrontabSchedule).filter_by(
                minute=minute, hour=hour, day_of_week=day_of_week, 
                day_of_month=day_of_month, month_of_year=month_of_year
            ).first()
            
            if not schedule:
                schedule = CrontabSchedule(
                    minute=minute, hour=hour, day_of_week=day_of_week,
                    day_of_month=day_of_month, month_of_year=month_of_year,
                    timezone='Asia/Shanghai'
                )
                session.add(schedule)
                session.flush()

            new_task = PeriodicTask(
                name=t["name"],
                task=t["task"],
                crontab_id=schedule.id,
                enabled=True,
                args='[]',
                kwargs='{}'
            )
            session.add(new_task)
            print(f"Created periodic task: {t['name']}")
    
    session.commit()
    session.close()

if __name__ == "__main__":
    init_scheduler()
