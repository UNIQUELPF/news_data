import os
import hashlib
import jwt
import redis
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from typing import Optional
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from email.mime.text import MIMEText
from email.header import Header

from pipeline.db import get_db_connection

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-to-a-random-string")
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", 7))
PWD_SALT = "news_salt"

# Redis connection for verification codes
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )
except Exception as e:
    print(f"Warning: Failed to connect to Redis: {e}")
    redis_client = None

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

class LoginRequest(BaseModel):
    username: str
    password: str

class UserRegisterRequest(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class SendCodeRequest(BaseModel):
    email: str

class LoginByCodeRequest(BaseModel):
    email: str
    code: str

class UpdateMeRequest(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None

class VipRenewRequest(BaseModel):
    plan: str

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

def send_verification_code_email(to_email: str, code: str, purpose: str = "登录"):
    # Always print code to stdout/log for local testing
    print(f"\n========================================\n[EMAIL VERIFICATION CODE] To: {to_email}\nCode: {code}\nPurpose: {purpose}\n========================================\n")
    
    if not SMTP_USER or not SMTP_PASSWORD or "@" not in SMTP_USER:
        print("[SMTP Not Fully Configured] Skipping SMTP send, printed to console above.")
        return True # Treat as sent for development if credentials are empty

    subject = f"全球政治经济数据库 - {purpose}验证码"
    content = f"您好，您的验证码是：{code}，有效期为 5 分钟。请勿将此验证码泄露给他人。"
    
    from email.utils import formataddr
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = formataddr((str(Header("全球政治经济数据库", "utf-8")), SMTP_FROM or SMTP_USER))
    message['To'] = to_email
    message['Subject'] = Header(subject, 'utf-8')
    
    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM or SMTP_USER, [to_email], message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

@router.post("/login")
def login(req: LoginRequest):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Find user by username OR email
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (req.username, req.username))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username/email or password")
            
        if not user['is_active']:
            raise HTTPException(status_code=403, detail="User account is deactivated")
            
        if not verify_password(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid username/email or password")
            
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
                "role": user['role'],
                "phone": user.get('phone'),
                "email": user.get('email'),
                "vip_expire_at": user['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if user.get('vip_expire_at') else None
            }
        }
    finally:
        connection.close()

@router.post("/register")
def register(req: UserRegisterRequest):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
        
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (req.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
            
        # Standardise email/phone to None if empty string
        email_val = req.email.strip() if req.email else ""
        if email_val == "":
            email_val = None
        else:
            if not ("@" in email_val and "." in email_val):
                raise HTTPException(status_code=400, detail="Invalid email format")
            # Check if email exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email_val,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
                
        phone_val = req.phone.strip() if req.phone else ""
        if phone_val == "":
            phone_val = None
            
        pwd_hash = hash_password(req.password)
        nickname_val = req.nickname.strip() if req.nickname else ""
        if not nickname_val:
            nickname_val = req.username
            
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, nickname, role, phone, email, is_active) 
            VALUES (%s, %s, %s, 'user', %s, %s, true) 
            RETURNING id, username, nickname, role, is_active, phone, email, vip_expire_at
            """,
            (req.username, pwd_hash, nickname_val, phone_val, email_val)
        )
        connection.commit()
        
        user = cursor.fetchone()
        user['id'] = str(user['id'])
        return user
    finally:
        connection.close()

@router.post("/login/send-code")
def send_login_code(req: SendCodeRequest):
    email = req.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Email not registered")
    finally:
        connection.close()
        
    # Generate 6-digit code
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    
    if redis_client:
        redis_client.set(f"email_code:{email}:login", code, ex=300)
    else:
        # Fallback to local process memory if Redis is down (highly unlikely in this docker stack)
        raise HTTPException(status_code=500, detail="Cache service unavailable")
        
    success = send_verification_code_email(email, code, "登录")
    if not success:
         raise HTTPException(status_code=500, detail="Failed to send verification code email")
         
    return {"message": "Verification code sent successfully"}

@router.post("/login-by-code")
def login_by_code(req: LoginByCodeRequest):
    email = req.email.strip()
    code = req.code.strip()
    
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")
        
    if not redis_client:
        raise HTTPException(status_code=500, detail="Cache service unavailable")
        
    redis_key = f"email_code:{email}:login"
    saved_code = redis_client.get(redis_key)
    
    if not saved_code or saved_code != code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    # Consume code
    redis_client.delete(redis_key)
    
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if not user['is_active']:
            raise HTTPException(status_code=403, detail="User account is deactivated")
            
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
                "role": user['role'],
                "phone": user.get('phone'),
                "email": user.get('email'),
                "vip_expire_at": user['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if user.get('vip_expire_at') else None
            }
        }
    finally:
        connection.close()

@router.get("/me")
def get_me(user = Depends(get_current_user)):
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, username, nickname, role, is_active, phone, email, vip_expire_at, created_at FROM users WHERE id = %s", (user['sub'],))
        db_user = cursor.fetchone()
        if not db_user or not db_user['is_active']:
            raise HTTPException(status_code=401, detail="User not found or deactivated")
        return {
            "id": str(db_user['id']),
            "username": db_user['username'],
            "nickname": db_user['nickname'],
            "role": db_user['role'],
            "phone": db_user['phone'],
            "email": db_user['email'],
            "vip_expire_at": db_user['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if db_user.get('vip_expire_at') else None,
            "created_at": db_user['created_at'].strftime("%Y-%m-%d %H:%M:%S") if db_user.get('created_at') else None
        }
    finally:
        connection.close()

@router.put("/me")
def update_me(req: UpdateMeRequest, current_user = Depends(get_current_user)):
    user_id = current_user['sub']
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        updates = []
        params = []
        
        if req.nickname is not None:
            updates.append("nickname = %s")
            params.append(req.nickname)
            
        if req.email is not None:
            email_val = req.email.strip()
            if email_val == "":
                email_val = None
            else:
                if not ("@" in email_val and "." in email_val):
                    raise HTTPException(status_code=400, detail="Invalid email format")
                # Check email uniqueness
                cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email_val, user_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Email is already in use")
            updates.append("email = %s")
            params.append(email_val)
            
        if req.phone is not None:
            phone_val = req.phone.strip()
            if phone_val == "":
                phone_val = None
            updates.append("phone = %s")
            params.append(phone_val)
            
        if req.new_password is not None and req.new_password.strip() != "":
            if not req.old_password:
                raise HTTPException(status_code=400, detail="Old password is required to change password")
            if not verify_password(req.old_password, user['password_hash']):
                raise HTTPException(status_code=400, detail="Incorrect old password")
            if len(req.new_password) < 6:
                raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
            updates.append("password_hash = %s")
            params.append(hash_password(req.new_password))
            
        if not updates:
            return {
                "id": str(user['id']),
                "username": user['username'],
                "nickname": user['nickname'],
                "role": user['role'],
                "phone": user.get('phone'),
                "email": user.get('email'),
                "vip_expire_at": user['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if user.get('vip_expire_at') else None
            }
            
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING *"
        params.append(user_id)
        cursor.execute(query, tuple(params))
        connection.commit()
        
        updated_user = cursor.fetchone()
        return {
            "id": str(updated_user['id']),
            "username": updated_user['username'],
            "nickname": updated_user['nickname'],
            "role": updated_user['role'],
            "phone": updated_user['phone'],
            "email": updated_user['email'],
            "vip_expire_at": updated_user['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if updated_user.get('vip_expire_at') else None
        }
    finally:
        connection.close()

@router.post("/me/renew-vip")
def renew_vip(req: VipRenewRequest, current_user = Depends(get_current_user)):
    user_id = current_user['sub']
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        now = datetime.now(timezone.utc)
        current_expire = user.get('vip_expire_at')
        
        if current_expire:
            if current_expire.tzinfo is None:
                current_expire = current_expire.replace(tzinfo=timezone.utc)
            start_time = max(now, current_expire)
        else:
            start_time = now
            
        new_expire = start_time + timedelta(days=30)
        
        cursor.execute("UPDATE users SET vip_expire_at = %s WHERE id = %s RETURNING vip_expire_at", (new_expire, user_id))
        connection.commit()
        
        updated = cursor.fetchone()
        return {
            "vip_expire_at": updated['vip_expire_at'].strftime("%Y-%m-%d %H:%M:%S") if updated.get('vip_expire_at') else None
        }
    finally:
        connection.close()
