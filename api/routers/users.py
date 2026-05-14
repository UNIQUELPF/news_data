from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from pipeline.db import get_db_connection
from api.routers.auth import get_current_admin, hash_password

router = APIRouter(dependencies=[Depends(get_current_admin)])

class UserCreateRequest(BaseModel):
    username: str
    password: str
    nickname: str
    role: str = "user"
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class UserUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

@router.get("/")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    nickname: Optional[str] = None,
    role: Optional[str] = None
):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Build query
        where_clauses = []
        params = []
        
        if nickname:
            where_clauses.append("nickname ILIKE %s")
            params.append(f"%{nickname}%")
        
        if role and role != "全部":
            where_clauses.append("role = %s")
            params.append(role)
            
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
            
        # Count total
        count_query = f"SELECT COUNT(*) as total FROM users {where_sql}"
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()['total']
        
        # Get items
        offset = (page - 1) * page_size
        query = f"""
            SELECT id, username, nickname, role, is_active, phone, email, created_at, last_login_at 
            FROM users 
            {where_sql} 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        cursor.execute(query, tuple(params))
        users = cursor.fetchall()
        
        for u in users:
            u['id'] = str(u['id'])
            if u['created_at']:
                u['created_at'] = u['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            if u['last_login_at']:
                u['last_login_at'] = u['last_login_at'].strftime("%Y-%m-%d %H:%M:%S")
                
        return {
            "items": users,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    finally:
        connection.close()

@router.post("/")
def create_user(req: UserCreateRequest):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id FROM users WHERE username = %s", (req.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
            
        pwd_hash = hash_password(req.password)
        
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, nickname, role, phone, email) 
            VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING id, username, nickname, role, is_active
            """,
            (req.username, pwd_hash, req.nickname, req.role, req.phone, req.email)
        )
        connection.commit()
        user = cursor.fetchone()
        user['id'] = str(user['id'])
        return user
    finally:
        connection.close()

@router.put("/{user_id}")
def update_user(user_id: str, req: UserUpdateRequest):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        updates = []
        params = []
        
        if req.nickname is not None:
            updates.append("nickname = %s")
            params.append(req.nickname)
        if req.password is not None and req.password.strip() != "":
            updates.append("password_hash = %s")
            params.append(hash_password(req.password))
        if req.role is not None:
            updates.append("role = %s")
            params.append(req.role)
        if req.phone is not None:
            updates.append("phone = %s")
            params.append(req.phone)
        if req.email is not None:
            updates.append("email = %s")
            params.append(req.email)
        if req.is_active is not None:
            updates.append("is_active = %s")
            params.append(req.is_active)
            
        if not updates:
            return {"status": "ok", "message": "Nothing to update"}
            
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, username, nickname, role, is_active"
        params.append(user_id)
        
        cursor.execute(query, tuple(params))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        connection.commit()
        user['id'] = str(user['id'])
        return user
    finally:
        connection.close()

@router.put("/{user_id}/toggle")
def toggle_user(user_id: str):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s RETURNING id, is_active", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        connection.commit()
        return user
    finally:
        connection.close()

@router.delete("/{user_id}")
def delete_user(user_id: str):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        connection.commit()
        return {"status": "ok"}
    finally:
        connection.close()
