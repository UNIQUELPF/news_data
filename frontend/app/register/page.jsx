"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "../../lib/auth";
import "../globals.css";

function RegisterContent() {
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPwd, setRegConfirmPwd] = useState("");
  const [regNickname, setRegNickname] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPhone, setRegPhone] = useState("");

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const router = useRouter();

  useEffect(() => {
    if (getUser()) {
      router.push("/");
    }
  }, [router]);

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!regUsername || !regPassword) {
      setError("用户名和密码为必填项");
      return;
    }
    if (regPassword.length < 6) {
      setError("密码长度至少为 6 位");
      return;
    }
    if (regPassword !== regConfirmPwd) {
      setError("两次输入的密码不一致");
      return;
    }
    if (regEmail && !/\S+@\S+\.\S+/.test(regEmail)) {
      setError("邮箱格式不正确");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: regUsername,
          password: regPassword,
          nickname: regNickname || undefined,
          email: regEmail || undefined,
          phone: regPhone || undefined
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "注册失败");

      setSuccess("注册成功！正在跳转到登录页面...");
      
      // Clear register fields
      setRegUsername("");
      setRegPassword("");
      setRegConfirmPwd("");
      setRegNickname("");
      setRegEmail("");
      setRegPhone("");

      setTimeout(() => {
        router.push("/login?prefill=" + encodeURIComponent(regUsername));
      }, 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'radial-gradient(circle at top left, rgba(147, 197, 253, 0.18), transparent 24%), linear-gradient(180deg, #12365e 0%, #0e2c4f 100%)', padding: '24px' }}>
      <div style={{ width: '100%', maxWidth: '500px', backgroundColor: '#ffffff', borderRadius: '32px', boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
        
        {/* Banner Header */}
        <div style={{ backgroundColor: '#0a2b4e', padding: '24px 28px', textAlign: 'center', position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginBottom: '8px' }}>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 'bold', background: 'linear-gradient(135deg, #fbbf24, #ffffff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0, letterSpacing: '1px' }}>全球政治经济数据库</h1>
          </div>
          <p style={{ color: '#b9d0f0', fontSize: '0.85rem', margin: '4px 0 0', letterSpacing: '2px' }}>专业 · 权威 · 智能分析平台</p>
        </div>

        {/* Form Container */}
        <div style={{ padding: '32px 36px' }}>
          
          <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#0a2b4e', marginBottom: '24px', textAlign: 'center' }}>新用户注册</h2>

          {/* Feedback Messages */}
          {error && (
            <div style={{ padding: '12px 16px', background: '#fee2e2', color: '#dc2626', borderRadius: '12px', marginBottom: '20px', fontSize: '14px', border: '1px solid #fca5a5' }}>
              ⚠️ {error}
            </div>
          )}
          {success && (
            <div style={{ padding: '12px 16px', background: '#ecfdf5', color: '#059669', borderRadius: '12px', marginBottom: '20px', fontSize: '14px', border: '1px solid #6ee7b7' }}>
              ✓ {success}
            </div>
          )}

          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                用户名<span style={{ color: '#ef4444', marginLeft: '4px' }}>*</span>
              </label>
              <input 
                type="text" 
                placeholder="唯一登录名，必填" 
                value={regUsername}
                onChange={e => setRegUsername(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
                required
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                昵称
              </label>
              <input 
                type="text" 
                placeholder="用户昵称（选填，默认同用户名）" 
                value={regNickname}
                onChange={e => setRegNickname(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                密码<span style={{ color: '#ef4444', marginLeft: '4px' }}>*</span>
              </label>
              <input 
                type="password" 
                placeholder="密码至少 6 位，必填" 
                value={regPassword}
                onChange={e => setRegPassword(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
                required
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                确认密码<span style={{ color: '#ef4444', marginLeft: '4px' }}>*</span>
              </label>
              <input 
                type="password" 
                placeholder="再次输入密码确认，必填" 
                value={regConfirmPwd}
                onChange={e => setRegConfirmPwd(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
                required
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                邮箱
              </label>
              <input 
                type="email" 
                placeholder="接收验证码或备用登录，选填" 
                value={regEmail}
                onChange={e => setRegEmail(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ width: '80px', flexShrink: 0, textAlign: 'left', fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>
                手机号
              </label>
              <input 
                type="tel" 
                placeholder="手机号码，选填" 
                value={regPhone}
                onChange={e => setRegPhone(e.target.value)}
                disabled={loading}
                style={{ flex: 1, padding: '10px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none', fontSize: '0.85rem' }}
              />
            </div>
            <button type="submit" disabled={loading} style={{ minHeight: '48px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '24px', fontSize: '1rem', fontWeight: 'bold', cursor: 'pointer', marginTop: '10px', transition: 'background 0.2s' }}>
              {loading ? "注册中..." : "注 册"}
            </button>
          </form>

          <div style={{ marginTop: '24px', textAlign: 'right', color: '#6f8298', fontSize: '0.85rem' }}>
            <span>已有账号？<span style={{ color: '#0a2b4e', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => router.push("/login")}>去登录</span></span>
          </div>

        </div>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>}>
      <RegisterContent />
    </Suspense>
  );
}
