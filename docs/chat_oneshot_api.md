# 政经小助手单次聊天接口文档

## 接口地址

同 Docker 网络内调用：

```text
POST http://api:8000/api/v1/chat/oneshot
```

宿主机或外部服务调用：

```text
POST http://127.0.0.1:18080/api/v1/chat/oneshot
```

生产环境替换成实际域名即可。

## 认证方式

请求头携带后台服务 token：

```http
x-admin-token: <ADMIN_API_TOKEN>
```

本地 `.env` 中对应配置项：

```env
ADMIN_API_TOKEN=change-this-admin-token
```

## 请求头

```http
Content-Type: application/json
x-admin-token: <ADMIN_API_TOKEN>
```

## 请求体

```json
{
  "message": "查询塞尔维亚最新的政经新闻，并列出来源",
  "think_mode": false,
  "system_prompt": "你是物流小助手，请从国际物流、港口、航运、通关、贸易风险角度回答用户问题。回答要简洁，优先给出对物流业务的影响和建议。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `message` | string | 是 | 用户问题，例如“查询韩国最新的政经新闻” |
| `think_mode` | boolean | 否 | 是否启用深度思考模型，默认 `false` |
| `system_prompt` | string | 否 | 调用方传入的业务提示词，用于指定助手角色、回答风格、输出格式等 |

`system_prompt` 会优先生效，例如可将助手设定为“物流小助手”。后端仍会保留新闻数据库检索、来源引用、不得编造事实等基础规则。

## 返回类型

接口返回 SSE 流：

```http
Content-Type: text/event-stream
```

不是普通 JSON 一次性返回。调用方需要按流读取 `data:` 行。

## 返回事件格式

每一行形如：

```text
data: {"type":"content","text":"..."}
```

结束标记：

```text
data: [DONE]
```

主要事件类型：

| type | 说明 |
|---|---|
| `session` | 服务端自动创建的临时会话 ID，调用方可忽略 |
| `think` | 模型思考过程文本，调用方可忽略 |
| `content` | 正式回答内容，调用方需要拼接这个字段 |
| `context` | 本次检索命中的文章 ID 列表 |
| `error` | 错误信息 |

## 返回示例

```text
data: {"type":"session","session_id":"ae2cddc3-f1a1-494b-bf86-f09544e4a739"}

data: {"type":"context","article_ids":[185,212,204,796]}

data: {"type":"content","text":"以下是系统数据库中收录的关于塞尔维亚的最新政经新闻："}

data: {"type":"content","text":"\n1. 塞尔维亚总统武契奇即将访华..."}

data: [DONE]
```

调用方一般只需要处理 `type = content`，把所有 `text` 拼接起来，就是最终回答。

## 错误返回

如果 token 错误：

```json
{
  "detail": "Invalid admin token"
}
```

如果请求体格式错误：

```json
{
  "detail": [
    {
      "type": "json_invalid",
      "loc": ["body", 1],
      "msg": "JSON decode error"
    }
  ]
}
```

如果聊天过程中出错，会以 SSE 返回：

```text
data: {"type":"error","text":"错误原因"}
```

## curl 示例

```bash
curl -N -X POST http://127.0.0.1:18080/api/v1/chat/oneshot \
  -H "x-admin-token: change-this-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"message":"查询塞尔维亚最新的政经新闻，并列出来源","think_mode":false,"system_prompt":"你是物流小助手，请从国际物流、港口、航运、通关、贸易风险角度回答用户问题。回答要简洁，优先给出对物流业务的影响和建议。"}'
```

## Node.js 解析示例

```js
async function askNews(message) {
  const res = await fetch("http://127.0.0.1:18080/api/v1/chat/oneshot", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-token": "change-this-admin-token",
    },
    body: JSON.stringify({
      message,
      think_mode: false,
      system_prompt: "你是物流小助手，请从国际物流、港口、航运、通关、贸易风险角度回答用户问题。回答要简洁，优先给出对物流业务的影响和建议。",
    }),
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let answer = "";
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;

      const payload = line.slice(6).trim();
      if (payload === "[DONE]") {
        return answer;
      }

      const event = JSON.parse(payload);

      if (event.type === "content") {
        answer += event.text;
      }

      if (event.type === "error") {
        throw new Error(event.text);
      }
    }
  }

  return answer;
}
```

## Python 解析示例

```python
import json
import requests

def ask_news(message: str) -> str:
    url = "http://127.0.0.1:18080/api/v1/chat/oneshot"

    with requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-admin-token": "change-this-admin-token",
        },
        json={
            "message": message,
            "think_mode": False,
            "system_prompt": "你是物流小助手，请从国际物流、港口、航运、通关、贸易风险角度回答用户问题。回答要简洁，优先给出对物流业务的影响和建议。",
        },
        stream=True,
        timeout=120,
    ) as r:
        r.raise_for_status()

        answer = ""

        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            payload = line[6:].strip()

            if payload == "[DONE]":
                break

            event = json.loads(payload)

            if event.get("type") == "content":
                answer += event["text"]

            if event.get("type") == "error":
                raise RuntimeError(event["text"])

        return answer
```

## 调用链说明

调用方不需要保存 `session_id`，也不需要单独调用 embedding、Qdrant 或文章查询接口。后端会自动完成：

```text
问题理解 -> embedding -> Qdrant 检索 -> PostgreSQL 查文章 -> 大模型总结 -> SSE 返回
```
