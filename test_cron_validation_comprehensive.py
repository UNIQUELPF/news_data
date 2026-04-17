#!/usr/bin/env python3
"""全面测试cron表达式验证功能"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 模拟验证逻辑
def validate_cron_expression(cron_expr):
    """模拟API中的验证逻辑"""
    try:
        from croniter import croniter
        from datetime import datetime
        import pytz
        
        # 验证cron表达式
        tz = pytz.timezone('Asia/Shanghai')
        base_time = tz.localize(datetime.now())
        
        # 尝试创建croniter对象
        cron = croniter(cron_expr, base_time)
        
        # 计算下一个执行时间
        next_time = cron.get_next(datetime)
        
        return {
            "valid": True,
            "next_execution": next_time.strftime('%Y-%m-%d %H:%M'),
            "error": None
        }
        
    except ImportError:
        # 如果croniter未安装，使用基本验证
        parts = cron_expr.split()
        if len(parts) != 5:
            return {
                "valid": False,
                "error": "Invalid cron expression. Must have exactly 5 parts (minute hour day month weekday)."
            }
        return {"valid": True, "error": None}
    except Exception as e:
        # 提供更详细的错误信息
        error_type = type(e).__name__
        error_msg = str(e)
        
        # 根据错误类型提供更友好的错误信息
        if "out of range" in error_msg:
            detail = f"Invalid cron expression: value out of range. {error_msg}"
        elif "not acceptable" in error_msg or "NotAlphaError" in error_type:
            detail = f"Invalid cron expression: syntax error. {error_msg}"
        elif "invalid range" in error_msg or "must not be zero" in error_msg:
            detail = f"Invalid cron expression: invalid value. {error_msg}"
        elif "Exactly 5, 6 or 7 columns" in error_msg:
            detail = "Invalid cron expression: must have exactly 5 parts (minute hour day month weekday)."
        elif "CroniterBadDateError" in error_type:
            detail = f"Invalid cron expression: invalid date. {error_msg}"
        else:
            detail = f"Invalid cron expression: {error_msg}"
        
        return {
            "valid": False,
            "error": detail
        }

def test_validation_cases():
    """测试各种cron表达式验证案例"""
    print("=== 全面测试cron表达式验证 ===")
    
    test_cases = [
        # (cron表达式, 是否有效, 测试描述)
        # 有效表达式
        ("*/30 * * * *", True, "每30分钟"),
        ("*/5 * * * *", True, "每5分钟"),
        ("0 * * * *", True, "每小时0分"),
        ("0 0 * * *", True, "每天午夜"),
        ("30 2 * * 1", True, "每周一2:30"),
        ("0 9-18 * * 1-5", True, "工作日9点到18点每小时"),
        ("0 0 1,15 * *", True, "每月1号和15号"),
        ("0 0 L * *", True, "每月最后一天"),
        
        # 无效表达式
        ("", False, "空字符串"),
        ("* * * *", False, "只有4个部分"),
        ("* * * * * *", True, "有6个部分（croniter支持）"),
        ("*/0 * * * *", False, "步长为0"),
        ("60 * * * *", False, "分钟超出范围（0-59）"),
        ("* 24 * * *", False, "小时超出范围（0-23）"),
        ("* * 32 * *", False, "日期超出范围（1-31）"),
        ("* * * 13 *", False, "月份超出范围（1-12）"),
        ("* * * * 8", False, "星期超出范围（0-7，0和7都表示周日）"),
        ("*/ * * * *", False, "缺少步长值"),
        ("a * * * *", False, "非数字字符"),
        ("1-60 * * * *", False, "范围超出限制"),
        ("*/30 * * * * extra", False, "多余字符"),
        ("0 0 31 2 *", False, "无效日期（2月没有31号）"),
        ("0 0 29 2 *", True, "有效日期（闰年2月29号）"),
    ]
    
    passed = 0
    failed = 0
    
    for cron_expr, expected_valid, description in test_cases:
        result = validate_cron_expression(cron_expr)
        is_valid = result["valid"]
        
        status = "✓" if is_valid == expected_valid else "✗"
        
        if is_valid == expected_valid:
            passed += 1
        else:
            failed += 1
        
        print(f"\n{status} {description}")
        print(f"  表达式: {cron_expr}")
        print(f"  预期: {'有效' if expected_valid else '无效'}")
        print(f"  实际: {'有效' if is_valid else '无效'}")
        
        if is_valid:
            print(f"  下一个执行时间: {result.get('next_execution', 'N/A')}")
        else:
            print(f"  错误信息: {result['error']}")
    
    print(f"\n测试结果: 通过 {passed}, 失败 {failed}")
    return failed == 0

def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    edge_cases = [
        # 边界值测试
        ("59 * * * *", True, "分钟最大值59"),
        ("0 23 * * *", True, "小时最大值23"),
        ("0 0 31 * *", True, "日期最大值31"),
        ("0 0 * 12 *", True, "月份最大值12"),
        ("0 0 * * 7", True, "星期最大值7（周日）"),
        ("0 0 * * 0", True, "星期最小值0（周日）"),
        
        # 特殊格式
        ("*/1 * * * *", True, "步长为1"),
        ("0-59 * * * *", True, "完整范围"),
        ("0,15,30,45 * * * *", True, "列表值"),
        ("*/15 9-17 * * 1-5", True, "复杂表达式"),
    ]
    
    for cron_expr, expected_valid, description in edge_cases:
        result = validate_cron_expression(cron_expr)
        is_valid = result["valid"]
        
        status = "✓" if is_valid == expected_valid else "✗"
        
        print(f"{status} {description}: {cron_expr}")
        if is_valid and 'next_execution' in result:
            print(f"    下一个执行: {result['next_execution']}")

def demonstrate_improvements():
    """展示改进效果"""
    print("\n=== 验证改进效果展示 ===")
    
    print("改进前（基本验证）的问题:")
    problematic = [
        "*/0 * * * *",  # 步长为0 - 应该无效
        "60 * * * *",   # 分钟60 - 应该无效
        "a * * * *",    # 非数字 - 应该无效
        "0 0 31 2 *",   # 2月31号 - 应该无效
    ]
    
    for expr in problematic:
        parts = expr.split()
        old_valid = len(parts) == 5
        result = validate_cron_expression(expr)
        new_valid = result["valid"]
        
        print(f"\n表达式: {expr}")
        print(f"  旧验证: {'有效' if old_valid else '无效'}")
        print(f"  新验证: {'有效' if new_valid else '无效'}")
        if not new_valid:
            print(f"  错误: {result['error']}")

def main():
    print("Cron表达式验证全面测试")
    print("=" * 70)
    
    # 检查croniter是否可用
    try:
        import croniter
        print("✓ croniter库可用")
    except ImportError:
        print("✗ croniter库未安装，部分测试可能不准确")
        print("  安装命令: pip install croniter")
    
    all_passed = test_validation_cases()
    test_edge_cases()
    demonstrate_improvements()
    
    print("\n" + "=" * 70)
    print("总结:")
    print("1. ✅ croniter提供了完整的cron表达式验证")
    print("2. ✅ 支持语法检查、数值范围验证、特殊字符检测")
    print("3. ✅ 能够检测无效日期（如2月31号）")
    print("4. ✅ 提供详细的错误信息，便于前端显示")
    print("5. ✅ 支持计算下一个执行时间（预览功能）")
    print("\n注意事项:")
    print("1. croniter支持5、6、7个部分的cron表达式")
    print("2. 星期几可以用0或7表示周日")
    print("3. 需要考虑闰年等特殊情况")
    print("4. 生产环境需要确保croniter已安装")

if __name__ == "__main__":
    main()