# Deployment

这份文档只覆盖当前仓库的最小可部署方案：

- `postgres`
- `redis`
- `api`
- `web`
- 可选的 `scheduler` / `translation-worker` / `embedding-worker` / `crawl-worker`

真实翻译 / embedding 的分批生产回填步骤见 [PRODUCTION_ROLLOUT.md](/home/fanhe/NingTai/news_data/PRODUCTION_ROLLOUT.md)。
生产回填后的搜索验收步骤见 [SEARCH_VALIDATION.md](/home/fanhe/NingTai/news_data/SEARCH_VALIDATION.md)。

当前推荐入口：

- React / Next.js 同域入口：`http://127.0.0.1:18080`
- 管理台入口：`http://127.0.0.1:18080/admin`
- API 直连入口：`http://127.0.0.1:8000`
- Frontend 直连调试入口：`http://127.0.0.1:13000/`

## 1. 环境准备

建议先复制环境文件：

```bash
cp .env.example .env
```

至少确认这些变量：

```bash
POSTGRES_DB=scrapy_db
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

ADMIN_API_TOKEN=change-this-admin-token

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
TRANSLATION_MODEL=gpt-4.1-mini

EMBEDDING_PROVIDER=local
DEMO_EMBEDDING_MODEL=demo-semantic-v1
EMBEDDING_MODEL=text-embedding-3-small
LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
LOCAL_EMBEDDING_DEVICE=cpu
LOCAL_EMBEDDING_BATCH_SIZE=16
```

说明：

- 如果只是联调页面和搜索，可以把 `EMBEDDING_PROVIDER=demo`
- 如果要启用管理面板鉴权，必须设置 `ADMIN_API_TOKEN`
- 如果要跑真实翻译，必须设置 `OPENAI_API_KEY`

完成 `.env` 后，建议先跑一次预检：

```bash
zsh scripts/preflight.sh .env
```

如果目标是生产模式，建议直接启用严格校验：

```bash
PRODUCTION_PIPELINE_REQUIRED=1 zsh scripts/preflight.sh .env
```

## 2. 启动基础服务

先起数据库和缓存：

```bash
docker compose up -d postgres redis
```

再起 API 和同域前端入口：

```bash
docker compose up -d api frontend web
```

如果你需要异步流水线，再起这些：

```bash
docker compose up -d scheduler crawl-worker translation-worker embedding-worker
```

## 3. 执行数据库迁移

按顺序执行以下迁移：

```bash
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000001_unified_news_schema.sql
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000003_pipeline_task_runs.sql
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000004_pipeline_task_audit_columns.sql
```

如果你要加载 demo 语义数据，再执行：

```bash
docker compose exec -T postgres psql -U your_user -d scrapy_db < migrations/000002_demo_semantic_seed.sql
```

说明：

- `000001`：统一文章主表、翻译、chunk、embedding
- `000003`：任务运行记录
- `000004`：任务审计字段
- `000002`：demo 文章和 demo embedding，用于联调搜索和相似文章

## 4. 最小验收

