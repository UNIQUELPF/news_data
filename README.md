# news_data

当前仓库用于建设“全球政治经济数据库”的采集与检索底座。

部署与联调步骤见 [DEPLOYMENT.md](docs/DEPLOYMENT.md)。
发版约定见 [RELEASE.md](docs/RELEASE.md)。
上线前待办见 [LAUNCH_TODO.md](docs/LAUNCH_TODO.md)。
搜索调优基线见 [SEARCH_TUNING.md](docs/SEARCH_TUNING.md)。
生产回填 runbook 见 [PRODUCTION_ROLLOUT.md](docs/PRODUCTION_ROLLOUT.md)。
搜索验收步骤见 [SEARCH_VALIDATION.md](docs/SEARCH_VALIDATION.md)。
流程架构图见 [PIPELINE_ARCHITECTURE.md](docs/PIPELINE_ARCHITECTURE.md)。

前端工程化骨架已创建在 [frontend](/home/fanhe/NingTai/news_data/frontend)。
当前默认入口就是 React / Next.js 工程化前端：

- 同域首页：`/`
- 管理台：`/admin`

CI 也已补齐最小骨架，位于 [.github/workflows/frontend-ci.yml](/home/fanhe/NingTai/news_data/.github/workflows/frontend-ci.yml) 和 [.github/workflows/python-sanity.yml](/home/fanhe/NingTai/news_data/.github/workflows/python-sanity.yml)：

- `Frontend CI`：安装前端依赖、运行 `npm test`、校验 `docker compose config`、构建 `frontend` 镜像
- `Frontend CI`：安装前端依赖、运行 `npm run lint`、`npm test`、校验 `docker compose config`、构建 `frontend` 镜像
- `Python CI / python-lint`：安装 Python 依赖和开发依赖，执行 `ruff check api pipeline tests`
- `Python CI / python-test`：安装 Python 依赖，执行 `python -m compileall api pipeline news_scraper_project`，并运行 `python -m unittest discover -s tests -p "test_*.py"`
- `Release Images`：按 `v*` tag 或手动触发规则构建 API / Frontend 镜像，并生成统一 tag

CI 已启用依赖缓存：

- 前端：`setup-node` 的 `npm` 缓存 + Buildx `gha` 层缓存
- Python：`setup-python` 的 `pip` 缓存
- 两条 workflow 都启用了并发取消，避免同一分支重复推送时堆积旧任务

本地可运行的 Python 质量检查：

```bash
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/ruff check api pipeline tests
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Spider 增量迁移的回归检查也已补上：

- [test_spider_incremental_migration.py](/home/fanhe/NingTai/news_data/tests/test_spider_incremental_migration.py)
  - 防止 spider 重新引入 `SELECT MAX(publish_time) FROM ...`
- [test_spider_incremental_runtime.py](/home/fanhe/NingTai/news_data/tests/test_spider_incremental_runtime.py)
  - 验证代表性 spider 初始化逻辑会走 `get_incremental_state()`

本地最小 smoke 验证：

```bash
zsh scripts/smoke.sh
```

如果入口不是默认的 `http://127.0.0.1:18080`，可以传自定义地址：

```bash
zsh scripts/smoke.sh http://127.0.0.1:18080
```

上线前总检查：

```bash
zsh scripts/pre_release_check.sh .env http://127.0.0.1:8000 http://127.0.0.1:18080
```

部署前环境预检：

```bash
zsh scripts/preflight.sh .env
```

如果要求真实翻译和真实 embedding，不允许 placeholder / demo：

```bash
PRODUCTION_PIPELINE_REQUIRED=1 zsh scripts/preflight.sh .env
```

一键启动最小栈并执行迁移：

```bash
zsh scripts/bootstrap_stack.sh .env
```

如果要同时导入 demo 语义数据：

```bash
zsh scripts/bootstrap_stack.sh .env --with-demo-seed
```

## 当前状态

已完成第一阶段的基础改造：

