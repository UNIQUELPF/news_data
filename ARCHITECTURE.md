# 全球政治经济数据库架构方案

## 目标

围绕“多语种资讯采集、翻译、语义检索、Web 展示”建设一套可持续扩展的数据平台，支持：

- 多国家、多站点新闻与政策信息采集
- 原文、译文、摘要的统一管理
- 基于国家、组织、企业、时间、分类的结构化筛选
- 基于关键词与向量召回的混合检索
- 后续专题聚合、相似文章推荐、风险监控

## 第一阶段技术栈

- 爬虫：`Scrapy + Playwright`
- 调度：`Celery + Redis`
- 主数据库：`PostgreSQL`
- 向量检索：`pgvector`
- API：`FastAPI`
- Web：`Next.js`
- 反向代理：`Nginx`
- 部署：`Docker Compose`

第一阶段不引入 Kubernetes、Kafka、独立搜索引擎，优先保证交付速度和系统可维护性。

## 服务拆分

### 1. crawl-worker

职责：

- 执行站点采集任务
- 解析标题、正文、发布时间、作者、栏目
- 将原始文章写入统一主表

说明：

- 现阶段继续复用现有 `Scrapy + Playwright` 代码
- 统一通过 `Celery + crawl-worker` 执行爬虫，不再保留独立 `crawler` 服务
- 为降低改造风险，当前仍保留 legacy table 双写
- spider 增量读取已统一迁移到 `news_scraper.utils.get_incremental_state()`

### 2. scheduler

职责：

- 按优先级调度 spider
- 按站点维度重试与限流
- 驱动翻译、embedding、索引更新链路

建议：

- 使用 `Celery Beat + Celery Worker`

### 3. translation-worker

职责：

- 标题翻译
- 中文摘要生成
- 重点文章正文翻译

策略：

- 标题全量翻译
- 摘要全量生成
- 正文按优先级和命中规则翻译，避免成本失控

### 4. embedding-worker

职责：

- 对标题、摘要、正文分块生成向量
- 写入 `pgvector`

策略：

- 采用 chunk 级别向量，而不是整篇文章单向量
- 向量写入前先完成文本清洗与语言统一

### 5. search-api

职责：

- 提供文章列表查询
- 提供关键词搜索、语义搜索、混合搜索
- 提供国家、组织、企业、时间、分类筛选

推荐框架：

- `FastAPI`

### 6. web-app

职责：

- 检索页
- 详情页
- 标签筛选与高亮展示

推荐框架：

- `Next.js`

## 数据流

1. `Scrapy spider` 采集原文
2. 入库到 `articles`
3. 创建翻译任务
4. 译文写入 `article_translations`
5. 创建 embedding 任务
6. 分块写入 `article_chunks`
7. 向量写入 `article_embeddings`
8. API 提供结构化筛选与混合检索
9. Web 展示搜索结果与详情页

## Spider 增量策略

当前 spider 侧的增量逻辑已经统一为一条路径：

1. 优先从统一表 `sources + articles` 读取该 `spider_name` 的最新 `publish_time`
2. 同时读取最近一批 `source_url` 作为去重集合
3. 如果统一表还没有该 spider 数据，再回退到 legacy table
4. `full_scan=true` 时仍按各 spider 原有语义走全量/大范围回溯

这样做的原因是：

- 避免继续把增量状态分散在“每 spider 一张表”的旧模式里
- 在不打断现有采集的前提下完成渐进迁移
- 允许统一表先承接新链路，同时 legacy table 继续作为兜底

当前仓库已增加两层回归保护：

- 静态测试：禁止 spider 中重新出现 `SELECT MAX(publish_time) FROM`
- 初始化级测试：验证代表性 spider 的 `_init_db*` / `get_latest_db_date()` 会调用 `get_incremental_state()`

## 数据模型

### 核心表

- `sources`
- `articles`
- `article_translations`
- `article_chunks`
- `crawl_jobs`
- `crawl_errors`

### `sources`

用于统一维护来源站点信息，而不是继续使用“每个 spider 一张表”的模式。

关键字段：

- `spider_name`
- `display_name`
- `domain`
- `country`
- `organization`
- `legacy_table`

### `articles`

统一保存所有抓取到的原文文章。

关键字段：

- `source_id`
- `source_url`
- `title_original`
- `content_original`
- `publish_time`
- `author`
- `language`
- `section`
- `country`
- `organization`
- `category`
- `legacy_table`
- `content_hash`
- `translation_status`
- `embedding_status`

### `article_translations`

保存中文译文、摘要及后续多语言结果。

关键字段：

- `article_id`
- `target_language`
- `title_translated`
- `summary_translated`
- `content_translated`
- `status`

### `article_chunks`

用于长文分块、摘要检索和后续向量化。

关键字段：

- `article_id`
- `chunk_index`
- `content_text`
- `token_count`
- `embedding_status`

## 搜索策略

第一阶段采用混合检索：

- 关键词检索：`PostgreSQL Full Text Search`
- 语义检索：`pgvector`
- 排序：关键词分数 + 向量相似度 + 时间衰减 + 来源权重

该方案优先满足你这个场景最常见的需求：

- 输入关键词
- 结合国家、组织、企业、时间进行过滤
- 返回标题、摘要、更新时间和标签

## 部署建议

### 阶段一：单机 Compose

服务：

- `scheduler`
- `crawl-worker`
- `translation-worker`
- `embedding-worker`
- `postgres`
- `redis`
- `api`
- `web`
- `nginx`

适合当前项目的验证和首版上线。

### 阶段二：分离扩容

- `crawler-worker` 横向扩容
- `translation-worker` 单独扩容
- `embedding-worker` 单独扩容
- 数据库与对象存储使用托管服务

## 当前仓库落地顺序

### 已确定

- 继续保留现有 `Scrapy + Playwright + PostgreSQL + Redis + Docker`
- 统一入库模型从本仓库直接演进

### 第一批改造

1. 在根目录补充架构文档
2. 增加统一新闻主表迁移 SQL
3. 将当前 pipeline 改为统一主表 + legacy table 双写
4. spider 增量依赖已从 legacy table 主逻辑迁移到统一 helper，legacy table 仅作为回退兜底

### 第二批改造

1. 增加 `Celery` 调度与异步任务
2. 落地翻译与摘要生成
3. 增加 `pgvector` 与 chunk 化
4. 增加 `FastAPI` 搜索接口
5. 增加 `Next.js` 展示层

## 当前实现状态

本次提交先落地以下内容：

- 根目录架构文档
- 统一数据模型迁移 SQL
- Scrapy 入库 pipeline 的统一化改造

翻译服务、embedding 服务、API 与 Web 将在后续步骤继续落地。
