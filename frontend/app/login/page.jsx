"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setAuth, getUser } from "../../lib/auth";
import "../globals.css";

function LoginContent() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (getUser()) {
      router.push("/");
    }
  }, [router]);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError("请输入用户名和密码");
      return;
    }
    
    setLoading(true);
    setError("");
    
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "登录失败");
      
      setAuth(data.token, data.user);
      
      const redirect = searchParams.get("redirect") || "/";
      router.push(redirect);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'linear-gradient(180deg, #12365e 0%, #0e2c4f 100%)' }}>
      <div style={{ background: '#fff', padding: '40px', borderRadius: '24px', width: '100%', maxWidth: '400px', boxShadow: '0 20px 40px rgba(0,0,0,0.2)' }}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <div style={{ display: 'inline-flex', justifyContent: 'center', alignItems: 'center', width: '60px', height: '60px', borderRadius: '50%', background: 'rgba(239, 201, 76, 0.1)', color: '#efc94c', fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>◎</div>
          <h1 style={{ margin: 0, fontSize: '24px', color: '#18324b' }}>全球政治经济数据库</h1>
          <p style={{ margin: '8px 0 0', color: '#6f8298', fontSize: '14px' }}>请输入账号密码登录</p>
        </div>

        {error && (
          <div style={{ padding: '12px', background: '#fee2e2', color: '#dc2626', borderRadius: '8px', marginBottom: '20px', fontSize: '14px', textAlign: 'center' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="field">
            <label>账号</label>
            <input 
              type="text" 
              placeholder="请输入用户名" 
              value={username}
              onChange={e => setUsername(e.target.value)}
              disabled={loading}
              autoFocus
            />
          </div>
          <div className="field">
            <label>密码</label>
            <input 
              type="password" 
              placeholder="请输入密码" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              disabled={loading}
            />
          </div>
          <button type="submit" disabled={loading} style={{ minHeight: '50px', background: '#2457d6', color: '#fff', border: 'none', borderRadius: '18px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', marginTop: '8px' }}>
            {loading ? "登录中..." : "登录"}
          </button>
        </form>
        
        <div style={{ marginTop: '24px', textAlign: 'center', color: '#6f8298', fontSize: '12px' }}>
          提示：初次使用请联系管理员分配账号
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
