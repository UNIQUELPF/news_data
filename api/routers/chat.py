import json
import os
import httpx
import asyncio
from typing import Optional, AsyncGenerator
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pipeline.db import get_db_connection
from pipeline.llm_client import embed_texts, get_llm_base_url, _get_headers
from pipeline.qdrant_utils import get_qdrant_client, COLLECTION_NAME
from api.routers.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-v4-flash")
CHAT_THINK_MODEL = os.getenv("CHAT_THINK_MODEL", "deepseek-v4-pro")
CHAT_RAG_TOP_K = int(os.getenv("CHAT_RAG_TOP_K", 5))

def get_chat_base_url():
    url = os.getenv("CHAT_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return url[:-1] if url.endswith("/") else url

def get_chat_headers():
    api_key = os.getenv("CHAT_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="CHAT_API_KEY or OPENAI_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    think_mode: bool = False

@router.post("/sessions")
def create_session(user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Check if the user already has a session with no user messages
        cursor.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at 
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id AND m.role = 'user'
            WHERE s.user_id = %s
            GROUP BY s.id
            HAVING COUNT(m.id) = 0
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (user['sub'],)
        )
        existing_empty = cursor.fetchone()
        if existing_empty:
            existing_empty['id'] = str(existing_empty['id'])
            return existing_empty

        cursor.execute(
            "INSERT INTO chat_sessions (user_id) VALUES (%s) RETURNING id, title, created_at, updated_at",
            (user['sub'],)
        )
        connection.commit()
        session = cursor.fetchone()
        session['id'] = str(session['id'])
        return session
    finally:
        connection.close()

@router.get("/sessions")
def list_sessions(user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE user_id = %s ORDER BY updated_at DESC",
            (user['sub'],)
        )
        sessions = cursor.fetchall()
        for s in sessions:
            s['id'] = str(s['id'])
            s['created_at'] = s['created_at'].isoformat() if s['created_at'] else None
            s['updated_at'] = s['updated_at'].isoformat() if s['updated_at'] else None
        return sessions
    finally:
        connection.close()

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM chat_sessions WHERE id = %s AND user_id = %s", (session_id, user['sub']))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found or not owned by user")
        connection.commit()
        return {"status": "ok"}
    finally:
        connection.close()

@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT 1 FROM chat_sessions WHERE id = %s AND user_id = %s", (session_id, user['sub']))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Session not found or not owned by user")

        cursor.execute(
            "SELECT id, role, content, think_content, model, context_article_ids, created_at FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,)
        )
        messages = cursor.fetchall()
        for m in messages:
            m['created_at'] = m['created_at'].isoformat() if m['created_at'] else None
        return messages
    finally:
        connection.close()

