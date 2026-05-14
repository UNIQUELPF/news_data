import os
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from pipeline.db import get_db_connection

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-to-a-random-string")
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", 7))
PWD_SALT = "news_salt"

class LoginRequest(BaseModel):
    username: str
    password: str

def _create_jwt_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_admin(user = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user

def verify_password(plain_password, salted_hash):
    if not salted_hash or ':' not in salted_hash:
        return False
    salt, original_hash = salted_hash.split(':')
    hash_val = hashlib.sha256((plain_password + salt).encode()).hexdigest()
    return hash_val == original_hash

def hash_password(password):
    import secrets
    salt = secrets.token_hex(8)
    hash_val = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hash_val}"

@router.post("/login")
def login(req: LoginRequest):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Find user by username
        cursor.execute("SELECT * FROM users WHERE username = %s", (req.username,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
            
        if not user['is_active']:
            raise HTTPException(status_code=403, detail="User account is deactivated")
            
        if not verify_password(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid username or password")
            
        # Update last login
        cursor.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user['id'],))
        connection.commit()
        
        token = _create_jwt_token(str(user['id']), user['username'], user['role'])
        
        return {
            "token": token,
            "user": {
                "id": str(user['id']),
                "username": user['username'],
                "nickname": user['nickname'],
                "role": user['role']
            }
        }
    finally:
        connection.close()

@router.get("/me")
def get_me(user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, username, nickname, role, is_active FROM users WHERE id = %s", (user['sub'],))
        db_user = cursor.fetchone()
        if not db_user or not db_user['is_active']:
            raise HTTPException(status_code=401, detail="User not found or deactivated")
        return {
            "id": str(db_user['id']),
            "username": db_user['username'],
            "nickname": db_user['nickname'],
            "role": db_user['role']
        }
    finally:
        connection.close()
