# 爬虫排障指南 (Spider Debugging Skill)

本手册旨在提供一套标准化的流程，用于快速定位和修复新闻爬虫在列表页、详情页以及增量抓取逻辑中的常见问题。

## 1. 问题分类与定位

在开始改代码前，先通过日志或数据库确认故障类型：

| 故障现象 | 核心排查点 | 常用排查工具 |
| :--- | :--- | :--- |
| **不抓新文章** | 列表页日期解析、`should_process` 逻辑、Redis 过滤 | `scrapy crawl -a full_scan=True` |
| **无尽翻页 (Over-crawl)** | 列表页主区域选择器、侧边栏干扰、`break` 熔断机制 | 浏览器控制台检查主列表容器 |
| **详情页没正文/图片** | `fallback_content_selector`、详情页反爬(Playwright) | `curl_cffi` 验证 HTML 或浏览器 DOM |
| **内容加载 Pending** | 后端 Qdrant 阻塞、相似推荐接口耦合 | 后端 API 日志、网络面板 |

---

## 2. 诊断与修复步骤

### 第一步：列表页精准锁定 (防止 Over-crawl)
不要使用模糊的 `article` 标签，必须锁定主列表容器。

⛔ **禁止使用浏览器 DevTools 定位选择器！** 浏览器会执行 JavaScript 动态渲染 DOM，与爬虫实际拿到的 HTML 可能完全不同。必须使用以下"源码实测法"。

#### 源码实测法（标准流程）

1. **在 `crawl-worker` 容器内用 `curl_cffi` 下载真实 HTML**：
   ```bash
   # 下载列表页源码到容器临时文件
   docker-compose exec crawl-worker bash -c \
     "python3 -c \"from curl_cffi import requests; r = requests.get('<列表页URL>', impersonate='chrome110'); print(r.text)\" > /tmp/debug_list.html"
   
   # 将文件拷贝到本地分析
   docker-compose cp crawl-worker:/tmp/debug_list.html ./debug_list.html
   ```
   > 这样获得的 HTML 与爬虫 `CurlCffiMiddleware` 实际拿到的完全一致（相同的 TLS 指纹、请求头、IP）。

2. **分析 HTML 结构**：
   ```bash
   # 统计页面中所有 class 名出现次数，快速定位列表项容器
   grep -oE "class=\"[^\"]+\"" debug_list.html | sort | uniq -c | sort -nr | head -n 30
   
   # 查看目标容器的完整 HTML 片段
   grep -C 10 "目标类名" debug_list.html | head -n 50
   
   # 确认翻页链接格式
   grep -oE "href=\"[^\"]+page[^\"]*\"" debug_list.html
   ```

3. **验证翻页路径是否有效**：
   ```bash
   docker-compose exec crawl-worker bash -c \
     "python3 -c \"from curl_cffi import requests; r = requests.get('<翻页URL>', impersonate='chrome110'); print(r.status_code)\""
   ```
   如果返回 404，说明翻页 URL 格式已变更（如 `/page/2` → `?page=2`）。

4. **检查点**：
   - 确认选中的容器中**不包含**侧边栏的"热门文章"或"最新推荐"。
   - 确认日期文本的实际格式（是否带前缀如 `Written by ..., 29 April 2026`）。
5. **修复**：使用更长的组合类名，例如 `.main-content .post-item` 而非 `.post-item`。

### 第二步：详情页正文“手术刀”定位 (解决漏图)
如果发现漏掉顶部大图或正文不全：
1. **找到最大容器**：寻找一个能同时包裹 `<h1>`(标题)、`.featured-image`(图片) 和 `.entry-content`(正文) 的父级 `div`。
2. **避免“或”逻辑**：尽量使用一个唯一的、具体的选择器（如 `.main-content.s-post-contain`），避免使用逗号 `,` 导致提取引擎在多个碎片块中迷路。
3. **设置 `fallback_content_selector`**：将找到的唯一容器填入该字段。
4. **前端图片渲染 `[object Object]` 异常**：检查 `item['images']` 是否未清洗。爬虫底层引擎可能返回字典数组 `[{"url": "..."}]`，若直接入库，前端 React 会渲染乱码。必须将其转化为纯字符串数组 `["http..."]`。
5. **og:image 绝对优先**：不要仅把 `og:image` 当作“备胎”。智能引擎极易将侧边栏广告（如 3D Dinheiro 图标）提取为主图。必须显式提取 `og:image` 并强制插入到 `item['images']` 列表的**第一位**。

