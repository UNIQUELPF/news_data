---
name: batch_optimize_spider
description: Use when the user wants to optimize or test multiple spiders at once — batch scanning a directory for V2 compliance, parallel repairing spiders, or batch verification testing. Triggers on "batch optimize", "批量优化", "批量测试", "批量检查", "all spiders in <directory>".
---

# Batch Spider Optimization & Testing

## When to Use

- "批量检查/优化/测试 <country> 的爬虫"
- "扫描所有爬虫看哪些需要 V2 升级"
- "把这个目录下的爬虫都跑一遍测试"

This skill is an **orchestration layer**. It uses `modernize_spider`'s checklist for scanning and `debug_spider`'s diagnostic rules for failure analysis.

## Architecture

```
batch_optimize_spider (编排层)
    ├── Phase 1: 批量扫描 ── 读所有爬虫，输出 V2 合规矩阵
    ├── Phase 2: 并行修复 ── 派发 parallel agents，1 agent/spider
    └── Phase 3: 批量验证 ── 批量跑测试，收集通过/失败结果
```

---

## Phase 1: Batch Scan (只读，不改代码)

### Step 1.1: 收集目标

确定扫描范围：
- 单目录: `spiders/brunei/`
- 多目录: `spiders/brunei/ spiders/cambodia/`
- 按国家: Brics 子目录如 `spiders/brics/uae/`

### Step 1.2: 逐文件扫描

对每个 spider `.py` 文件，对照以下 7 项快速扫描：

| # | 检查项 | 检测方式 |
|---|--------|---------|
| 1 | `SmartSpider` 继承 | `grep "SmartSpider" <file>` |
| 2 | `use_curl_cffi = True` | `grep "use_curl_cffi" <file>` |
| 3 | 列表页提取 `publish_time` | 读 `parse_list`/`parse`，检查是否提取日期 |
| 4 | 调用 `should_process()` | `grep "should_process" <file>` |
| 5 | `has_valid_item_in_window` 断路器 | `grep "has_valid_item_in_window" <file>` |
| 6 | 无硬编码页数上限 `page < N` | `grep -E "page\s*<\s*\d+|offset\s*<\s*\d+" <file>` |
| 7 | `fallback_content_selector` | `grep "fallback_content_selector" <file>` |

对每个 Spider 给出状态：PASS / WARN / FAIL。

### Step 1.3: 输出扫描矩阵

输出一张表格，列名：`Spider | SmartSpider | curl_cffi | Date | should_process | CircuitBreaker | NoPageLimit | Fallback | Status`

Status 规则：
- **READY**: 7/7 PASS — 已经是标准 V2
- **MINOR**: 5-6/7 PASS — 缺部分配置项
- **MAJOR**: < 5/7 PASS — 需要完整 V2 升级

### Step 1.4: 向用户呈现矩阵 + 建议

告诉用户：哪些可以直接批量测试，哪些需要先修复，哪些需要完整重写。让用户决定下一步。

---

## Phase 2: Parallel Repair

### Step 2.1: 确认修复范围

根据 Phase 1 的扫描结果，用户指定哪些爬虫需要修复。

### Step 2.2: 派发 Parallel Agents

使用 `Agent` 工具同时派发，每个 agent 修复一个 spider：

```
Agent 1: "用 modernize_spider 规范修复 spiders/brunei/bn_pmo_spider.py"
Agent 2: "用 modernize_spider 规范修复 spiders/brunei/bn_brudirect_spider.py"
```

**规则**：
- 每个 agent 修复**一个** spider
- 所有 agent 并行派发（单条消息中多个 Agent tool call）
- 每个 agent 修复完必须输出：改动清单 + 达标情况
- 所有 agent 完成后再进入 Phase 3

### Step 2.3: 汇总修复结果

收集所有 agent 的输出，汇总成表格呈现给用户。

---

## Phase 3: Batch Verification

### Step 3.1: 批量测试命令

对已修复的爬虫逐个跑 `CLOSESPIDER_ITEMCOUNT=2` 验证：

```bash
# 单个爬虫测试
docker-compose exec crawl-worker bash -c \
  "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=2"

# 批量测试脚本（容器内执行）
for spider in spider1 spider2 spider3; do
  echo "=== Testing $spider ==="
  docker-compose exec crawl-worker bash -c \
    "cd news_scraper_project && scrapy crawl $spider -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=2" \
    2>&1 | grep -E "item_scraped|finish_reason|ERROR|Filtered out (no date)" | tail -5
  echo "---"
done
```

### Step 3.2: 验证标准

每个 spider 通过测试的条件：
- `item_scraped_count > 0`（或 `finish_reason: finished` 且 0 条是有原因的，如全部 too old）
- 日志中无 `ERROR`
- 无 `Filtered out (no date)` 出现

### Step 3.3: 输出结果矩阵

| Spider | 抓取条数 | 翻页停止 | 日期 | 图片 | 错误 | Status |
|--------|---------|---------|------|------|------|--------|
| spider_a | 2 | finished | PASS | PASS | 0 | PASS |
| spider_b | 0 | finished | PASS | FAIL | 0 | FAIL |

---

## Batch Test Only (不修复)

如果用户只想批量测试现有爬虫（不修复），跳过 Phase 2，直接执行 Phase 3。测试结果中标记出 FAIL 的爬虫，询问用户是否要进入修复流程。

## Rules

- Phase 1 必须只读，不改任何代码。改代码在 Phase 2。
- Phase 2 的每个 agent 修完一个 spider 必须立即自测（`CLOSESPIDER_ITEMCOUNT=2`），通过后才算完成。
- 批量操作前先告知用户影响范围（文件数、预计耗时），让用户确认。
- 如果批量测试中某个 spider 卡住超过 120 秒，超时标记为 TIMEOUT，继续下一个。
