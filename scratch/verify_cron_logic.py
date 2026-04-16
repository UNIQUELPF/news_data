from datetime import datetime, timedelta
from croniter import croniter

def test_logic(cron_expr, last_run_at, now):
    try:
        base_time = last_run_at if last_run_at else (now - timedelta(minutes=60))
        it = croniter(cron_expr, base_time)
        next_run = it.get_next(datetime)
        should_run = next_run <= now
        print(f"Cron: {cron_expr:15} | Last: {last_run_at.strftime('%H:%M') if last_run_at else 'None':5} | Now: {now.strftime('%H:%M'):5} | Next: {next_run.strftime('%H:%M'):5} | Should Run: {should_run}")
        return should_run
    except Exception as e:
        print(f"Error for {cron_expr}: {e}")
        return False

# Test cases
now = datetime(2026, 4, 16, 10, 6)

print("=== Standard matches ===")
test_logic("*/5 * * * *", datetime(2026, 4, 16, 10, 0), now) # True (due at 10:05)
test_logic("*/5 * * * *", datetime(2026, 4, 16, 10, 5), now) # False (next is 10:10)
test_logic("0 * * * *", datetime(2026, 4, 16, 9, 0), now)    # True (due at 10:00)
test_logic("0 0 * * *", datetime(2026, 4, 15, 0, 0), now)   # True (due at 00:00)

print("\n=== First run matches (None) ===")
test_logic("*/5 * * * *", None, now) # True (due at 09:10, 09:15... 10:05)
test_logic("0 * * * *", None, now)    # True (due at 10:00)
test_logic("0 11 * * *", None, now)   # False (next is 11:00)

print("\n=== Advanced features ===")
test_logic("0 0 * * MON", datetime(2026, 4, 12, 0, 0), now) # 2026-04-13 is Monday. False (it's Thursday)
# Wait, 2026-04-13 was Monday. Today is Thursday (16th).
# If it last ran on 12th (Sunday), it should have run on 13th (Monday).
test_logic("0 0 * * MON", datetime(2026, 4, 12, 0, 0), now) # Should be True

print("\n=== List and Range ===")
test_logic("1,6,11 * * * *", datetime(2026, 4, 16, 10, 0), now) # True (due at 10:01)
test_logic("1-5 * * * *", datetime(2026, 4, 16, 10, 0), now)    # True (due at 10:01)