先验 API：

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/api/v1/articles?page=1&page_size=3"
```

再验同域入口：

```bash
curl -I http://127.0.0.1:18080/
curl http://127.0.0.1:18080/health
curl "http://127.0.0.1:18080/api/v1/articles?page=1&page_size=3"
```

也可以直接运行仓库内置的 smoke 脚本：

```bash
zsh scripts/smoke.sh
```

如果入口不是默认地址，可显式传入：

```bash
zsh scripts/smoke.sh http://127.0.0.1:18080
```

打开浏览器访问：

```bash
http://127.0.0.1:18080
```

任务和运行监控入口：

```bash
http://127.0.0.1:18080/admin
```

如果要按发布前标准一次性跑完整检查：

```bash
zsh scripts/pre_release_check.sh .env http://127.0.0.1:8000 http://127.0.0.1:18080
```

## 5. 管理面板

`/admin` 管理台依赖 `/api/v1/pipeline/*`，这些接口受 `ADMIN_API_TOKEN` 保护。

你有两种方式提供 token：

1. 页面输入 `Admin Token`
2. 页面加载前注入：

```html
<script>
  window.APP_ADMIN_TOKEN = "your-admin-token";
  window.APP_ADMIN_ACTOR = "alex.moro";
</script>
```

管理接口请求头：

```bash
X-Admin-Token: your-admin-token
X-Admin-Actor: alex.moro
```

React 管理面板已支持两种模式：

- `仅回填`
- `完整流程`

选择“完整流程”后，可直接在页面里填写 spider 列表并触发 `pipeline_run`。
Spider 模板来源于后端 `/api/v1/pipeline/presets`，因此更新批次定义时只需要改后端配置。
面板顶部还会直接显示 `/api/v1/pipeline/runtime` 的核心状态，包括 `production_ready`、翻译模式、embedding provider 和当前 hybrid 权重。
监控区会同时显示 `/api/v1/pipeline/monitor` 的抓取指标和任务阻塞指标，包括最近抓取、失败 Spider Top、最近失败摘要、近 24 小时 spider 健康度、当前排队任务数，以及翻译/向量阶段的 pending/processing/failed 状态。失败 spider 和失败摘要还支持一键把 spider 预填到“完整流程”表单里，直接做定向重跑。

## 6. 回填与联调

触发回填：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pipeline/backfill \
  -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  -H "Content-Type: application/json" \
  -d '{"target_language":"zh-CN","translate_limit":20,"embed_limit":20}'
```

触发完整流水线：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pipeline/run \
  -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  -H "Content-Type: application/json" \
  -d '{"spiders":["malaysia_enanyang","usa_arstechnica"],"target_language":"zh-CN","translate_limit":20,"embed_limit":20}'
```

或者：

```bash
ADMIN_API_TOKEN=your-admin-token \
ADMIN_ACTOR=alex.moro \
SPIDERS=malaysia_enanyang,usa_arstechnica \
zsh scripts/run_pipeline.sh http://127.0.0.1:8000
```

一键拉起服务、执行迁移并做 smoke：

```bash
zsh scripts/bootstrap_stack.sh .env
```

如果需要 demo 语义数据：

```bash
zsh scripts/bootstrap_stack.sh .env --with-demo-seed
```

查询任务：

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/tasks
```

查询当前 runtime：

```bash
curl -H "X-Admin-Token: your-admin-token" \
  http://127.0.0.1:8000/api/v1/pipeline/runtime
```

严格按生产配置触发回填：

```bash
zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

默认支持三档 rollout：

```bash
ROLLOUT_STAGE=small zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=medium zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
ROLLOUT_STAGE=large zsh scripts/run_production_backfill.sh .env http://127.0.0.1:8000
```

如果要调 hybrid 搜索权重，可在 `.env` 里设置：

```bash
HYBRID_KEYWORD_WEIGHT=0.35
HYBRID_SEMANTIC_WEIGHT=0.65
```

取消任务：

```bash
curl -X POST -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  http://127.0.0.1:8000/api/v1/pipeline/tasks/<task_id>/cancel
```

重试任务：

```bash
curl -X POST -H "X-Admin-Token: your-admin-token" \
  -H "X-Admin-Actor: alex.moro" \
  http://127.0.0.1:8000/api/v1/pipeline/tasks/<task_id>/retry
```

## 7. 本地 Embedding

如果走本地 embedding：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cpu
export LOCAL_EMBEDDING_BATCH_SIZE=8
```

安装可选依赖：

```bash
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

更完整的本地模型说明见 [LOCAL_EMBEDDING_SETUP.md](/home/fanhe/NingTai/news_data/LOCAL_EMBEDDING_SETUP.md)。

## 8. 常见问题

`web` 起不来，提示端口占用

- 当前仓库默认将 `nginx` 映射到 `18080`
- 如果还冲突，改 [docker-compose.yml](/home/fanhe/NingTai/news_data/docker-compose.yml) 里的 `web.ports`

管理面板提示缺少 Admin Token

- 检查 `.env` 里的 `ADMIN_API_TOKEN`
- 检查页面输入的 token 是否与 `api` 服务环境一致

语义搜索没有结果

- 检查是否已导入 `000002_demo_semantic_seed.sql`
- 或检查 `embedding-worker` 是否真的写入了 `article_embeddings`

回填任务一直 `PENDING`

- 检查是否启动了相应 Celery worker
- 组合回填任务至少需要 `embedding-worker`
- 如果后续改成分队列消费，也要确保对应 queue 有 worker 在监听

`pipeline_run` 一直 `PENDING`

- 检查是否启动了 `crawl-worker`
- 爬虫任务路由到 `crawl` queue
- 如果只起了 `translation-worker` / `embedding-worker`，爬虫任务不会被消费
