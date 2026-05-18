import json
import os
import httpx
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
        "你是'政经小助手'，一个专业的全球政治经济分析助手。\n"
        "你可以通过调用 'search_news_articles' 工具来检索新闻数据库，获取实时的文章和资讯。\n"
        "若用户的问题是打招呼、日常寒暄或与政经新闻完全不沾边，直接回复，严禁调用任何工具。\n"
        "引用检索到的资料回答时，必须指明来源，格式严格为 '[文章 ID]'，例如 '[文章 102]'。"
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[:-1]:
        messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": message})

    tool_called = False
    context_article_ids = []
    context_text = ""
    
    try:
        # First round: Let the LLM decide if it needs to call the search tool (Non-streaming)
        async with httpx.AsyncClient(timeout=60.0) as client:
            first_response = await client.post(
                f"{get_chat_base_url()}/chat/completions",
                headers=get_chat_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto"
                }
            )
            first_response.raise_for_status()
            res_data = first_response.json()
            choice = res_data['choices'][0]
            message_obj = choice['message']
            
            if 'tool_calls' in message_obj and message_obj['tool_calls']:
                tool_called = True
                tool_call = message_obj['tool_calls'][0]
                args = json.loads(tool_call['function']['arguments'])
                search_query = args.get('query', message)
                limit = args.get('limit', CHAT_RAG_TOP_K)
                
                # Execute tool - search Qdrant and Postgres
                query_vectors, _ = embed_texts([search_query])
                if query_vectors:
                    q_client = get_qdrant_client()
                    search_results = q_client.query_points(
                        collection_name=COLLECTION_NAME,
                        query=query_vectors[0],
                        limit=limit,
                        with_payload=True
                    )
                    
                    if search_results and search_results.points:
                        # Enforce similarity threshold on tool-returned scores (lowered to 0.4 for generic queries)
                        valid_points = [res for res in search_results.points if res.score >= 0.4]
                        if valid_points:
                            article_ids = list(dict.fromkeys([res.payload["article_id"] for res in valid_points]))
                            context_article_ids = article_ids
                            
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
                                        (article_ids,)
                                    )
                                    articles = cursor.fetchall()
                                    for a in articles:
                                        content_preview = a['content'][:1000] if a['content'] else ""
                                        context_text += f"\n[Document {a['id']}] Title: {a['title']}\nContent: {content_preview}\n"
                            finally:
                                connection.close()
                
                # Push source articles to frontend first
                yield "data: " + json.dumps({"type": "context", "article_ids": context_article_ids}) + "\n\n"
                
                # Formulate secondary LLM request with tool context
                messages.append(message_obj)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "name": "search_news_articles",
                    "content": context_text if context_text else "暂无匹配的资料。"
                })
                # Add strict role system instruction to tell the LLM that search is complete and it must synthesize the final response without calling tools
                messages.append({
                    "role": "system",
                    "content": "请注意：你已经完成了 search_news_articles 工具调用。现在请根据已经检索到的参考资料直接为用户做出最终分析解答。在这个回答阶段，严禁再次输出任何工具调用标签（如 <||DSML||tool_calls> 或任何 XML/JSON 格式的工具调用指令），直接以自然语言输出给用户。"
                })
                
                # Stream the final synthesis response based on retrieved tools
                payload = {
                    "model": model,
                    "messages": messages,
                    "tools": tools,
                    "stream": True,
                    "temperature": 0.5
                }
                
                full_content = ""
                full_think_content = ""
                
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{get_chat_base_url()}/chat/completions",
                        headers=get_chat_headers(),
                        json=payload
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_lines():
                            if chunk.startswith("data: ") and chunk != "data: [DONE]":
                                data_str = chunk[6:]
                                try:
                                    data = json.loads(data_str)
                                    delta = data['choices'][0]['delta']
                                    
                                    if 'content' in delta and delta['content']:
                                        content = delta['content']
                                        full_content += content
                                        yield "data: " + json.dumps({"type": "content", "text": content}) + "\n\n"
                                        
                                    if 'reasoning_content' in delta and delta['reasoning_content']:
                                        think = delta['reasoning_content']
                                        full_think_content += think
                                        yield "data: " + json.dumps({"type": "think", "text": think}) + "\n\n"
                                except Exception as e:
                                    pass
                
                yield "data: [DONE]\n\n"
                _save_assistant_message(session_id, full_content, full_think_content, model, context_article_ids)
                
            else:
                # No tool needed (greeting/chitchat).
                # Directly stream the pre-generated response from the first call instantly
                yield "data: " + json.dumps({"type": "context", "article_ids": []}) + "\n\n"
                content = message_obj.get('content', '')
                reasoning = message_obj.get('reasoning_content', '')
                
                if reasoning:
                    yield "data: " + json.dumps({"type": "think", "text": reasoning}) + "\n\n"
                if content:
                    yield "data: " + json.dumps({"type": "content", "text": content}) + "\n\n"
                yield "data: [DONE]\n\n"
                
                _save_assistant_message(session_id, content, reasoning, model, [])
                
    except Exception as e:
        yield "data: " + json.dumps({"type": "error", "text": str(e)}) + "\n\n"


@router.post("/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest, user = Depends(get_current_user)):
    return StreamingResponse(
        _stream_chat_response(session_id, user['sub'], req.message, req.think_mode),
        media_type="text/event-stream"
    )
