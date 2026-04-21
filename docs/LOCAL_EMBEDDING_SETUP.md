# Local Embedding Setup

这份文档用于把本地 embedding 跑起来，默认模型是 `BAAI/bge-m3`。

适用场景：

- 翻译走云端，embedding 走本地
- 只在本地或内网环境生成向量
- 避免 embedding 请求长期依赖外部服务

## 通用准备

先复制环境变量模板：

```bash
cp .env.example .env
```

推荐至少设置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export HF_CACHE_DIR=./.cache/huggingface
export HF_TOKEN=your_huggingface_token
```

说明：

- `HF_CACHE_DIR` 会被挂载到容器内的 `/root/.cache/huggingface`
- 推荐直接用项目内的 `./.cache/huggingface`，便于迁移和复用
- `HF_TOKEN` 会同时作为 `HF_TOKEN` 和 `HUGGINGFACE_HUB_TOKEN` 传给容器
- 如果宿主机已经缓存过 `BAAI/bge-m3`，容器会直接复用，不必重新下载
- 没有 `HF_TOKEN` 也能下载，但会受匿名限速影响

embedding worker 启动命令：

```bash
docker compose up -d redis postgres
docker compose up -d embedding-worker
```

手动触发一个任务：

```bash
docker compose exec -T embedding-worker celery -A pipeline.celery_app:celery_app call pipeline.tasks.embed.embed_next_pending_article
```

## macOS CPU

适合 MacBook 本机开发和小批量验证。

推荐配置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cpu
export LOCAL_EMBEDDING_BATCH_SIZE=4
```

建议安装命令：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install torch
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

建议：

- `LOCAL_EMBEDDING_BATCH_SIZE` 从 `4` 开始
- 首次模型下载会比较慢
- 不建议在 Mac CPU 上批量处理长文历史库

## Linux CPU

适合云主机、测试机、没有 GPU 的服务机。

推荐配置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cpu
export LOCAL_EMBEDDING_BATCH_SIZE=8
```

建议安装命令：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

建议：

- CPU 机器只开一个 `embedding-worker`
- 批量补历史数据时，优先降低 `LOCAL_EMBEDDING_BATCH_SIZE`
- 如果系统内存有限，不要和 Playwright 爬虫同时高并发跑

## Linux GPU

适合正式批量向量化和持续更新。

前提：

- 宿主机 `nvidia-smi` 正常
- Docker 侧 GPU 运行时已经可用
- Python 环境能正常安装 GPU 版 `torch`

推荐配置：

```bash
export EMBEDDING_PROVIDER=local
export LOCAL_EMBEDDING_MODEL=BAAI/bge-m3
export LOCAL_EMBEDDING_DEVICE=cuda
export LOCAL_EMBEDDING_BATCH_SIZE=32
```

建议安装命令：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install torch
./.venv/bin/python -m pip install -r requirements-local-embedding.txt
```

建议：

- `embedding-worker` 单独部署，不和翻译或爬虫抢 GPU
- batch size 从 `16` 起调，再逐步增加
- 先用 10 到 50 篇文章做压测，再决定正式参数

## 验证

依赖安装完后，可以先验证本地 provider 是否可用：

```bash
./.venv/bin/python -c "from pipeline.llm_client import get_embedding_provider, get_embedding_model; print(get_embedding_provider(), get_embedding_model())"
```

如果要验证模型是否真的能产出向量：

```bash
EMBEDDING_PROVIDER=local LOCAL_EMBEDDING_MODEL=BAAI/bge-m3 LOCAL_EMBEDDING_DEVICE=cpu ./.venv/bin/python -c "from pipeline.llm_client import embed_texts; vectors, model = embed_texts(['hello world']); print(model, len(vectors), len(vectors[0]))"
```

## 常见问题

`torch` 下载很大：

- Linux 上优先区分 CPU 和 GPU 安装方式
- CPU 环境建议显式使用 PyTorch CPU 源

首次加载很慢：

- 首次会下载 `BAAI/bge-m3` 权重
- 后续会复用本地缓存

worker 没写向量：

- 检查 `articles.translation_status` 是否已经是 `completed`
- 检查 `EMBEDDING_PROVIDER` 是否为 `local`
- 检查 `LOCAL_EMBEDDING_DEVICE` 是否和实际环境匹配
- 查看 `embedding-worker` 日志：

```bash
docker compose logs --tail=200 embedding-worker
```
