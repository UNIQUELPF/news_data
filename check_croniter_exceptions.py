#!/usr/bin/env python3
"""检查croniter库的异常类型"""

import croniter
from datetime import datetime
import pytz

def list_croniter_exceptions():
    """列出croniter的所有异常类型"""
    print("=== croniter异常类型 ===")
    
    # 查看croniter模块的所有属性
    for attr_name in dir(croniter):
        attr = getattr(croniter, attr_name)
        if isinstance(attr, type) and issubclass(attr, Exception):
            print(f"- {attr_name}: {attr}")
    
    print("\n=== 测试各种错误对应的异常类型 ===")
    
    test_cases = [
        ("", "空字符串"),
        ("* * * *", "只有4个部分"),
        ("*/0 * * * *", "步长为0"),
        ("60 * * * *", "分钟超出范围"),
        ("a * * * *", "非数字字符"),
        ("*/ * * * *", "缺少步长值"),
        ("0 0 31 2 *", "无效日期"),
    ]
    
    tz = pytz.timezone('Asia/Shanghai')
    base_time = tz.localize(datetime.now())
    
    for cron_expr, description in test_cases:
        try:
            cron = croniter.croniter(cron_expr, base_time)
            cron.get_next(datetime)
            print(f"{cron_expr:20} -> 有效 ({description})")
        except Exception as e:
            exception_type = type(e).__name__
            module = e.__class__.__module__
            full_name = f"{module}.{exception_type}" if module != "builtins" else exception_type
            print(f"{cron_expr:20} -> {exception_type} ({description})")
            print(f"    完整名称: {full_name}")
            print(f"    错误信息: {str(e)}")

def check_exception_hierarchy():
    """检查异常类的继承关系"""
    print("\n=== 异常类继承关系 ===")
    
    # 获取所有异常类
    exception_classes = []
    for attr_name in dir(croniter):
        attr = getattr(croniter, attr_name)
        if isinstance(attr, type) and issubclass(attr, Exception):
            exception_classes.append(attr)
    
    # 打印继承关系
    for exc_class in exception_classes:
        print(f"\n{exc_class.__name__}:")
        bases = exc_class.__bases__
        for base in bases:
            print(f"  ← {base.__name__}")

def create_custom_validation():
    """创建使用具体异常类型的验证函数"""
    print("\n=== 使用具体异常类型的验证函数 ===")
    
    # 导入所有可能的异常
    from croniter import (
        CroniterError,
        CroniterBadCronError,
        CroniterBadDateError,
        CroniterNotAlphaError,
    )
    
    def validate_cron_with_specific_exceptions(cron_expr):
        """使用具体异常类型进行验证"""
        try:
            tz = pytz.timezone('Asia/Shanghai')
            base_time = tz.localize(datetime.now())
            cron = croniter.croniter(cron_expr, base_time)
            next_time = cron.get_next(datetime)
            return {"valid": True, "next_time": next_time}
            
        except CroniterBadCronError as e:
            # 处理cron表达式语法错误
            return {"valid": False, "error_type": "CroniterBadCronError", "error": str(e)}
            
        except CroniterBadDateError as e:
            # 处理日期错误
            return {"valid": False, "error_type": "CroniterBadDateError", "error": str(e)}
            
        except CroniterNotAlphaError as e:
            # 处理非字母字符错误
            return {"valid": False, "error_type": "CroniterNotAlphaError", "error": str(e)}
            
        except CroniterError as e:
            # 处理其他croniter错误
            return {"valid": False, "error_type": "CroniterError", "error": str(e)}
            
        except Exception as e:
            # 处理其他异常
            return {"valid": False, "error_type": type(e).__name__, "error": str(e)}
    
    # 测试
    test_cases = [
        ("*/30 * * * *", "有效表达式"),
        ("60 * * * *", "分钟超出范围"),
        ("a * * * *", "非数字字符"),
        ("0 0 31 2 *", "无效日期"),
    ]
    
    for cron_expr, description in test_cases:
        result = validate_cron_with_specific_exceptions(cron_expr)
        print(f"\n{description}: {cron_expr}")
        if result["valid"]:
            print(f"  结果: 有效")
            print(f"  下一个时间: {result['next_time'].strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"  结果: 无效")
            print(f"  异常类型: {result['error_type']}")
            print(f"  错误信息: {result['error']}")

def main():
    print("croniter异常类型分析")
    print("=" * 60)
    
    list_croniter_exceptions()
    check_exception_hierarchy()
    create_custom_validation()
    
    print("\n" + "=" * 60)
    print("建议:")
    print("1. 使用具体的异常类型而不是字符串匹配")
    print("2. CroniterBadCronError: 处理语法和范围错误")
    print("3. CroniterBadDateError: 处理日期错误")
    print("4. CroniterNotAlphaError: 处理非字母字符错误")
    print("5. CroniterError: 基类，处理其他错误")

if __name__ == "__main__":
    main()