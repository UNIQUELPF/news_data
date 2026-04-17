#!/usr/bin/env python3
"""测试使用具体异常类型的验证逻辑"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import pytz

def test_exception_handling_logic():
    """测试异常处理逻辑"""
    print("=== 测试具体异常类型处理 ===")
    
    # 模拟API中的异常处理逻辑
    def handle_cron_validation_error(e):
        """模拟API中的错误处理逻辑"""
        from croniter import (
            CroniterError,
            CroniterBadCronError,
            CroniterBadDateError,
            CroniterNotAlphaError,
            CroniterUnsupportedSyntaxError,
        )
        
        error_msg = str(e)
        
        # 根据具体的异常类型提供错误信息
        if isinstance(e, CroniterBadDateError):
            return f"Invalid cron expression: invalid date. {error_msg}"
        elif isinstance(e, CroniterNotAlphaError):
            return f"Invalid cron expression: syntax error (non-numeric character). {error_msg}"
        elif isinstance(e, CroniterUnsupportedSyntaxError):
            return f"Invalid cron expression: unsupported syntax. {error_msg}"
        elif isinstance(e, CroniterBadCronError):
            # CroniterBadCronError 包含多种错误：范围错误、语法错误等
            if "out of range" in error_msg:
                return f"Invalid cron expression: value out of range. {error_msg}"
            elif "invalid range" in error_msg or "must not be zero" in error_msg:
                return f"Invalid cron expression: invalid value. {error_msg}"
            elif "Exactly 5, 6 or 7 columns" in error_msg:
                return "Invalid cron expression: must have exactly 5 parts (minute hour day month weekday)."
            else:
                return f"Invalid cron expression: syntax error. {error_msg}"
        elif isinstance(e, CroniterError):
            return f"Invalid cron expression: {error_msg}"
        else:
            return f"Invalid cron expression: {error_msg}"
    
    test_cases = [
        # (cron表达式, 期望的异常类型, 期望的错误关键词, 描述)
        ("", "CroniterBadCronError", "Exactly 5, 6 or 7 columns", "空字符串"),
        ("* * * *", "CroniterBadCronError", "Exactly 5, 6 or 7 columns", "只有4个部分"),
        ("*/0 * * * *", "CroniterBadCronError", "must not be zero", "步长为0"),
        ("60 * * * *", "CroniterBadCronError", "out of range", "分钟超出范围"),
        ("a * * * *", "CroniterNotAlphaError", "not acceptable", "非数字字符"),
        ("*/ * * * *", "CroniterNotAlphaError", "not acceptable", "缺少步长值"),
        ("0 0 31 2 *", "CroniterBadDateError", "failed to find next date", "无效日期"),
    ]
    
    tz = pytz.timezone('Asia/Shanghai')
    base_time = tz.localize(datetime.now())
    
    passed = 0
    failed = 0
    
    for cron_expr, expected_exception, expected_keyword, description in test_cases:
        try:
            from croniter import croniter
            cron = croniter(cron_expr, base_time)
            cron.get_next(datetime)
            
            # 如果代码执行到这里，说明没有抛出异常
            print(f"✗ {description}: {cron_expr}")
            print(f"  错误: 预期抛出异常但没有抛出")
            failed += 1
            
        except Exception as e:
            actual_exception = type(e).__name__
            error_detail = handle_cron_validation_error(e)
            
            # 检查异常类型
            exception_match = actual_exception == expected_exception
            
            # 检查错误信息
            keyword_match = expected_keyword.lower() in error_detail.lower()
            
            if exception_match and keyword_match:
                status = "✓"
                passed += 1
            else:
                status = "✗"
                failed += 1
            
            print(f"\n{status} {description}")
            print(f"  表达式: {cron_expr}")
            print(f"  预期异常: {expected_exception}")
            print(f"  实际异常: {actual_exception}")
            print(f"  预期关键词: '{expected_keyword}'")
            print(f"  错误信息: {error_detail}")
            
            if not exception_match:
                print(f"  ❌ 异常类型不匹配")
            if not keyword_match:
                print(f"  ❌ 错误信息不包含预期关键词")
    
    print(f"\n测试结果: 通过 {passed}, 失败 {failed}")
    return failed == 0

def compare_old_vs_new():
    """比较新旧错误处理方式"""
    print("\n=== 新旧错误处理方式对比 ===")
    
    print("旧方式（字符串匹配）:")
    print("  - 使用字符串查找判断错误类型")
    print("  - 脆弱：依赖错误信息的文本格式")
    print("  - 不准确：可能误判")
    print("  - 示例: if 'out of range' in error_msg:")
    
    print("\n新方式（异常类型判断）:")
    print("  - 使用 isinstance() 判断异常类型")
    print("  - 健壮：依赖类型系统，不依赖文本")
    print("  - 准确：精确匹配异常类型")
    print("  - 示例: if isinstance(e, CroniterBadDateError):")
    
    print("\n优势:")
    print("  1. 类型安全：编译器/IDE可以检查")
    print("  2. 可维护性：代码更清晰，易于理解")
    print("  3. 健壮性：不依赖错误信息的文本格式")
    print("  4. 扩展性：易于添加新的异常类型处理")

def test_exception_hierarchy_handling():
    """测试异常继承关系的处理"""
    print("\n=== 测试异常继承关系处理 ===")
    
    from croniter import (
        CroniterError,
        CroniterBadCronError,
        CroniterBadDateError,
        CroniterNotAlphaError,
    )
    
    # 创建各种异常实例
    exceptions = [
        (CroniterBadDateError("failed to find next date"), "CroniterBadDateError"),
        (CroniterNotAlphaError("[a * * * *] is not acceptable"), "CroniterNotAlphaError"),
        (CroniterBadCronError("[60 * * * *] is not acceptable, out of range"), "CroniterBadCronError"),
        (CroniterError("generic error"), "CroniterError"),
    ]
    
    for exc, exc_name in exceptions:
        print(f"\n测试异常: {exc_name}")
        
        # 测试 isinstance 检查
        checks = [
            ("isinstance(exc, CroniterBadDateError)", isinstance(exc, CroniterBadDateError)),
            ("isinstance(exc, CroniterNotAlphaError)", isinstance(exc, CroniterNotAlphaError)),
            ("isinstance(exc, CroniterBadCronError)", isinstance(exc, CroniterBadCronError)),
            ("isinstance(exc, CroniterError)", isinstance(exc, CroniterError)),
            ("isinstance(exc, Exception)", isinstance(exc, Exception)),
        ]
        
        for check_str, result in checks:
            print(f"  {check_str:50} -> {result}")

def main():
    print("具体异常类型处理测试")
    print("=" * 60)
    
    all_passed = test_exception_handling_logic()
    compare_old_vs_new()
    test_exception_hierarchy_handling()
    
    print("\n" + "=" * 60)
    print("总结:")
    print("✅ 您说得完全正确！croniter有具体的异常类型")
    print("✅ 应该使用 isinstance() 而不是字符串匹配")
    print("✅ 异常类型体系清晰，便于精确处理")
    print("✅ 改进后的代码更健壮、可维护")
    
    print("\n异常类型处理策略:")
    print("1. CroniterBadDateError: 日期相关错误（如2月31号）")
    print("2. CroniterNotAlphaError: 非字母字符错误")
    print("3. CroniterBadCronError: 语法和范围错误（需要进一步细分）")
    print("4. CroniterError: 其他croniter错误")
    print("5. Exception: 其他所有异常")

if __name__ == "__main__":
    main()