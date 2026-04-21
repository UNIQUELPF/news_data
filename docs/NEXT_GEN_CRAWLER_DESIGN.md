# NNIS v2 — 新一代新闻情报系统架构设计

> 分支: `refactor-v2` | 最后更新: 2026-04-20

---

## 1. 设计目标

| 目标 | 说明 |
|:---|:---|
| **富文本保真** | 保留段落、图片、标题等排版结构，不再仅存纯文本 |
| **算法自适应** | 用 DOM 密度算法自动定位正文，减少对 CSS 选择器的依赖 |
| **向量检索独立** | 向量数据迁入 **Qdrant**，PostgreSQL 仅存原始/清洗后的结构化数据 |
| **AI 原生** | 以 Markdown 为主存储格式，天然适配 RAG / LLM 分析 |
| **前端兼容** | 前端页面结构保持不变，仅调整 API 返回字段 |

---

## 2. 整体架构

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Scrapy      │────▶│  Content Engine   │────▶│  PostgreSQL │
│  Spiders     │     │  (trafilatura +   │     │  (原始+清洗) │
│  (采集层)    │     │   BS4 + markdown) │     └──────┬──────┘
└─────────────┘     └──────────────────┘            │
                                                     ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Celery      │────▶│  LLM Pipeline    │────▶│  Qdrant     │
│  Workers     │     │  (翻译+元数据+   │     │  (向量检索)  │
│  (调度层)    │     │   Embedding)     │     └─────────────┘
└─────────────┘     └──────────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │  FastAPI          │
                    │  (API 层)         │◀──── Next.js Frontend
                    └──────────────────┘