- 新增统一数据模型设计文档：[ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 新增统一新闻主表迁移脚本：[migrations/000001_unified_news_schema.sql](/home/fanhe/NingTai/news_data/migrations/000001_unified_news_schema.sql)
- Scrapy pipeline 已支持：
  - 写入统一主表 `sources` / `articles`
  - 同时保留 legacy table 双写，避免现有 spider 增量逻辑立刻失效
- 所有 spider 的增量时间读取已迁移为统一 helper：
  - 优先读 `sources + articles`
  - 无统一数据时回退 legacy table
  - 不再在 spider 内部直接使用 `SELECT MAX(publish_time)` 作为主增量逻辑

## 启动数据库

```bash
docker compose up -d postgres redis
```

## 应用迁移

在 PostgreSQL 容器启动后执行：

```bash
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000001_unified_news_schema.sql
```

如果你是在宿主机本地执行：

```bash
psql -h 127.0.0.1 -p 5432 -U your_user -d scrapy_db -f migrations/000001_unified_news_schema.sql
```

## 运行爬虫

当前不再保留独立 `crawler` 服务，统一通过 `crawl-worker` 执行采集任务。

手动投递一个爬虫任务：

```bash
docker compose exec -T crawl-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.crawl.run_spider --args='["usa_fed"]'
```

## 启动调度骨架

调度层已接入 `Celery + Redis` 最小骨架，包含：

- `scheduler`：Celery Beat
- `crawl-worker`：执行爬虫任务
- `translation-worker`：预留翻译任务队列
- `embedding-worker`：预留向量任务队列

启动方式：

```bash
docker compose up -d redis scheduler crawl-worker translation-worker embedding-worker
```

手动投递一个翻译任务：

```bash
docker compose exec -T translation-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.translate.translate_next_pending_article
```

当前翻译任务已经接入数据库状态流转：

- 领取 `articles.translation_status = 'pending'` 的文章
- 更新为 `processing`
- 写入 `article_translations`
- 完成后更新为 `completed`

当配置了 `OPENAI_API_KEY` 后，翻译任务会调用 OpenAI 兼容接口生成：

- 中文标题
- 中文摘要
- 中文全文译文

未配置时会自动回退到 placeholder，方便本地联调。

批量回填翻译：

```bash
docker compose exec -T translation-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.translate.translate_backfill_articles --kwargs='{"target_language":"zh-CN","limit":50}'
```

强制重算一批译文：

```bash
docker compose exec -T translation-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.translate.translate_backfill_articles --kwargs='{"target_language":"zh-CN","limit":50,"force":true}'
```

说明：

- 默认会处理 `translation_status in (pending, failed)` 的文章
- 如果文章缺少目标语言的 `article_translations` 记录，也会被纳入回填
- `force=true` 会直接重跑，不看当前翻译状态

手动投递一个 embedding 任务：

```bash
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.embed.embed_next_pending_article
```

当前 embedding 任务已接入数据库状态流转：

- 仅处理 `translation_status = 'completed'` 的文章
- 更新 `articles.embedding_status`
- 将文本按块写入 `article_chunks`
- 配置模型后写入 `article_embeddings`

未配置模型密钥时，embedding 任务会只做 chunk 化，不会报错退出。

批量回填 embedding：

```bash
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.embed.embed_backfill_articles --kwargs='{"limit":50}'
```

强制重算一批已完成文章：

```bash
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.embed.embed_backfill_articles --kwargs='{"limit":50,"force":true}'
```

说明：

- 默认会处理 `translation_status = completed` 且 `embedding_status in (pending, failed)` 的文章
- 如果文章没有 `article_embeddings` 记录，也会被纳入回填
- `force=true` 会直接重跑，不看当前 embedding 状态

分别执行翻译回填和 embedding 回填：

```bash
# 执行翻译回填
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.backfill.manual_global_processing --kwargs='{"target_language":"zh-CN","limit":50,"force":false}'

# 执行 embedding 回填
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.backfill.manual_generate_embeddings --kwargs='{"limit":50,"force":false}'
```

说明：

- 可以分别控制翻译和 embedding 回填
- 适合补历史数据或初始化语义搜索索引
- 通过前端管理面板可以更方便地控制这些任务
- 如果要全量重跑，可传 `force_translate=true` 和 `force_embed=true`

串行执行“爬虫 -> 翻译回填 -> embedding 回填”：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pipeline/run \
  -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  -H "Content-Type: application/json" \
  -d '{"spiders":["malaysia_enanyang","usa_arstechnica"],"target_language":"zh-CN","translate_limit":20,"embed_limit":20}'
```

或者直接用脚本触发并轮询：

```bash
ADMIN_API_TOKEN=your-admin-token \
ADMIN_ACTOR=alex.moro \
SPIDERS=malaysia_enanyang,usa_arstechnica \
zsh scripts/run_pipeline.sh http://127.0.0.1:8000
```

说明：

- `pipeline/run` 会顺序执行指定 spider，再执行翻译和 embedding 回填
- 任务类型会记录为 `pipeline_run`
- `tasks/{task_id}/retry` 现在同时支持 `backfill` 和 `pipeline_run`
- 工程化前端里的管理面板现在也支持在“仅回填 / 完整流程”之间切换，并直接填写 spider 列表
- 完整流程的 spider 模板现在由后端接口 `/api/v1/pipeline/presets` 提供，前后端不再各维护一份
- 管理面板现在会直接显示当前 runtime 状态，包括是否 `production_ready`、翻译模式、embedding provider 和当前 hybrid 权重

查看当前运行时配置：

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/runtime
```

严格按生产配置触发回填：

```bash
zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

支持分批 rollout：

```bash
ROLLOUT_STAGE=small zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=medium zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=large zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

搜索权重也已参数化：

```bash
HYBRID_KEYWORD_WEIGHT=0.35
HYBRID_SEMANTIC_WEIGHT=0.65
```

当前生效权重可以通过 `/api/v1/pipeline/runtime` 查看。

## 真实模型配置

翻译和 embedding 任务使用 OpenAI 兼容接口，默认配置：

- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `TRANSLATION_MODEL=gpt-4.1-mini`
- `EMBEDDING_MODEL=text-embedding-3-small`

需要的环境变量：

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_BASE_URL=https://api.openai.com/v1
export TRANSLATION_MODEL=gpt-4.1-mini
export EMBEDDING_MODEL=text-embedding-3-small
```

如果是 `docker compose` 启动 worker，可以在启动前导出这些环境变量，Compose 会自动透传同名变量。

## 本地 Embedding

embedding 现在支持两种 provider：

- `EMBEDDING_PROVIDER=openai`
- `EMBEDDING_PROVIDER=local`
- `EMBEDDING_PROVIDER=demo`

其中 `demo` 模式用于联调语义搜索和相似文章，不依赖真实模型服务。

如果要使用本地模型，推荐先从 `BAAI/bge-m3` 开始：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cpu
export LOCAL_EMBEDDING_BATCH_SIZE=16
```

说明：

- `LOCAL_EMBEDDING_DEVICE=cpu` 适合开发验证
- 有 GPU 时建议改成 `cuda`
- 本地模式只影响 embedding，不影响翻译；翻译仍然需要 `OPENAI_API_KEY` 或兼容接口
- 首次加载模型会下载权重，时间较长
- `HF_CACHE_DIR` 默认可设为项目内的 `./.cache/huggingface`，会挂载到容器内的 `/root/.cache/huggingface`
- `HF_TOKEN` 会同时透传成 `HF_TOKEN` 和 `HUGGINGFACE_HUB_TOKEN`
- 如果你以前成功下载过 `bge-m3`，可以直接复用宿主机的 Hugging Face 缓存

如果你希望“翻译走云端，embedding 走本地”，这是当前最推荐的组合。

本地 embedding 依赖默认不在主 `requirements.txt` 里，避免基础环境被超大 `torch` 依赖拖慢。需要时单独安装：

```bash
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

如果你的 Python 环境默认拉到的是 CUDA 版 `torch`，建议显式安装 CPU 版 `torch` 后再安装本地 embedding 依赖；否则包体积会非常大。

更完整的安装说明见 [LOCAL_EMBEDDING_SETUP.md](docs/LOCAL_EMBEDDING_SETUP.md)。

可以先复制环境变量模板：

```bash
cp .env.example .env
```

### CPU 开发版

适合本机联调、样例数据验证、小批量 embedding。

推荐配置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cpu
export LOCAL_EMBEDDING_BATCH_SIZE=8
```

依赖安装建议分两步：

```bash
./.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

启动：

```bash
docker compose up -d redis postgres
docker compose up -d embedding-worker
```

手动跑一个 embedding 任务：

```bash
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.embed.embed_next_pending_article
```

CPU 模式的实际建议：

- 只开 `embedding-worker`，不要同时堆多个 embedding worker
- `LOCAL_EMBEDDING_BATCH_SIZE` 从 `4` 或 `8` 起步
- 长文很多时优先缩小 batch，不要先加并发

### GPU 生产版

适合批量处理、持续向量化、搜索索引更新。

推荐配置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cuda
export LOCAL_EMBEDDING_BATCH_SIZE=32
```

依赖安装建议：

```bash
./.venv/bin/python -m pip install torch
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

启动建议：

```bash
docker compose up -d redis postgres
docker compose up -d embedding-worker
```

GPU 模式的实际建议：

- 先确认宿主机 `nvidia-smi` 正常
- `embedding-worker` 单独部署，不要和爬虫、翻译抢同一张卡
- `LOCAL_EMBEDDING_BATCH_SIZE` 从 `16` 起调，再根据显存抬到 `32` 或更高

### 推荐组合

第一版最稳的组合是：

- `translation-worker` 走云端 OpenAI 兼容接口
- `embedding-worker` 走本地 `BAAI/bge-m3`
- API 和爬虫继续用现有容器

这样可以把高质量中文翻译和低成本本地向量化拆开，控制成本也更容易。

## 启动 API

这个 API 设计参考了早期原型界面的交互结构，优先支持：

- 搜索框
- 资讯类别 / 国别 / 组织 / 时间筛选
- 列表分页
- 文章详情
- 相似文章推荐

启动方式：

```bash
docker compose up -d api
```

如果要以同域方式同时打开前端和 API，启动：

```bash
docker compose up -d api web
```

说明：

- `api` 使用独立的轻量镜像 [Dockerfile.api](docker/Dockerfile.api)
- `scheduler` 和 `translation-worker` 使用轻量 Celery 镜像 [Dockerfile.celery](docker/Dockerfile.celery)
- `crawl-worker` 使用带 Playwright 的爬虫镜像 [Dockerfile.crawl](docker/Dockerfile.crawl)
- `embedding-worker` 使用带本地 embedding 依赖的镜像 [Dockerfile.embed](docker/Dockerfile.embed)
- 后端接口迭代和联调会明显更快
- `web` 使用 `nginx` 反向代理静态页面和 `/api/*`
- 同域入口默认是 `http://127.0.0.1:18080`
- `nginx` 已启用基础安全头、gzip 和静态资源缓存

接口：

- `GET /health`
- `GET /api/v1/filters`
- `GET /api/v1/articles`
- `GET /api/v1/articles/{article_id}`
- `GET /api/v1/pipeline/summary`
- `POST /api/v1/pipeline/backfill`
- `GET /api/v1/pipeline/tasks/{task_id}`
- `GET /api/v1/pipeline/tasks`
- `POST /api/v1/pipeline/tasks/{task_id}/cancel`
- `POST /api/v1/pipeline/tasks/{task_id}/retry`

管理接口鉴权：

- `GET /api/v1/pipeline/summary`
- `POST /api/v1/pipeline/backfill`
- `GET /api/v1/pipeline/tasks/{task_id}`
- `GET /api/v1/pipeline/tasks`
- `POST /api/v1/pipeline/tasks/{task_id}/cancel`
- `POST /api/v1/pipeline/tasks/{task_id}/retry`

以上接口现在支持通过 `ADMIN_API_TOKEN` 做最小鉴权。
如果在 `api` 服务环境里配置了 `ADMIN_API_TOKEN`，请求时需要带：

```bash
-H "X-Admin-Token: your-admin-token"
```

推荐同时带上操作人标识，便于审计：

```bash
-H "X-Admin-Actor: alex.moro"
```

`/api/v1/articles` 现在支持三种检索模式：

- `search_mode=keyword`
- `search_mode=semantic`
- `search_mode=hybrid`

说明：

- `keyword`：沿用标题、正文、译文的关键词匹配
- `semantic`：对查询词做 embedding，再和 `article_embeddings` 做相似度排序
- `hybrid`：融合关键词分数和语义分数

如果使用 `semantic` 或 `hybrid`，需要先有可用的 embedding provider，并且文章已经写入 `article_embeddings`。

`GET /api/v1/articles/{article_id}` 现在会额外返回：

- `chunks`
- `similar_articles`

回填任务 API：

- `POST /api/v1/pipeline/backfill`：触发“翻译回填 + embedding 回填”
- `GET /api/v1/pipeline/tasks/{task_id}`：查询任务状态和结果
- `POST /api/v1/pipeline/tasks/{task_id}/cancel`：取消排队中或运行中的任务
- `POST /api/v1/pipeline/tasks/{task_id}/retry`：按原参数重试历史回填任务

示例：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pipeline/backfill \
  -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  -H "Content-Type: application/json" \
  -d '{"target_language":"zh-CN","translate_limit":20,"embed_limit":20}'
```

示例：

```bash
curl http://127.0.0.1:8000/api/v1/articles?page=1&page_size=10
```

```bash
curl "http://127.0.0.1:8000/api/v1/articles?q=OpenAI&country=德国&time_range=1m"
```

```bash
curl "http://127.0.0.1:8000/api/v1/articles?q=欧盟AI法案&search_mode=semantic&page=1&page_size=10"
```

```bash
curl "http://127.0.0.1:8000/api/v1/articles?q=OpenAI&search_mode=hybrid&country=德国&time_range=1m"
```

工程化前端现在已支持两种方式调用 API：

- 如果页面和 API 同源部署，自动使用当前站点的 `/api/v1/*`
- 如果你直接用 `file://` 打开 HTML，默认请求 `http://127.0.0.1:8000`

推荐优先使用 `nginx` 同域入口：

```bash
http://127.0.0.1:18080
```

也可以在页面加载前手动指定：

```html
<script>
  window.APP_API_BASE = "http://127.0.0.1:8000";
</script>
```

管理面板说明：

- 页面顶部“回填任务面板”现在带 `Admin Token` 输入框
- 支持填写“操作人”，会随管理请求一起传到后端
- 输入后会缓存到浏览器 `localStorage`
- 也支持在页面加载前注入 `window.APP_ADMIN_TOKEN`
- 也支持在页面加载前注入 `window.APP_ADMIN_ACTOR`
- 只影响 `/api/v1/pipeline/*` 管理接口
- 搜索和文章详情接口不受影响

审计字段：

- 回填任务会记录 `requested_by`
- 回填任务会记录 `request_ip`
- 回填任务会记录 `user_agent`

如果你已经跑过旧版本迁移，再执行一次：

```bash
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000004_pipeline_task_audit_columns.sql
```

后续将按 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 继续推进：

- 将 spider 增量逻辑从 legacy table 迁移到统一 `articles`
- 引入 `Celery + Redis` 调度
- 增加翻译、摘要、embedding 流水线
- 提供 `FastAPI` 搜索接口与 `Next.js` Web 展示
