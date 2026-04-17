#!/usr/bin/env python3
"""测试croniter库的表达式校验功能"""

from datetime import datetime
import croniter
import pytz

def test_croniter_validation():
    """测试croniter的表达式校验功能"""
    print("=== 测试croniter表达式校验 ===")
    
    test_cases = [
        # (cron表达式, 是否有效, 描述)
        ("*/30 * * * *", True, "有效的简单表达式"),
        ("*/5 * * * *", True, "有效的简单表达式"),
        ("0 * * * *", True, "每小时0分"),
        ("0 0 * * *", True, "每天午夜"),
        ("30 2 * * 1", True, "每周一2:30"),
        
        # 无效表达式
        ("", False, "空字符串"),
        ("* * * *", False, "只有4个部分"),
        ("* * * * * *", False, "有6个部分"),
        ("*/0 * * * *", False, "步长为0"),
        ("60 * * * *", False, "分钟超出范围"),
        ("* 24 * * *", False, "小时超出范围"),
        ("* * 32 * *", False, "日期超出范围"),
        ("* * * 13 *", False, "月份超出范围"),
        ("* * * * 7", False, "星期超出范围"),
        ("*/ * * * *", False, "缺少步长值"),
        ("a * * * *", False, "非数字字符"),
        ("1-60 * * * *", False, "范围超出限制"),
        ("*/30 * * * * extra", False, "多余字符"),
    ]
    
    for cron_expr, expected_valid, description in test_cases:
        try:
            # 尝试创建croniter对象来验证表达式
            # 使用当前时间作为参考时间
            test_time = datetime.now()
            tz = pytz.timezone('Asia/Shanghai')
            test_time_tz = tz.localize(test_time)
            
            cron = croniter.croniter(cron_expr, test_time_tz)
            
            # 如果创建成功，尝试获取下一个执行时间
            next_time = cron.get_next(datetime)
            
            is_valid = True
            status = "✓" if is_valid == expected_valid else "✗"
            
            if is_valid:
                print(f"{status} {cron_expr:20} -> 有效 ({description})")
                print(f"    下一个执行时间: {next_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                print(f"{status} {cron_expr:20} -> 无效 ({description})")
                
        except Exception as e:
            is_valid = False
            status = "✓" if is_valid == expected_valid else "✗"
            print(f"{status} {cron_expr:20} -> 无效 ({description})")
            print(f"    错误信息: {type(e).__name__}: {str(e)}")
        
        print()

def test_current_validation():
    """测试当前实现的校验方式"""
    print("\n=== 测试当前实现的校验方式 ===")
    
    test_cases = [
        ("*/30 * * * *", True, "有效的简单表达式"),
        ("* * * *", False, "只有4个部分"),
        ("* * * * * *", False, "有6个部分"),
        ("*/0 * * * *", True, "当前实现不会检测步长为0"),
        ("60 * * * *", True, "当前实现不会检测范围"),
        ("a * * * *", True, "当前实现不会检测非数字字符"),
    ]
    
    for cron_expr, expected_valid, description in test_cases:
        parts = cron_expr.split()
        is_valid = len(parts) == 5
        status = "✓" if is_valid == expected_valid else "✗"
        
        if is_valid:
            print(f"{status} {cron_expr:20} -> 有效 ({description})")
        else:
            print(f"{status} {cron_expr:20} -> 无效 ({description})")

def compare_validation_methods():
    """比较两种校验方式的差异"""
    print("\n=== 校验方式对比 ===")
    print("当前实现:")
    print("  - 只检查是否有5个部分")
    print("  - 不验证每个部分的语法")
    print("  - 不验证数值范围")
    print("  - 不验证特殊字符")
    print()
    print("croniter校验:")
    print("  - 完整的语法验证")
    print("  - 数值范围检查")
    print("  - 特殊字符验证")
    print("  - 可以计算下一个执行时间")
    print("  - 支持时区")

def demonstrate_croniter_features():
    """展示croniter的高级功能"""
    print("\n=== croniter高级功能展示 ===")
    
    try:
        from croniter import croniter
        import pytz
        
        tz = pytz.timezone('Asia/Shanghai')
        base_time = tz.localize(datetime(2024, 1, 1, 0, 0))
        
        # 1. 计算下一个执行时间
        cron = croniter("*/30 * * * *", base_time)
        print("1. 计算执行时间序列:")
        for i in range(3):
            next_time = cron.get_next(datetime)
            print(f"   第{i+1}次: {next_time.strftime('%Y-%m-%d %H:%M')}")
        
        # 2. 验证复杂表达式
        print("\n2. 复杂表达式验证:")
        complex_exprs = [
            "0 0 L * *",        # 每月最后一天
            "0 0 15W * *",      # 最近的工作日
            "0 0 * * 1#2",      # 每月的第二个周一
            "0 0 1,15 * *",     # 每月1号和15号
            "0 8-18 * * 1-5",   # 工作日8点到18点每小时
        ]
        
        for expr in complex_exprs:
            try:
                cron = croniter(expr, base_time)
                next_time = cron.get_next(datetime)
                print(f"   {expr:15} -> 有效, 下一个: {next_time.strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                print(f"   {expr:15} -> 无效: {e}")
                
    except ImportError:
        print("croniter库未安装")

def main():
    print("Cron表达式校验功能测试")
    print("=" * 60)
    
    test_croniter_validation()
    test_current_validation()
    compare_validation_methods()
    demonstrate_croniter_features()
    
    print("\n" + "=" * 60)
    print("建议:")
    print("1. 使用croniter进行完整的cron表达式验证")
    print("2. 在update_periodic_schedule函数中添加croniter验证")
    print("3. 提供更详细的错误信息给前端")
    print("4. 考虑添加表达式预览功能（显示下一个执行时间）")

if __name__ == "__main__":
    main()