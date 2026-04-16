from celery.schedules import crontab
from datetime import datetime

# Example cron: every 5 minutes
c = crontab(minute="*/5")
dt = datetime(2026, 4, 16, 10, 0)
print(f"Match 10:00: {c.is_due(dt)}")

dt2 = datetime(2026, 4, 16, 10, 1)
print(f"Match 10:01: {c.is_due(dt2)}")