```

---

## 3. 数据存储设计

### 3.1 PostgreSQL — 结构化数据 (原始 + 清洗)

**核心原则**: PostgreSQL 负责所有结构化元数据、原始内容和清洗后的富文本内容。不再存储向量。

#### 表: `sources` (数据源)

```sql
CREATE TABLE sources (
    id          BIGSERIAL PRIMARY KEY,
    spider_name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    domain      TEXT,
    country_code TEXT,
    country     TEXT,
    language    TEXT,              -- 该源的主要语言
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

> **变更**: 移除 `organization`, `legacy_table` 字段。新系统不再维护遗留表。

#### 表: `articles` (文章主表)

```sql
CREATE TABLE articles (
    id               BIGSERIAL PRIMARY KEY,
    source_id        BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_url       TEXT NOT NULL UNIQUE,

    -- 原始内容 (爬虫直接写入)
    title_original   TEXT,
    content_raw_html TEXT,           -- NEW: 爬虫获取的原始正文 HTML 片段
    content_cleaned  TEXT,           -- NEW: 清洗后的标准化 HTML (仅 p/img/h1-h6/ul/ol/li/a/strong/em)
    content_markdown TEXT,           -- NEW: 转换后的 Markdown (用于 AI/RAG)
    content_plain    TEXT,           -- NEW: 纯文本 (用于全文搜索, 兼容现有前端)

    -- 媒体资产
    images           JSONB,          -- NEW: [{url, alt, caption, width, height}]
    
    -- 元数据
    publish_time     TIMESTAMP,
    author           TEXT,
    language         TEXT,
    section          TEXT,
    country_code     TEXT,
    country          TEXT,
    company          TEXT,
    province         TEXT,
    city             TEXT,
    category         TEXT,
    content_hash     TEXT,

    -- 处理状态
    extraction_status  TEXT NOT NULL DEFAULT 'pending',  -- NEW: pending/completed/failed
    translation_status TEXT NOT NULL DEFAULT 'pending',
    embedding_status   TEXT NOT NULL DEFAULT 'pending',

    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_articles_source_id ON articles(source_id);
CREATE INDEX idx_articles_publish_time ON articles(publish_time DESC);
CREATE INDEX idx_articles_country_code ON articles(country_code);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_articles_company ON articles(company);
CREATE INDEX idx_articles_extraction_status ON articles(extraction_status);
CREATE INDEX idx_articles_translation_status ON articles(translation_status);
CREATE INDEX idx_articles_embedding_status ON articles(embedding_status);
-- 全文搜索索引
CREATE INDEX idx_articles_content_plain_trgm ON articles USING gin (content_plain gin_trgm_ops);
CREATE INDEX idx_articles_title_trgm ON articles USING gin (title_original gin_trgm_ops);
```

> **核心变更**:
> - `content_original` 拆分为 4 个字段: `content_raw_html` / `content_cleaned` / `content_markdown` / `content_plain`
> - 新增 `images` JSONB 字段存储提取的图片资产列表
> - 新增 `extraction_status` 跟踪内容提取状态
> - 移除 `organization`, `legacy_table` 字段

#### 表: `article_translations` (翻译)

```sql
CREATE TABLE article_translations (
    id                 BIGSERIAL PRIMARY KEY,
    article_id         BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    target_language    TEXT NOT NULL,
    title_translated   TEXT,
    summary_translated TEXT,
    content_translated TEXT,          -- 翻译后的 Markdown 格式
    translator         TEXT,
    status             TEXT NOT NULL DEFAULT 'pending',
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, target_language)
);
```

#### 表: `crawl_jobs` / `pipeline_task_runs` / `pipeline_periodic_tasks`

> 保持不变，继续用于任务调度和监控。

### 3.2 Qdrant — 向量检索

**核心原则**: 所有向量数据从 PostgreSQL 迁出，统一存入 Qdrant。

#### Collection: `article_chunks`

```json
{
  "collection_name": "article_chunks",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "article_id": "integer",
    "chunk_index": "integer",
    "chunk_text": "text",
    "title": "text",
    "country_code": "keyword",
    "category": "keyword",
    "company": "keyword",
    "publish_time": "datetime",
    "language": "keyword"
  }
}
```

> **优势对比现有方案**:
> - 现有: 向量存 PostgreSQL JSONB → 余弦相似度在 Python 层手动计算，性能差
> - 新方案: Qdrant 原生 ANN 索引 → 毫秒级向量检索，支持 payload 过滤

### 3.3 删除的表

以下现有表在新系统中**不再需要**:

| 现有表 | 原因 |
|:---|:---|
| `article_chunks` (PG) | chunk 文本和向量统一存入 Qdrant payload |
| `article_embeddings` (PG) | 向量数据迁入 Qdrant |
| 所有 legacy spider 表 | 不再维护遗留表 |

### 3.4 数据库迁移机制 (Database Migrations)

**现有痛点**：目前在爬虫的 `PostgresPipeline` 中大量使用 `_ensure_unified_tables()` 和 `CREATE TABLE IF NOT EXISTS`。这种方式有两个严重缺陷：
1. **性能损耗**：每次爬虫入库都去触发 DDL (数据定义语言) 检查，浪费数据库连接资源和执行时间。
2. **缺乏版本控制**：表结构变动无法追踪，多人协作时容易出现字段不同步的问题。

**新系统方案：引入专门的 Migration 管理**
新架构中，我们**彻底废除**代码运行时的 `ensure_table` 操作。采用专门的 Migration 机制进行统一部署和结构控制：

1. **统一的初始化脚本 / 迁移工具**：
   - 我们已经确定采用 **Alembic** 作为官方数据库迁移工具。它是 Python 生态下最知名、最正统的数据库迁移工具，完美支持原生的 SQL 迁移，也有极佳的扩展性。
   - 所有的表结构创建、修改脚本（如 `001_init_v2_schema.py`）都将放置在根目录的 `alembic/versions/` 目录下统一管理。
2. **执行时机**：
   - 表结构的初始化或变更**只在系统部署 / 更新时执行一次**。
   - 可以通过 Docker Compose 启动时执行一次 Migration 容器，或者在 API 的 `lifespan` 启动事件中检测并执行。
3. **爬虫端剥离 DDL**：
   - 爬虫 Pipeline 中**只保留 DML (INSERT/UPDATE/SELECT)**。爬虫默认表已经存在，如果表不存在直接抛错（Fail Fast），这样可以倒逼规范化部署流程。

---

## 4. 内容提取引擎 (Content Extraction Engine)

### 4.1 处理流程

```
原始 HTML ──▶ 噪音清除 ──▶ 正文定位 ──▶ 资产修复 ──▶ 格式分发
                │              │             │            │
            去 script/      trafilatura    补全 img      → content_cleaned (HTML)
            style/nav/      算法优先       绝对路径      → content_markdown (MD)
            form/aside      CSS回退        处理懒加载    → content_plain (Text)
                                                         → images (JSON)
```

### 4.2 核心实现 (`pipeline/content_engine.py`)

```python
import trafilatura
from markdownify import markdownify as md
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]
ALLOWED_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "img", "a",
                "ul", "ol", "li", "strong", "em", "b", "i", "br", "blockquote", "figure", "figcaption"}

class ContentEngine:
    @staticmethod
    def process(raw_html: str, base_url: str, fallback_selector: str | None = None) -> dict:
        """
        返回:
        {
            "content_raw_html": str,      # 原始正文 HTML 片段
            "content_cleaned": str,       # 标准化 HTML
            "content_markdown": str,      # Markdown
            "content_plain": str,         # 纯文本
            "images": list[dict],         # [{url, alt}]
        }
        """
        # 1. 算法定位正文
        extracted_html = trafilatura.extract(
            raw_html, output_format="html",
            include_images=True, include_links=True
        )

        # 2. 回退: 用 CSS 选择器
        if not extracted_html and fallback_selector:
            soup = BeautifulSoup(raw_html, "lxml")
            node = soup.select_one(fallback_selector)
            extracted_html = str(node) if node else None

        if not extracted_html:
            return {"content_raw_html": "", "content_cleaned": "", 
                    "content_markdown": "", "content_plain": "", "images": []}

        raw_html_fragment = extracted_html

        # 3. 清洗 + 资产修复
        soup = BeautifulSoup(extracted_html, "lxml")
        
        # 删除噪音标签
        for tag in soup(NOISE_TAGS):
            tag.decompose()

        # 修复图片路径 (含懒加载)
        images = []
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("data-original") or img.get("src")
            if src:
                abs_url = urljoin(base_url, src)
                img["src"] = abs_url
                images.append({"url": abs_url, "alt": img.get("alt", "")})
            img.attrs = {k: v for k, v in img.attrs.items() if k in ("src", "alt")}

        # 修复链接
        for a in soup.find_all("a"):
            href = a.get("href")
            if href:
                a["href"] = urljoin(base_url, href)

        # 移除非白名单标签 (保留内容, 去掉标签本身)
        for tag in soup.find_all(True):
            if tag.name not in ALLOWED_TAGS:
                tag.unwrap()

        content_cleaned = str(soup)
        content_markdown = md(content_cleaned, heading_style="ATX").strip()
        content_plain = soup.get_text("\n", strip=True)

        return {
            "content_raw_html": raw_html_fragment,
            "content_cleaned": content_cleaned,
            "content_markdown": content_markdown,
            "content_plain": content_plain,
            "images": images,
        }
```

### 4.3 爬虫端调用示例

```python
# 新版 Spider 基类
class SmartSpider(scrapy.Spider):
    fallback_content_selector = None  # 子类可覆盖, 如 "div.article-body"

    def extract_content(self, response) -> dict:
        from pipeline.content_engine import ContentEngine
        return ContentEngine.process(
            raw_html=response.text,
            base_url=response.url,
            fallback_selector=self.fallback_content_selector,
        )
```

---

## 5. 增量爬取与去重策略优化

为了解决历史架构中“漏抓”和“数据库查询压力”的问题，新架构将引入**滑动时间窗口**与**分布式去重**组合的增量方案。

### 5.1 滑动时间窗口 (取代绝对时间截断)
- **痛点**: 历史版本以数据库中 `MAX(publish_time)` 为硬性 `cutoff_date`，导致乱序发布或补录的新闻因发布时间较旧被直接跳过，造成永久漏抓。
- **新方案**: 
  1. **日常增量抓取**：引入 7 天安全缓冲期。设定 `cutoff_date = MAX(publish_time) - timedelta(days=7)`。要求爬虫回推最近 7 天的列表防止漏抓，重复判定交由 Redis。
  2. **首次运行 (冷启动)**：当数据库中没有该爬虫的数据时，`MAX(publish_time)` 为空，自动回退到全局配置项 `settings.get('DEFAULT_START_DATE')`（例如：`2024-01-01`），自动执行大跨度的全量爬取。
  3. **人为干预与传参**：支持通过 Scrapy 命令参数动态调整窗口。
     - 强制全量：`scrapy crawl spider_name -a full_scan=1`（直接使用 `settings.get('DEFAULT_START_DATE')`）。
     - 自定义回溯：`scrapy crawl spider_name -a window_days=30`（覆盖默认的 7 天，往回推 30 天进行修复性补抓）。

### 5.2 Redis 去重 (取代 PG LIMIT 5000)
- **痛点**: 历史版本每次启动都要查询 Postgres 获取最新的 5000 条 URL 放入内存去重，对 DB 压力大，且高频网站容易超量导致重复抓取。
- **新方案**: 统一使用基于 Redis 的集中式指纹过滤（如 `scrapy-redis` 的 `RFPDupeFilter` 或 Bloom Filter）。爬虫无需向 PostgreSQL 请求近期 URL 列表，通过 Redis 进行 O(1) 的绝对去重，不占用应用内存且支持千万级数据。

### 5.3 列表页提前熔断 (Early Stopping)
- **新方案**: 在解析新闻列表页时，加入页级熔断器。如果发现**当前页中所有的文章发布时间均小于 `cutoff_date`**，将立即终止“下一页 (Next Page)”的翻页请求，避免无效的深层抓取，节省代理流量和网络请求。

### 5.4 全链路时区规范 (Timezone Management)
处理多国新闻源时，时区错乱会导致增量逻辑失效或前端展示混乱。新架构必须强制执行**“入库转 UTC，出库交前端”**的国际化标准方案：
1. **爬虫解析层 (Source -> UTC)**：
   - 目标网站的时间都是 Local Time。我们在子爬虫或爬虫配置中硬编码该国的时区（如 `timezone = 'Asia/Bahrain'`）。
   - 在解析时，利用 `dateparser` 将其识别为对应时区的时间，并立刻转换为 **UTC 时间**。
2. **存储层 (PostgreSQL 统一 UTC)**：
   - 数据库中的 `publish_time` 统一变更为 `TIMESTAMP WITH TIME ZONE`（简称 `TIMESTAMPTZ`）类型，或严格以 naive UTC 的形式存入普通的 `TIMESTAMP`。无论 Docker 容器所在的时区是什么，数据库内部始终记录的是绝对时间点。
3. **API与后端逻辑层 (UTC in, UTC out)**：
   - Python 代码里的 `cutoff_date` 对比、Celery 定时任务触发、数据库查询，全部统一使用 UTC 时间。API 接口在序列化 `publish_time` 时，强制输出带有 `Z` 结尾的标准 ISO-8601 格式（如 `2026-04-20T10:00:00Z`）。
4. **前端展示层 (Browser Local)**：
   - 前端接收到 API 的 UTC 字符串后，不做任何硬编码加减。直接交给浏览器的原生 `Date` 对象或类似 `dayjs` 库，它们会自动根据**当前用户的系统时区**（如你在国内就是北京时间 `UTC+8`）进行渲染。

---

## 6. 处理管线 (Pipeline) 重设计

### 6.1 新管线流程

```
Crawl ──▶ Extract ──▶ Translate ──▶ Embed ──▶ Index
  │          │            │            │          │
  │          │            │            │          └─ 写入 Qdrant
  │          │            │            └─ 生成向量
  │          │            └─ LLM 翻译 + 元数据提取
  │          └─ ContentEngine 提取富文本
  └─ Scrapy 抓取原始 HTML
```

### 6.2 各阶段任务与命名优化

为了在 Celery Flower 或监控大盘中提供更直观的视图，彻底抛弃旧版基于 Python 文件路径的冗长命名，采用“领域驱动（Domain-Driven）”的 `domain.resource.action` 命名规范：

| 阶段 | 旧任务名示例 | 新任务名 (Celery Task Name) | 核心功能 |
|:---|:---|:---|:---|
| **调度** | `pipeline.tasks.crawl.run_all...` | **`news.crawl.schedule_all`** | 触发所有启用的爬虫任务 |
| **抓取** | `pipeline.tasks.crawl.run_spider` | **`news.crawl.spider.run`** | 爬取单站，存入 `content_raw_html` |
| **提取** | *(无)* | **`news.pipeline.content.extract`** | `ContentEngine` 洗稿，生成 4 种格式 |
| **翻译** | `pipeline.tasks.translate...` | **`news.pipeline.content.translate`** | 大模型本土化与结构化元数据提取 |
| **向量** | `pipeline.tasks.embed...` | **`news.pipeline.vector.embed`** | Markdown 拆分、向量化并入库 Qdrant |

### 6.3 Scrapy Pipeline 变更

现有 `PostgresPipeline.process_item()` 修改:
- 爬虫不再调用 `p.get_text()`, 而是存储原始 HTML
- `ContentEngine.process()` 在 Scrapy Pipeline 中直接调用
- 一次性写入 `content_raw_html`, `content_cleaned`, `content_markdown`, `content_plain`, `images`

### 6.4 Embed 任务变更 (Qdrant)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

def embed_and_index(article_id: int, chunks: list[str], metadata: dict):
    client = QdrantClient(url=QDRANT_URL)
    vectors, model_name = embed_texts(chunks)
    
    points = [
        PointStruct(
            id=f"{article_id}_{i}",
            vector=vec,
            payload={
                "article_id": article_id,
                "chunk_index": i,
                "chunk_text": chunk,
                **metadata,  # country_code, category, publish_time, etc.
            }
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name="article_chunks", points=points)
```

---

## 7. API 层变更

### 7.1 搜索接口改造 (`/api/v1/articles`)

| 搜索模式 | 现有实现 | 新实现 |
|:---|:---|:---|
| **keyword** | PostgreSQL ILIKE | PostgreSQL `pg_trgm` + `content_plain` |
| **semantic** | PG 取向量 → Python 算余弦 | **Qdrant ANN 查询** (毫秒级) |
| **hybrid** | Python 手动融合 | Qdrant scroll + PG keyword → RRF 融合 |

### 7.2 文章详情接口 (`/api/v1/articles/{id}`)

返回字段变更:

```json
{
  "article": {
    "content_original": "...",           // 改名自 content_plain, 兼容前端
    "content_html": "...",               // NEW: content_cleaned, 前端可直接渲染
    "content_markdown": "...",           // NEW: AI 分析用
    "images": [{"url": "...", "alt": "..."}]  // NEW
  }
}
```

> **前端兼容策略**: 前端现有字段 `content_original` 映射到 `content_plain`, 保持 API 向后兼容。

### 7.3 相似文章接口

```
现有: PG article_embeddings → Python cosine_similarity  (O(n) 扫描)
新增: Qdrant scroll → 原生 ANN 检索 (O(log n))
```

---

## 8. Docker Compose 变更

新增 Qdrant 服务:

```yaml
  qdrant:
    image: qdrant/qdrant:v1.13
    container_name: news_qdrant
    ports:
      - "6333:6333"    # REST API
      - "6334:6334"    # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334

volumes:
  postgres_data:
  qdrant_data:          # NEW
```

API 和 Worker 容器新增环境变量:
```yaml
QDRANT_URL: http://qdrant:6333
```

---

## 9. 依赖变更 (`requirements.txt`)

```diff
 scrapy
 scrapy-playwright
-scrapy-redis
 celery[redis]
 fastapi
 uvicorn[standard]
 psycopg2-binary
 httpx
 beautifulsoup4
-feedparser
 curl_cffi
 dateparser==1.2.0
 playwright-stealth==1.0.6
-jdatetime
-pypdf
 croniter
+trafilatura           # 正文自动提取
+markdownify           # HTML → Markdown
+lxml                  # 高性能 HTML 解析
+qdrant-client         # Qdrant 向量数据库客户端
```

---

## 10. 高可用与异常容错机制

为保证生产环境下的健壮性，系统针对各种边界情况设计以下容错与监控流程：

### 10.1 本土新闻免译路由 (Translation Bypass)
- 并非所有文章都需要全文翻译。在 Celery 的 `translate` 节点，将引入语言路由判断。
- 当爬虫源语言为 `zh-CN` 或文章正文识别为中文时，跳过 LLM 的翻译 Prompt，直接调用轻量级的 `提取 Prompt`（仅抽取涉事公司、省份、城市、分类等元数据）。这能大幅节省大模型 Token 开销并提高流转速度。

### 10.2 爬虫静默断流监控 (Silent Failure Alerting)
- 为了防范目标网站隐性改版（如防爬虫策略升级或 DOM 异动）导致爬虫空转（不报错但也抓不到数据），利用 `articles` 表的记录时间作为探针。
- 设计后台巡检任务：若发现某数据源连续 3 天以上未能入库新文章，将在系统控制台标红报警，提示运维人员介入排查。

### 10.3 状态机流转与失败重试 (Dead Letter Retry)
- 任何外部依赖调用（如 OpenAI 翻译、Qdrant 向量化）都可能因网络抖动失败。`articles` 表中的状态字段 (`extraction_status`, `translation_status`, `embedding_status`) 构成了完整的数据流转状态机。
- 设立夜间轮询任务：自动扫描状态为 `failed` 且出错时间超过 1 小时的数据，将其自动重新投递到 Celery 队列进行二次重试。超过 3 次失败的数据标记为 `dead`，等待人工查验。

---

## 11. Celery 任务调度与并发优化

针对历史代码中 `pipeline/tasks/` 下的定时调度和并发分发机制，新架构将进行以下三点核心演进，以解决高并发下的资源瓶颈和调度阻塞问题：

### 11.1 解除 `crawl.py` 批量分发中的“木桶效应”
- **痛点**：历史实现使用 `chain(group(batch1), group(batch2))` 强制分批串行调度爬虫。如果某一批次中有一个爬虫因目标网站无响应而卡死（Straggler），后续所有批次的几百个爬虫将被完全阻塞。
- **新方案**：彻底废除 `chain` 批次处理。将所有待执行的爬虫任务作为完全独立的原子任务，一次性全部平行投入 Celery 队列（仅执行 `delay()`）。并发峰值管控交由 Celery Worker 的全局并发数配置（如 `celery worker -c 5`）或任务级限流配置自然接管。

### 11.2 替换自定义轮询器，拥抱原生 Celery Beat
- **痛点**：历史实现 `orchestrate.py` 中手工写了一个“查询数据库并依赖 `croniter` 算时间”的轮询器，属于低维度的“重复造轮子”，极易发生时间漂移，且不支持分布式高可用部署。
- **新方案**：废除自定义的 `dispatch_periodic_tasks`。引入成熟的工业标准 `celery-sqlalchemy-scheduler` 或原生的 `Redbeat`。直接将数据库中的 cron 规则注册为真正的 Celery Beat 任务，由 Celery 原生进行毫秒级的精准、防重复调度。

### 11.3 废除 `subprocess` 子进程调用，节约内存暴增开销
- **痛点**：历史实现在 Celery Worker 中通过 `subprocess.run(["scrapy", "crawl", name])` 调用系统命令拉起爬虫。每次启动都要新建一个完整的 Python 解释器环境，开销巨大，20 个并发极易导致服务器 OOM 崩溃。
- **新方案**：改为在 Celery 同一进程内，通过 Scrapy 原生 API (`CrawlerRunner` 或 `CrawlerProcess`) 配合 Twisted Reactor 执行任务。彻底消灭子进程冷启动的极高 CPU/内存开销，并实现数据库连接池等内存资源的进程级共享。

---

## 12. 迁移路线图

### Phase 1: 基础设施与核心工具 (Infrastructure & Core)
- [x] 配置 Alembic 与 `requirements.txt` (已完成)
- [x] 执行 `alembic upgrade head` 生成 PostgreSQL V2 表结构
- [x] Docker Compose 加入 Qdrant 容器并启动
- [x] 开发 `pipeline/content_engine.py` (基于 Trafilatura 的智能提取与清洗)

### Phase 2: 爬虫基座与管道重构 (Spider Base & Pipeline)
- [x] 编写 `SmartSpider` 基类：实现 7天滑动窗口、冷启动判断、命令行参数覆写、以及时区转换 (转为 UTC)。
- [x] 改造 `PostgresPipeline`：剥离原本的建表 DDL 逻辑，接入 `ContentEngine`，并实现多格式内容并行入库。
- [x] 改造并验证 `bahrain_cbb` 爬虫，确保入库的 Markdown 格式完美且无漏抓。

### Phase 3: 任务调度与异常流转优化 (Celery Refactoring)
- [x] 优化 `crawl.py`：解绑 `chain` 批次限制，提升并发吞吐量。 (已完成)
- [x] 优化 `translate.py`：加入本地新闻免翻译路由。 (已完成: BYPASS_ORGANIZATIONS)
- [x] 编写失败重试脚本 (轮询 `status='failed'` 的数据投递)。 (已完成: retry_failed_pipeline_tasks)

### Phase 4: 向量数据库接入 (Qdrant Integration)
- [x] 编写 Qdrant Collection 初始化脚本 (建库与创建索引)。 (已完成: qdrant_utils.py)
- [x] 改造 `embed.py`：使其读取 Markdown 格式切片，并将向量与 payload 写入 Qdrant，同时更新 PG 中的 `embedding_status`。 (已完成)
- [x] 编写历史数据清洗与灌库脚本。 (已完成: embed_backfill_articles)

### Phase 5: API 升级与前端适配 (API & Frontend)
- [x] 改造 FastAPI 搜索接口：语义搜索完全走 Qdrant，并实现 PG 与 Qdrant 的混合搜索 (RRF)。 (已完成)
- [x] 改造详情页接口：返回带 `Z` 尾缀的严格 UTC 时间，暴露 `content_cleaned` 与 `images`。 (已完成)
- [x] 前端字段映射，确保 UI 展示与老版本无缝衔接。 (已完成: ArticleOverview 升级与 CSS 注入)

### Phase 6: 遗留系统清理 (Cleanup)
- [x] 删除 PostgreSQL 中的 `article_chunks` 和 `article_embeddings` 表。 (已完成)
- [x] 删除原有的遗留表和手动建表脚本。 (已完成)
- [x] 结项与文档归档。 (已完成)

---
**项目状态：100% 交付。系统已进入全量生产运行状态。**

---

## 13. 未来演进：任务管理高级特性 (Future Roadmap: Advanced Task Management)

基于目前已成功接入的 `celery-sqlalchemy-scheduler` 动态调度架构，计划在下一个迭代周期针对任务的控制面与大盘监控体验进行深度优化，核心目标是提升管理员对异步流水线的**绝对控制力**与**可观测性**。

### 13.1 增加“手动立刻触发一次 (Trigger Now)”功能
*   **背景**：当前只能修改 Cron 规则等待其自然触发，或仅能通过全局开关禁用，缺乏即时测试与临时调度的能力。
*   **规划**：
    *   **后端 API**：新增单次触发接口，读取目标定时任务的 `task_path` 与参数，绕过 Beat 调度器，直接调用 Celery 的 `.delay()` 将任务推入 Worker 队列。
    *   **前端 UI**：在 `TaskSchedulesPanel` 的定时任务卡片中新增 `[ ⚡ 立刻执行一次 ]` 按钮，实现不干扰原有 Cron 节奏的单发执行。

### 13.2 增加“强杀正在运行任务 (Force Terminate)”机制
*   **背景**：`is_enabled` 开关仅能阻断未来调度，若 Worker 已开始处理某一长耗时任务（如卡死的巨型爬虫），前端目前无能为力。
*   **规划**：
    *   **后端 API**：暴露任务强制撤销接口 `POST /api/v1/pipeline/tasks/{task_id}/revoke`，底层调用 `celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')`。
    *   **前端 UI**：在 `TaskHistoryList` 日志面板中，识别处于 `Processing` 状态的任务，渲染高危操作按钮 `[ 🛑 强制终止进程 ]`，点击后立即斩断后台 Worker 执行流。

### 13.3 暴露高阶调度指标 (总运行次数与执行时间预览)
*   **背景**：目前调度面板仅展现了上次分发时间（Last Dispatched），缺乏系统全局视图。
*   **规划**：
    *   **后端 API**：在 `GET /api/v1/pipeline/schedules` 中暴露 `celery_periodic_task` 原生维护的 `total_run_count` (累计触发次数)。
    *   **前端 UI**：
        1. 渲染显示每个定时任务的历史累计触发总数。
        2. 在用户编辑 Cron 表达式时（如输入 `0 2 * * *`），引入自然语言预览与“下一次预计执行时间”（Next Execution Time）计算，防范手误引发的调度雪崩。

### 13.4 任务监控视图优先级重构
*   **背景**：`TaskPanel` 的执行日志混杂了历史记录与当前运行状态，导致并发期难以抓取核心信息。
*   **规划**：
    *   **前端 UI**：重构大盘结构，将“正在运行的任务 (Active Tasks)”置顶为独立区域并高亮，配合动态 Loading 与实时耗时计时器（Time Elapsed），让系统算力分布情况一目了然。
