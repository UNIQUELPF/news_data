# Skill: 新闻爬虫 V2 现代化改造指南 (News Spider V2 Modernization)

## 描述 (Description)
此技能用于将传统的旧版新闻爬虫重构为现代化的 `SmartSpider` V2 架构。它实现了从老式 Scrapy 爬虫向统一、智能、增量式框架的自动化迁移。可以参考代码：news_scraper_project/news_scraper/spiders/albania/albania.py

## 目标 (Goal)
确保所有新闻爬虫遵循标准化的 V2 架构，包括：正确的 UTC 时间处理、TLS 指纹模拟 (curl-cffi)、以及在保留原有验证选择器的基础上实现自动正文提取。

## 核心指令 (Instructions)
 
### 0. 批量重构工作流 (Batch Refactoring Workflow)
当需要优化一个目录下的多个爬虫时，**必须**遵循以下闭环流程：
1.  **逐个击破**: 严禁一次性修改多个文件。按逻辑顺序每次只重构**一个**爬虫。
2.  **自检输出**: 每完成一个爬虫的修改，必须对照“标准验证清单”在对话中输出该爬虫的达标情况。
3.  **实地演练**: 在进入下一个爬虫前，必须运行测试命令（如 `scrapy crawl <name> -o test.json` 或使用 debug 脚本）验证：
    - 是否抓到了有效的 `publish_time`？
    - `content_markdown` 是否包含图片且无杂质？
    - 翻页是否在截止日期处正确停止？
4.  **循环迭代**: 确认上一个爬虫完美达标后，再开始下一个。

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

### 4. 列表页逻辑 (增量抓取)
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
  - **⛔ 强制规则 - 日期熔断（最高优先级）**: 如果列表页某文章 `publish_time` 解析为 `None`，**该条目绝对不能让 `has_valid_item_in_window` 变为 `True`**。只有明确拿到日期且在窗口期内，才可触发翻页。目的是防止选择器失效时爬虫无限回溯整站。
  - **⛔ 强制规则 - 禁止硬编码页数上限**: 严禁使用 `if page < 20` 或 `if offset < 200` 等形式来控制翻页终止。翻页的唯一合法终止条件是：① `has_valid_item_in_window` 为 `False`，或 ② 页面上不存在"下一页"链接/按钮。如需全局兜底保护，只允许在 `custom_settings` 中使用 `CLOSESPIDER_ITEMCOUNT`。

### 5. 精确内容提取 (详情页)
- **"手术刀式"选择器策略**:
  - **避免模糊选择**: 不要单独使用 `article` 或 `div.content` 等通用标签。
  - **核心容器**: 锁定包裹标题、头图和正文的**最小唯一容器**（例如 `.main-content.s-post-contain`）。
- **⛔ 强制规则 - 禁止 XPath 全文扫描**: 传给 `auto_parse_item` 的所有 XPath 参数（`publish_time_xpath`、`title_xpath`）**必须限定在明确的容器范围内**，严禁使用以 `//tag` 开头可能命中侧边栏/页脚的写法：
  - ❌ 错误: `"//time/text()"` — 会扫描整个页面，极易命中侧边栏日期
  - ❌ 错误: `"//h1/text()"` — 推荐优先改用 `//meta[@property='og:title']/@content`
  - ✅ 正确: `"//div[contains(@class,'author-info')]//time/text()"` — 限定在作者区域
  - ✅ 例外: `//meta[@property='...']` 和 `//meta[@name='...']` 因 `<meta>` 在 `<head>` 中唯一，允许使用全局查询。。
- **图片完整性**:
  - **og:image 优先**: 自动提取引擎容易把侧边栏广告误认为头图。必须显式提取 `//meta[@property='og:image']/@content` 并将其**插入**到 `item['images']` 列表的最前面，确保其被视为首要封面图。
  - **防止前端 `[object Object]` 错误**: 确保 `item['images']` 最终是一个纯字符串列表（`['http...']`），如果留下了字典（`[{'url': '...'}]`），React 前端会渲染报错。
- **去噪清洗**:
  - 定义 `clutter_selectors` 来剔除“阅读更多”、“相关文章”和社交分享栏。

### 6. 标准验证清单 (Verification Checklist)
在完成一个爬虫并交付前，**必须**逐一核对并确认以下关键点：
1.  **列表容器**: 列表区域是否被精确锁定（例如 `main .news-list`），以排除侧边栏/页眉干扰？
2.  **日期选择器 (列表页)**: 列表页是否能成功提取日期？（这是实现翻页早停的关键）。
3.  **⛔ 日期熔断**: `publish_time` 为 `None` 时，是否确保 `has_valid_item_in_window` **不会** 被设为 `True`？日期解析失败即不触发翻页。
4.  **⛔ 无硬编码页数**: 代码中是否完全没有 `page < N` 或 `offset < N` 形式的上限？翻页终止必须由"Next 链接不存在"或 `has_valid_item_in_window == False` 驱动。
5.  **⛔ 无全文 XPath 扫描**: `publish_time_xpath` 和 `title_xpath` 中，是否所有 `//tag` 形式都已被限定在容器范围内（`//meta[...]` 除外）？
6.  **翻页可靠性**: 初始请求和所有分页请求是否都显式设置了 `dont_filter=True`？
7.  **增量窗口**: 实际运行日志是否显示爬虫在触达截止日期（Cutoff Date）后正确停止了翻页？
8.  **详情页头图**: `og:image` 是否被显式提取并插入到 `item['images']` 的首位？
9.  **前端兼容性**: 验证 `item['images']` 是否为纯字符串列表 `['http...']`，绝不能是字典列表。
10. **正文纯净度**: `content_markdown` 是否包含了主图？是否彻底去除了"相关阅读"、"分享到"等侧边栏/页脚杂质？
11. **语言检测**: 是否实现了自动语言识别（特别是在埃塞俄比亚等存在双语或多语种内容的地区）？