### 第三步：日期与翻页熔断 (防止扫全站)
如果日期抓不到，必须立刻停止。
1. **XPath 大小写敏感踩坑**：现代 JS 框架常将属性写为驼峰命名（如 `dateTime`）。Scrapy XPath 严格区分大小写，务必使用容错写法 `//@dateTime | //@datetime`，且调试时必须看 `curl` 源码而非浏览器 devtools。
2. **Dateparser ISO 冲突陷阱**：除非高度模糊的日期，否则**不要**盲目硬编码 `languages=['pt']` 或 `DATE_ORDER`。强制这些设置会破坏它原本对标准 ISO 时间（`YYYY-MM-DD`）的完美嗅探，导致标准时间全盘解析失败返回 `None`。
3. **Common Error: 'str' object has no attribute 'tzinfo'**:
    - 发生于向 `parse_to_utc` 传入了原始字符串而非 `datetime` 对象。
    - 解决: 先执行 `dateparser.parse(raw_str)`。
4. **解析检查**：确保列表页能提取出 `publish_time`。
5. **Panic Break**：在循环中判断，如果是一个有效的文章块但抓不到日期，直接 `break` 退出。
   ```python
   if is_valid_block and not publish_time:
       self.logger.error("STRICT STOP: No date found. Breaking to avoid backfill.")
       break
   ```

---

## 3. 注意点与禁忌

- **禁忌 1：过度依赖通配符**。尽量不要用 `//div` 这种大范围扫描，优先用 CSS 类名。
- **禁忌 2：忽视反爬。** 如果 `curl` 拿到的 HTML 和浏览器看到的不一样，必须开启 `use_curl_cffi = True` 或 `playwright: True`。
- **注意 3：性能监控。** 抓取图片会显著增加单条数据的大小，注意观察 API 响应耗时，必要时进行接口拆分。

## 4. 进阶：数据清理与环境同步

### 场景：修复代码后，发现它还是不抓取之前的文章？
**原因**：Scrapy 的去重机制（Redis）可能已经记录了这些 URL，认为它们已处理过。
**对策**：
1. **强制扫描**：运行爬虫时加上 `-a full_scan=True` 参数绕过去重逻辑。**这也会刷新/覆盖已入库文章的错误数据（如空时间或错误的封面图）**。
2. **清理 Redis**：如果需要彻底重来，进入 Redis 执行 `DEL <spider_name>:dupefilter`。

### 场景：抓取到的 Markdown 格式混乱或有杂质
**诊断**：在 `parse_detail` 中临时打印内容片段：`self.logger.debug(f"Markdown snippet: {item['content_markdown'][:200]}")`。
**排查**：
- 检查图片链接是否正确闭合。
- 如果出现了“点击查看全文”或“延伸阅读”，说明 `clutter_selectors` 需要补充屏蔽项。

### 场景：列表页 200 正常，详情页全部报 403 (Cloudflare 盾/防爬拦截)
**现象**：爬虫能成功提取列表页 URL，但在进入 `parse_detail` 时，Scrapy 日志疯狂输出 `Ignoring response <403 ...>`。
**核心分析方法**：
1. **对比测试**：很多高级防火墙（如 Cloudflare）对网站“门面”（列表页）放行，但对高频访问的“详情页”设置了极高的 JS Challenge（浏览器指纹校验）。
2. **命令验证**：在容器中用 Python 脚本和纯 `curl` 进行裸请求测试：
   ```bash
   docker-compose exec crawl-worker python -c "import requests; print(requests.get('详情页URL', headers={'User-Agent': 'Mozilla/5.0...'}).status_code)"
   ```
   如果返回也是 403，说明网站不仅封了默认 User-Agent，甚至可能拦截了非浏览器的底层 TLS 指纹（如 curl_cffi）。
**对策 (Playwright 破盾)**：
1. **开启无头浏览器**：如果 `use_curl_cffi = True` 依然失效，说明必须执行完整的 JS 挑战。在爬虫类中全局开启 `playwright = True`。
2. **强制移交引擎**：在 `parse_list` 中 yield 详情页请求时，手动注入 `playwright: True` 告诉中间件接管：
   ```python
   meta = {'publish_time_hint': publish_time}
   if getattr(self, 'playwright', False):
       meta['playwright'] = True
   yield scrapy.Request(url, callback=self.parse_detail, meta=meta)
   ```
3. **安全测试指令**：为了不污染线上数据，使用截断命令测试爬虫是否成功破盾：
   ```bash
   # 测试抓取，成功抓到 2 条后自动安全关闭爬虫
   docker-compose exec crawl-worker bash -c "cd news_scraper_project && scrapy crawl <spider_name> -a full_scan=True -s CLOSESPIDER_ITEMCOUNT=2"
   ```

## 5. 验证流程 (Standard Verification)
修改后，必须执行以下三步验证：
1. **采样测试**：用 `scrapy crawl <name> -o test.json` 跑几分钟，确认 `test.json` 里的图片和日期字段无误。
2. **翻页逻辑验证**：观察终端日志，确保翻页在达到日期边界（如 30 天前）时能主动停止，而不是无限请求 `page/100...`。
3. **前端最终确认**：在系统前端搜索最新抓取的文章，确认图片显示正常且详情页加载顺畅。
