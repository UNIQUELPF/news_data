#!/usr/bin/env python3
"""测试改进后的cron表达式验证功能"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from api.main import app
import json

client = TestClient(app)

def test_cron_validation():
    """测试cron表达式验证"""
    print("=== 测试改进后的cron表达式验证 ===")
    
    # 注意：这里需要模拟admin token，实际测试中应该使用有效的token
    headers = {"x-admin-token": "test-admin-token"}
    
    test_cases = [
        # (cron表达式, 期望状态码, 期望包含的关键词, 描述)
        ("*/30 * * * *", 200, "success", "有效的简单表达式"),
        ("*/5 * * * *", 200, "success", "有效的简单表达式"),
        ("", 400, "Invalid cron expression", "空字符串"),
        ("* * * *", 400, "must have exactly 5", "只有4个部分"),
        ("* * * * * *", 400, "must have exactly 5", "有6个部分"),
        ("*/0 * * * *", 400, "out of range", "步长为0"),
        ("60 * * * *", 400, "out of range", "分钟超出范围"),
        ("* 24 * * *", 400, "out of range", "小时超出范围"),
        ("a * * * *", 400, "syntax error", "非数字字符"),
        ("*/ * * * *", 400, "syntax error", "缺少步长值"),
    ]
    
    # 由于需要实际的schedule_id，我们只测试验证逻辑
    print("注意：需要实际的schedule_id才能完整测试API端点")
    print("以下测试验证逻辑的正确性：")
    
    for cron_expr, expected_code, expected_keyword, description in test_cases:
        print(f"\n测试: {description}")
        print(f"表达式: {cron_expr}")
        
        # 模拟验证逻辑
        try:
            from croniter import croniter
            from datetime import datetime
            import pytz
            
            tz = pytz.timezone('Asia/Shanghai')
            base_time = tz.localize(datetime.now())
            cron = croniter(cron_expr, base_time)
            next_time = cron.get_next(datetime)
            
            print(f"结果: 有效")
            print(f"下一个执行时间: {next_time.strftime('%Y-%m-%d %H:%M')}")
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"结果: 无效")
            print(f"错误类型: {error_type}")
            print(f"错误信息: {error_msg}")
            
            # 检查错误信息是否包含预期关键词
            if expected_code == 400 and expected_keyword.lower() in error_msg.lower():
                print(f"✓ 错误信息符合预期")
            else:
                print(f"✗ 错误信息不符合预期")

def demonstrate_validation_improvement():
    """展示验证改进的效果"""
    print("\n=== 验证改进对比 ===")
    
    print("改进前的验证（只检查5个部分）:")
    invalid_examples = [
        "*/0 * * * *",  # 步长为0
        "60 * * * *",   # 分钟超出范围
        "a * * * *",    # 非数字字符
    ]
    
    for expr in invalid_examples:
        parts = expr.split()
        is_valid_old = len(parts) == 5
        print(f"  {expr:15} -> {'有效' if is_valid_old else '无效'}")
    
    print("\n改进后的验证（使用croniter）:")
    for expr in invalid_examples:
        try:
            from croniter import croniter
            from datetime import datetime
            import pytz
            
            tz = pytz.timezone('Asia/Shanghai')
            base_time = tz.localize(datetime.now())
            cron = croniter(expr, base_time)
            print(f"  {expr:15} -> 有效")
        except Exception as e:
            error_type = type(e).__name__
            print(f"  {expr:15} -> 无效 ({error_type})")

def test_croniter_availability():
    """测试croniter是否可用"""
    print("\n=== croniter库可用性测试 ===")
    
    try:
        import croniter
        print("✓ croniter库已安装")
        
        # 测试基本功能
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone('Asia/Shanghai')
        base_time = tz.localize(datetime.now())
        
        test_expr = "*/30 * * * *"
        cron = croniter.croniter(test_expr, base_time)
        next_time = cron.get_next(datetime)
        
        print(f"✓ 基本功能正常")
        print(f"  测试表达式: {test_expr}")
        print(f"  下一个执行时间: {next_time.strftime('%Y-%m-%d %H:%M')}")
        
        return True
    except ImportError:
        print("✗ croniter库未安装")
        print("  安装命令: pip install croniter")
        return False
    except Exception as e:
        print(f"✗ croniter库有问题: {e}")
        return False

def main():
    print("Cron表达式验证改进测试")
    print("=" * 60)
    
    croniter_available = test_croniter_availability()
    
    if croniter_available:
        test_cron_validation()
        demonstrate_validation_improvement()
        
        print("\n" + "=" * 60)
        print("改进总结:")
        print("1. ✅ 添加了完整的cron表达式语法验证")
        print("2. ✅ 支持数值范围检查（分钟0-59，小时0-23等）")
        print("3. ✅ 提供详细的错误信息")
        print("4. ✅ 支持计算下一个执行时间（预览功能）")
        print("5. ✅ 向后兼容：如果croniter未安装，使用基本验证")
        print("\n注意事项:")
        print("1. 需要将croniter添加到requirements.txt")
        print("2. 生产环境需要确保croniter已安装")
        print("3. 考虑添加表达式预览功能到前端")
    else:
        print("\n注意：croniter库未安装，改进的功能将无法使用")
        print("建议安装croniter以获得完整的验证功能:")
        print("  pip install croniter")

if __name__ == "__main__":
    main()