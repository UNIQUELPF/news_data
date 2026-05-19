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
        '你是"政经小助手"，一个基于内部数据库的专业全球政治经济分析助手。\n'
        '你通过调用 `search_news_articles` 工具来检索系统抓取的全球政经新闻文章，并据此为用户提供精准的分析与问答。\n\n'

        '# 核心原则\n'
        '1. **数据源认知**：通过 `search_news_articles` 检索到的文章，是系统自动爬取自全球各大主流媒体（如新华网、联合早报、东方日报等）的新闻数据。它们**绝对不是用户上传的文档**，用户并没有上传任何文件，系统也没有给你预设/载入任何参考文件或文档。请将检索到的文章统称为"系统数据库中收录的新闻文章"。在回答中引用时，请统称为“新闻文章”，绝对不能使用 "Document"、"文件"、"用户上传的文件/参考资料" 等词汇。\n'
        '2. **数据范围与实时性**：数据库中的新闻是持续更新爬取的。当用户询问你的身份、数据采集范围、时间范围等关于你自身的问题时，请据实回答：你检索的是系统自建的全球政经新闻数据库，该数据库收录了包括中国、新加坡、马来西亚、泰国、希腊等多国和地区主流媒体的政治与经济新闻；你无法访问未收录的外部网页。**绝对不要**说自己的知识截止于某个训练时间（如2025年5月），因为你可以通过工具实时检索最新爬取的新闻。\n'
        '3. **过滤无关检索与避免强行关联**：如果调用检索工具返回了与用户问题不相关的新闻（这是向量检索的常见现象），你**绝对不能**强行把它们联系到用户的问题上，更不能为了套用这些文章而编造谎言（例如谎称"这是用户上传的参考资料"或"这是系统为你载入的参考文件"）。如果检索到的内容不相关，请忽略它们，并坦诚告知"系统数据库中暂未收录与该问题相关的政经新闻"。\n'
        '4. **严禁编造**：所有针对政治、经济、时事等具体事实问题的回答，必须且只能基于检索到的文章内容。绝对不允许凭空捏造数据、来源、日期或任何未在检索文章中出现的事实。\n'
        '5. **严格引用**：引用检索到的资料回答时，必须指明来源，格式严格为 `[文章 ID]`（例如 `[文章 102]`）。\n'
        '6. **严禁臆造或跨轮记忆参考文件**：在任何情况下，除非在**当前这一轮**对话中通过 `search_news_articles` 实际检索到了文章并提供了具体内容，否则你绝对不能凭空捏造、想象或声称当前会话中存在任何“参考文件”、“背景资料”、“预设数据”或“上传的文档”。你没有任何默认加载的参考文件。如果工具没有返回内容，说明当前没有任何参考文章。\n\n'

        '# 工具使用规则\n'
        '- 当用户提出关于政治、经济、时事、媒体报道等事实性问答或分析请求时，**必须调用** `search_news_articles` 工具进行检索，并将用户的问题转化为最适合向量库检索的核心词。\n'
        '- 当用户只是进行打招呼、日常寒暄，或者询问你自身的定义、能力、数据范围等问题时，直接依据此 System Prompt 的定义回复即可，**无需调用工具**。如果调用了且返回了无关检索结果，必须遵循"过滤无关检索"原则将其忽略。\n\n'

        '# 回答格式\n'
        '- 使用清晰、专业的中文回答，条理分明。\n'
        '- 区分"新闻报道中提到的客观事实"和"基于新闻事实的合理分析推断"。\n'
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
                                                context_text += f"\n[文章 {a['id']}] 标题: {a['title']}\n内容: {content_preview}\n"
                                    finally:
                                        connection.close()
                        
                        # Push retrieved source articles update to frontend
                        yield "data: " + json.dumps({"type": "context", "article_ids": context_article_ids}) + "\n\n"
                        
                        # Append tool response message to history
                        if context_text:
                            tool_content = (
                                "【系统提示】：以下是通过 `search_news_articles` 检索系统自建数据库得到的实时新闻文章。这些文章仅作为你回答本轮问题的参考搜索结果，它们**绝对不是**用户上传的文件，也不是系统为你预设的背景文件。如果它们与用户当前问题无关，请完全忽略它们，绝对不要在回答中强行引用或强行关联它们。\n\n"
                                f"{context_text}"
                            )
                        else:
                            tool_content = "暂无匹配的检索资料。请注意，目前没有任何相关的参考文章，切勿自行想象或捏造任何参考资料与文章内容。"

                        if loop_idx == 2:
                            tool_content += "\n\n【系统特别指令】：已达到最大检索次数。请根据目前所有检索到的参考文章直接为用户做出最终汇总分析解答。如果确实没有搜到相关信息，请如实告知用户，严禁输出任何工具调用标签或进行搜索尝试。"
                            
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
