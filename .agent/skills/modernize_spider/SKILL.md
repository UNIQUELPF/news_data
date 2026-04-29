# Skill: 新闻爬虫 V2 现代化改造指南 (News Spider V2 Modernization)

## 描述 (Description)
此技能用于将传统的旧版新闻爬虫重构为现代化的 `SmartSpider` V2 架构。它实现了从老式 Scrapy 爬虫向统一、智能、增量式框架的自动化迁移。

## 目标 (Goal)
确保所有新闻爬虫遵循标准化的 V2 架构，包括：正确的 UTC 时间处理、TLS 指纹模拟 (curl-cffi)、以及在保留原有验证选择器的基础上实现自动正文提取。

## 核心指令 (Instructions)

### 1. 类定义基础 (Class Foundation)
- **继承**: `news_scraper.spiders.smart_spider.SmartSpider`。
- **元数据**: 必须定义以下类属性：
  - `source_timezone`: (例如 'Europe/Sarajevo' 或 'Africa/Cairo')
  - `country_code`: 3位 ISO 国家代码。
  - `country`: 国家的中文名称。
  - `language`: 2位语言代码。
- **TLS 防护**: 始终设置 `use_curl_cffi = True`。

### 2. 请求处理 (Request Handling)
- **异步启动**: 使用 `async def start(self)` 代替 `start_urls`。
  ```python
  async def start(self):
      yield scrapy.Request(url, callback=self.parse, dont_filter=True)
  ```
- **自定义设置**: 除非站点有特殊需求，否则统一包含以下配置：
  ```python
  custom_settings = {
      "CONCURRENT_REQUESTS": 2, 
      "DOWNLOAD_DELAY": 1.0,
      "AUTOTHROTTLE_ENABLED": True,
  }
  ```

### 3. 高效调研规则 (Efficient Research Rules)
- **CURL 优先**: 始终先使用 `curl`（配合 `-H "User-Agent: ..."` 和 `-L`）检查 HTML 源码。**除非** 站点高度依赖 JS 渲染，否则不要浪费时间使用浏览器代理。
- **人工干预**: 如果简单的 Header 伪装后 `curl` 仍返回空或 403，请**停止**盲目尝试，直接向用户索要 HTML 源码或手动检查。禁止胡乱猜测。
- **保留成功经验**: 如果原爬虫的列表页选择器是准确的，**严禁随意更改**。只需在其基础上封装新的日期/熔断逻辑即可。

### 4. 标准验证清单 (7点检查法)
在完成一个爬虫前，必须验证以下 7 点：
1.  **列表容器**: 列表区域是否被精确锁定（例如 `.news-list`），以排除侧边栏干扰？
2.  **日期选择器 (列表页)**: 是否能成功提取所有列表项的日期？
3.  **日期格式 (DMY/MDY)**: `DATE_ORDER` 是否根据目标国家正确设置（例如欧洲通常为 'DMY'）？
4.  **熔断机制 (Panic Break)**: 当日期提取失败时，爬虫是否使用 `return`（而非 `break`）来终止整个翻页链？
5.  **翻页可靠性**: 初始请求和所有分页请求是否都设置了 `dont_filter=True`？
6.  **增量窗口**: 翻页是否在触达历史截止时间（Cutoff）后正确停止？
7.  **详情页选择器**: 文章正文提取是否精确，是否剔除了侧边栏和页脚杂质？

### 5. 列表页逻辑 (增量抓取)
- **请求可靠性**:
  - **初始请求和翻页请求必须设置 `dont_filter=True`**。这确保了即便索引 URL 在之前的任务中见过，爬虫依然会检查新内容。
- **日期提取策略**:
  - **机器码优先**: 如果存在 `<time>` 标签，优先提取 `datetime` 属性（ISO 格式）而非可见文本。
  - **XPath 大小写敏感警告**: 现代 JS 框架（React/Next.js）常将标准 HTML5 属性渲染为驼峰式（如 `dateTime`）。Scrapy 的 XPath 极其敏感，请查看 `curl` 源码并使用防御性 XPath 如 `//@dateTime | //@datetime`。
  - **列表页日期是强制要求**: 列表页日期提取是实现“早停”的关键。如果缺失，必须记录 `self.logger.warning`。
- **时间解析**:
  - **重要**: 如果原爬虫已有验证过的 XPath/CSS 选择器或自定义解析函数（如 `parse_az_date`），**请保留**。
  - **Dateparser ISO 冲突**: `dateparser` 有强大的自动检测功能。除非格式极度模糊，否则避免显式传递 `languages` 或 `DATE_ORDER`。强制设置这些参数会导致标准 ISO 字符串解析失败（例如 `2026-04-27` 在 `DMY` 设置下会报错）。
  - 使用 `self.parse_to_utc()` 将日期转为 UTC。
- **翻页控制**:
  - **Panic Break (严格准入)**: 如果列表页提取不到 `publish_time`，请使用 `break` 停止循环。这是防止在选择器失效时意外全站重爬的保护措施。

### 6. 精确内容提取 (详情页)
- **“手术刀式”选择器策略**:
  - **避免模糊选择**: 不要单独使用 `article` 或 `div.content` 等通用标签。
  - **核心容器**: 锁定包裹标题、头图和正文的**最小唯一容器**（例如 `.main-content.s-post-contain`）。
- **图片完整性**:
  - **og:image 优先**: 自动提取引擎容易把侧边栏广告误认为头图。必须显式提取 `//meta[@property='og:image']/@content` 并将其**插入**到 `item['images']` 列表的最前面，确保其被视为首要封面图。
  - **防止前端 `[object Object]` 错误**: 确保 `item['images']` 最终是一个纯字符串列表（`['http...']`）。如果留下了字典（`[{'url': '...'}]`），React 前端会渲染报错。
- **去噪清洗**:
  - 定义 `clutter_selectors` 来剔除“阅读更多”、“相关文章”和社交分享栏。

### 7. 验证
- **日志监控**: 验证翻页是否在触达日期窗口后正确停止。
- **内容检查**: 验证 `content_markdown` 是否包含主图，且无侧边栏杂质。