def _save_assistant_message(session_id: str, content: str, think_content: str, model: str, article_ids: list):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content, think_content, model, context_article_ids) VALUES (%s, %s, %s, %s, %s, %s)",
            (session_id, 'assistant', content, think_content if think_content else None, model, article_ids)
        )
        cursor.execute("UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
        connection.commit()
    finally:
        connection.close()

async def _stream_chat_response(session_id: str, user_id: str, message: str, think_mode: bool) -> AsyncGenerator[str, None]:
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        # Check session
        cursor.execute("SELECT title FROM chat_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
        session = cursor.fetchone()
        if not session:
            yield "data: " + json.dumps({"error": "Session not found"}) + "\n\n"
            return
            
        # If title is default, update it to first 20 chars of message
        if session['title'] == '新会话':
            new_title = message[:20] + "..." if len(message) > 20 else message
            cursor.execute("UPDATE chat_sessions SET title = %s WHERE id = %s", (new_title, session_id))

        # Insert user message
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, 'user', message)
        )
        
        # Get history (limit to last 10 messages for context window)
        cursor.execute(
            """
            SELECT role, content FROM chat_messages 
            WHERE session_id = %s 
            ORDER BY created_at DESC LIMIT 10
            """,
            (session_id,)
        )
        history = list(reversed(cursor.fetchall()))
        connection.commit()
    finally:
        connection.close()

    model = CHAT_THINK_MODEL if think_mode else CHAT_MODEL
    
    # 1. Define tools (Function Calling)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_news_articles",
                "description": "搜索全球政经新闻数据库，获取最新文章以回答复杂的政经和时事问题。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "优化后的搜索关键词（如 '埃及通胀率' 或 '沙特石油产量'），必须将用户问题转化为最适合向量库搜索的核心词"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返回的文章数量，默认 5",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # Prepare message flow
    system_prompt = (
        '# 角色定义\n'
        '你是"政经小助手"，一个基于内部新闻数据库的专业全球政治经济分析助手。\n'
        '你的知识**仅限于**通过 `search_news_articles` 工具从数据库中检索到的新闻文章。\n\n'

        '# 核心原则（严格遵守）\n'
        '1. **严禁编造**：你的所有事实性回答必须且只能基于检索到的文章内容。绝对不允许凭空捏造数据、来源、日期或任何事实信息。\n'
        '2. **坦诚无知**：如果检索结果为空或不包含用户所问的信息，你必须明确告知"数据库中暂未检索到相关信息"，绝不可自行补充或推测。\n'
        '3. **严格引用**：每一个来自检索结果的事实性陈述，都必须标注来源，格式为 `[文章 ID]`（例如 `[文章 102]`）。不得引用未经检索返回的文章。\n\n'

        '# 工具使用规则\n'
        '- 当用户提出与政治、经济、时事、国际关系相关的事实性问题时，**必须先调用** `search_news_articles` 工具进行检索，然后基于检索结果回答。\n'
        '- 当用户的问题是打招呼、日常寒暄、或与政经新闻完全无关时，直接回复，**严禁调用工具**。\n'
        '- 将用户的问题转化为最有效的搜索关键词（而非直接传入原始问题）。\n\n'

        '# 关于自身的问题\n'
        '当用户询问你的身份、能力、数据范围等问题时，请据实回答：\n'
        '- 你是"政经小助手"，基于团队自建的全球政经新闻数据库提供问答服务。\n'
        '- 数据库收录了来自全球多个国家和地区的主流政经新闻媒体文章。\n'
        '- 你只能检索数据库中已收录的文章，无法访问互联网或其他外部数据源。\n'
        '- 不要编造具体的数据量、覆盖日期范围或数据源列表等你并不确切知道的信息。\n\n'

        '# 回答格式\n'
        '- 使用清晰、专业的中文回答。\n'
        '- 涉及多个来源时，分点整理，条理清晰。\n'
        '- 区分"文章中明确提到的信息"和"你自己的分析推断"，后者需明确标注为分析观点。\n'
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[:-1]:
        messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": message})

    tool_called = False
    context_article_ids = []
    context_text = ""
    
    try:
        tool_called_at_least_once = False
        context_article_ids = []
        
        # Fully streaming multi-turn agent loop (max 3 turns to prevent infinite loops)
        async with httpx.AsyncClient(timeout=60.0) as client:
            for loop_idx in range(3):
                full_content = ""
                full_think_content = ""
                tool_calls_buffer = {}
                
                # Turn 1, 2, 3 always run with tools available so the model can search up to 3 times
                async with client.stream(
                    "POST",
                    f"{get_chat_base_url()}/chat/completions",
                    headers=get_chat_headers(),
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "stream": True
                    }
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: ") and chunk != "data: [DONE]":
                            data_str = chunk[6:]
                            try:
                                data = json.loads(data_str)
                                delta = data['choices'][0]['delta']
                                
                                # Instantly yield reasoning chunks to the frontend for real-time progress!
                                if 'reasoning_content' in delta and delta['reasoning_content']:
                                    think = delta['reasoning_content']
                                    full_think_content += think
                                    yield "data: " + json.dumps({"type": "think", "text": think}) + "\n\n"
                                    
                                # Instantly yield regular response content chunks to the frontend!
                                if 'content' in delta and delta['content']:
                                    content = delta['content']
                                    full_content += content
                                    yield "data: " + json.dumps({"type": "content", "text": content}) + "\n\n"
                                    
                                # Buffer and accumulate tool calls chunks if any
                                if 'tool_calls' in delta and delta['tool_calls']:
                                    for tc in delta['tool_calls']:
                                        idx = tc.get('index', 0)
                                        if idx not in tool_calls_buffer:
                                            tool_calls_buffer[idx] = {
                                                "id": tc.get("id", ""),
                                                "type": tc.get("type", "function"),
                                                "function": {
                                                    "name": tc.get("function", {}).get("name", ""),
                                                    "arguments": tc.get("function", {}).get("arguments", "")
                                                }
                                            }
                                        else:
                                            if "id" in tc and tc["id"]:
                                                tool_calls_buffer[idx]["id"] = tc["id"]
                                            if "function" in tc:
                                                fn = tc["function"]
                                                if "name" in fn and fn["name"]:
                                                    tool_calls_buffer[idx]["function"]["name"] += fn["name"]
                                                if "arguments" in fn and fn["arguments"]:
                                                    tool_calls_buffer[idx]["function"]["arguments"] += fn["arguments"]
                            except Exception:
                                pass
                
                # Convert the accumulated tool calls buffer into a sorted list
                tool_calls = [v for k, v in sorted(tool_calls_buffer.items())]
                
                if tool_calls:
                    # Append assistant message containing the tool calls to history
                    assistant_msg = {
                        "role": "assistant",
                        "content": full_content if full_content else None,
                    }
                    if full_think_content:
                        assistant_msg["reasoning_content"] = full_think_content
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    messages.append(assistant_msg)
                    
                    # Execute all tools requested in this turn
                    for tc in tool_calls:
                        tool_called_at_least_once = True
                        args_str = tc["function"]["arguments"]
                        try:
                            args = json.loads(args_str)
                        except Exception:
                            args = {}
                        search_query = args.get('query', message)
                        limit = args.get('limit', CHAT_RAG_TOP_K)
                        
                        # Execute search - search Qdrant and Postgres
                        query_vectors, _ = embed_texts([search_query])
                        current_turn_article_ids = []
                        context_text = ""
                        
                        if query_vectors:
                            q_client = get_qdrant_client()
                            search_results = q_client.query_points(
                                collection_name=COLLECTION_NAME,
                                query=query_vectors[0],
                                limit=limit,
                                with_payload=True
                            )
                            
                            if search_results and search_results.points:
                                valid_points = [res for res in search_results.points if res.score >= 0.4]
                                if valid_points:
                                    current_turn_article_ids = list(dict.fromkeys([res.payload["article_id"] for res in valid_points]))
                                    for aid in current_turn_article_ids:
                                        if aid not in context_article_ids:
                                            context_article_ids.append(aid)
                                    
                                    connection = get_db_connection()
                                    try:
                                        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                                            cursor.execute(
                                                """
                                                SELECT a.id, COALESCE(t.title_translated, a.title_original) as title, COALESCE(t.content_translated, a.content_plain) as content
                                                FROM articles a
                                                LEFT JOIN article_translations t ON t.article_id = a.id AND t.target_language = 'zh-CN'
                                                WHERE a.id = ANY(%s)
                                                """,
                                                (current_turn_article_ids,)
                                            )
                                            articles = cursor.fetchall()
                                            for a in articles:
                                                content_preview = a['content'][:1000] if a['content'] else ""
                                                context_text += f"\n[Document {a['id']}] Title: {a['title']}\nContent: {content_preview}\n"
                                    finally:
                                        connection.close()
                        
                        # Push retrieved source articles update to frontend
                        yield "data: " + json.dumps({"type": "context", "article_ids": context_article_ids}) + "\n\n"
                        
                        # Append tool response message to history
                        tool_content = context_text if context_text else "暂无匹配的资料。"
                        if loop_idx == 2:
                            tool_content += "\n\n【系统特别指令】：已达到最大检索次数。请根据目前所有检索到的参考文章直接为用户做出最终汇总分析解答。如果确实没有搜到海力士的实时股价，请如实告知用户，并汇总已知的上市地点及历史信息，严禁输出任何工具调用标签或进行搜索尝试。"
                            
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc['id'],
                            "name": "search_news_articles",
                            "content": tool_content
                        })
                else:
                    # No more tools requested. Complete successfully!
                    yield "data: [DONE]\n\n"
                    _save_assistant_message(session_id, full_content, full_think_content, model, context_article_ids)
                    return
            
            # --- FINAL FORCED SYNTHESIS STAGE ---
            # If the loop finished (meaning 3 tool searches were executed), invoke the LLM one final time completely WITHOUT tools to synthesize the final streamed response.
            full_content = ""
            full_think_content = ""
            
            async with client.stream(
                "POST",
                f"{get_chat_base_url()}/chat/completions",
                headers=get_chat_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: ") and chunk != "data: [DONE]":
                        data_str = chunk[6:]
                        try:
                            data = json.loads(data_str)
                            delta = data['choices'][0]['delta']
                            
                            if 'reasoning_content' in delta and delta['reasoning_content']:
                                think = delta['reasoning_content']
                                full_think_content += think
                                yield "data: " + json.dumps({"type": "think", "text": think}) + "\n\n"
                                
                            if 'content' in delta and delta['content']:
                                content = delta['content']
                                full_content += content
                                yield "data: " + json.dumps({"type": "content", "text": content}) + "\n\n"
                        except Exception:
                            pass
            
            yield "data: [DONE]\n\n"
            _save_assistant_message(session_id, full_content, full_think_content, model, context_article_ids)
            return
            
    except Exception as e:
        yield "data: " + json.dumps({"type": "error", "text": str(e)}) + "\n\n"


@router.post("/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest, user = Depends(get_current_user)):
    return StreamingResponse(
        _stream_chat_response(session_id, user['sub'], req.message, req.think_mode),
        media_type="text/event-stream"
    )
