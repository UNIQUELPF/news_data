#!/usr/bin/env python3
"""比较当前cron解析器和croniter库的功能"""

from datetime import datetime, timedelta
import sys

# 模拟当前系统的cron解析器
def _match_cron_field(field_expr, value, max_val):
    """Check if a value matches a single cron field expression.
    Supports: * (any), */N (every N), N (exact), N,M (list), N-M (range).
    """
    for part in field_expr.split(','):
        part = part.strip()
        if part == '*':
            return True
        if '/' in part:
            base, step = part.split('/', 1)
            step = int(step)
            if base == '*':
                if value % step == 0:
                    return True
            else:
                base_val = int(base)
                if value >= base_val and (value - base_val) % step == 0:
                    return True
        elif '-' in part:
            lo, hi = part.split('-', 1)
            if int(lo) <= value <= int(hi):
                return True
        else:
            if value == int(part):
                return True
    return False

def _cron_matches_current(cron_expr, dt):
    """Check if a datetime matches a cron expression (minute hour dom month dow)."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    return (
        _match_cron_field(minute, dt.minute, 59) and
        _match_cron_field(hour, dt.hour, 23) and
        _match_cron_field(dom, dt.day, 31) and
        _match_cron_field(month, dt.month, 12) and
        _match_cron_field(dow, dt.isoweekday() % 7, 6)  # 0=Sunday
    )

def test_current_implementation():
    """测试当前实现"""
    print("=== 测试当前cron解析器实现 ===")
    
    test_cases = [
        # (cron表达式, 测试时间, 期望结果)
        ('*/30 * * * *', datetime(2024, 1, 1, 0, 0), True),   # 整点
        ('*/30 * * * *', datetime(2024, 1, 1, 0, 30), True),  # 30分
        ('*/30 * * * *', datetime(2024, 1, 1, 0, 15), False), # 15分
        ('*/5 * * * *', datetime(2024, 1, 1, 0, 0), True),    # 0分
        ('*/5 * * * *', datetime(2024, 1, 1, 0, 5), True),    # 5分
        ('*/5 * * * *', datetime(2024, 1, 1, 0, 7), False),   # 7分
        ('0 * * * *', datetime(2024, 1, 1, 1, 0), True),      # 每小时0分
        ('0 * * * *', datetime(2024, 1, 1, 1, 30), False),    # 每小时30分
        ('0 0 * * *', datetime(2024, 1, 1, 0, 0), True),      # 午夜
        ('0 0 * * *', datetime(2024, 1, 1, 12, 0), False),    # 中午
        ('30 2 * * 1', datetime(2024, 1, 1, 2, 30), True),    # 周一2:30 (2024-01-01是周一)
        ('30 2 * * 1', datetime(2024, 1, 2, 2, 30), False),   # 周二2:30
    ]
    
    passed = 0
    failed = 0
    
    for cron_expr, test_time, expected in test_cases:
        result = _cron_matches_current(cron_expr, test_time)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {cron_expr:15} {test_time.strftime('%Y-%m-%d %H:%M')} -> {result} (期望: {expected})")
    
    print(f"\n通过: {passed}, 失败: {failed}")
    return failed == 0

def test_croniter_if_available():
    """测试croniter库（如果可用）"""
    print("\n=== 测试croniter库 ===")
    
    try:
        from croniter import croniter
        import pytz
        
        # 设置时区为UTC+8
        tz = pytz.timezone('Asia/Shanghai')
        
        test_cases = [
            ('*/30 * * * *', datetime(2024, 1, 1, 0, 0)),
            ('*/30 * * * *', datetime(2024, 1, 1, 0, 30)),
            ('*/30 * * * *', datetime(2024, 1, 1, 0, 15)),
            ('*/5 * * * *', datetime(2024, 1, 1, 0, 0)),
            ('*/5 * * * *', datetime(2024, 1, 1, 0, 5)),
            ('*/5 * * * *', datetime(2024, 1, 1, 0, 7)),
            ('0 * * * *', datetime(2024, 1, 1, 1, 0)),
            ('0 * * * *', datetime(2024, 1, 1, 1, 30)),
            ('0 0 * * *', datetime(2024, 1, 1, 0, 0)),
            ('0 0 * * *', datetime(2024, 1, 1, 12, 0)),
            ('30 2 * * 1', datetime(2024, 1, 1, 2, 30)),
            ('30 2 * * 1', datetime(2024, 1, 2, 2, 30)),
        ]
        
        print("croniter库可用！")
        print("示例用法:")
        for cron_expr, test_time in test_cases[:3]:
            # 转换为有时区的时间
            test_time_tz = tz.localize(test_time)
            cron = croniter(cron_expr, test_time_tz)
            next_time = cron.get_next(datetime)
            prev_time = cron.get_prev(datetime)
            
            print(f"  {cron_expr:15} {test_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"    下一个执行时间: {next_time.strftime('%Y-%m-%d %H:%M')}")
            print(f"    上一个执行时间: {prev_time.strftime('%Y-%m-%d %H:%M')}")
        
        return True
    except ImportError:
        print("croniter库未安装")
        print("安装命令: pip install croniter")
        return False
    except Exception as e:
        print(f"测试croniter时出错: {e}")
        return False

def analyze_limitations():
    """分析当前实现的局限性"""
    print("\n=== 当前cron解析器的局限性分析 ===")
    
    limitations = [
        "1. 不支持高级cron语法:",
        "   - L (最后一天): '0 0 L * *' 每月最后一天",
        "   - W (工作日): '0 0 15W * *' 最近的工作日",
        "   - # (第N个星期X): '0 0 * * 1#2' 每月的第二个周一",
        "",
        "2. 时区处理简单:",
        "   - 硬编码为UTC+8",
        "   - 不支持夏令时",
        "",
        "3. 性能问题:",
        "   - 每分钟遍历检查，最多60次",
        "   - 对于长时间未运行的任务，效率低下",
        "",
        "4. 边界情况:",
        "   - 月份天数处理不完整（2月28/29天）",
        "   - 星期几和日期的组合可能有问题",
        "",
        "5. 错误处理:",
        "   - 无效cron表达式可能崩溃",
        "   - 缺少详细的错误信息",
    ]
    
    for line in limitations:
        print(line)

def main():
    print("Cron解析器比较测试")
    print("=" * 50)
    
    # 测试当前实现
    current_ok = test_current_implementation()
    
    # 测试croniter
    croniter_available = test_croniter_if_available()
    
    # 分析局限性
    analyze_limitations()
    
    print("\n" + "=" * 50)
    print("总结:")
    
    if current_ok:
        print("✓ 当前实现能处理基本cron表达式")
    else:
        print("✗ 当前实现存在测试失败")
    
    if croniter_available:
        print("✓ croniter库功能更强大，推荐用于生产环境")
    else:
        print("✗ croniter库未安装")
    
    print("\n建议:")
    if croniter_available:
        print("1. 考虑用croniter替换当前实现，以获得更好的功能和健壮性")
        print("2. 需要添加依赖: pip install croniter pytz")
        print("3. 修改orchestrate.py中的_cron_matches函数")
    else:
        print("1. 当前实现满足基本需求，但可以考虑改进")
        print("2. 建议至少修复时区处理和边界情况")
        print("3. 或者安装croniter: pip install croniter")

if __name__ == "__main__":
    main()