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
        
        # RAG Pipeline
        # 1. Embed query
        query_vectors, _ = embed_texts([message])
        context_text = ""
        context_article_ids = []
        
        if query_vectors:
            # 2. Search Qdrant
            q_client = get_qdrant_client()
            search_results = q_client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vectors[0],
                limit=CHAT_RAG_TOP_K,
                with_payload=True
            )
            
            if search_results and search_results.points:
                article_ids = list(dict.fromkeys([res.payload["article_id"] for res in search_results.points]))
                context_article_ids = article_ids
                
                # 3. Fetch article content
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

        connection.commit()
    finally:
        connection.close()

    system_prompt = (
        "你是'政经小助手'，一个专业的全球政治经济分析助手。\n"
        "你需要基于提供的参考资料来回答用户的问题。\n"
        "如果提供的资料无法回答问题，请依据你的常识回答，但必须声明这不是从资料中获得的。\n"
        "引用资料时请说明来源，比如 '[根据参考资料 102]'。\n\n"
        "参考资料：\n" + (context_text if context_text else "暂无匹配的资料。")
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[:-1]: # exclude the latest user message which is appended below
        messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": message})

    model = CHAT_THINK_MODEL if think_mode else CHAT_MODEL
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.5
    }

    full_content = ""
    full_think_content = ""
    
    # Send context articles to client first
    yield "data: " + json.dumps({"type": "context", "article_ids": context_article_ids}) + "\n\n"

    try:
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
                            
                            # Standard content
                            if 'content' in delta and delta['content']:
                                content = delta['content']
                                full_content += content
                                yield "data: " + json.dumps({"type": "content", "text": content}) + "\n\n"
                                
                            # Think content (for deepseek reasoning models)
                            if 'reasoning_content' in delta and delta['reasoning_content']:
                                think = delta['reasoning_content']
                                full_think_content += think
                                yield "data: " + json.dumps({"type": "think", "text": think}) + "\n\n"
                        except Exception as e:
                            print(f"Error parsing SSE chunk: {e}")
                            
        yield "data: [DONE]\n\n"
        
        # Save assistant message to DB
        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (session_id, role, content, think_content, model, context_article_ids) VALUES (%s, %s, %s, %s, %s, %s)",
                (session_id, 'assistant', full_content, full_think_content if full_think_content else None, model, context_article_ids)
            )
            cursor.execute("UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
            connection.commit()
        finally:
            connection.close()
            
    except Exception as e:
        yield "data: " + json.dumps({"type": "error", "text": str(e)}) + "\n\n"


@router.post("/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest, user = Depends(get_current_user)):
    return StreamingResponse(
        _stream_chat_response(session_id, user['sub'], req.message, req.think_mode),
        media_type="text/event-stream"
    )
