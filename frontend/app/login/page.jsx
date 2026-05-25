"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setAuth, getUser } from "../../lib/auth";
import "../globals.css";

function LoginContent() {
  const [loginMethod, setLoginMethod] = useState("password"); // "password" or "emailcode"
  
  // Login form states
  const [loginIdent, setLoginIdent] = useState(""); // Username or Email
  const [loginPassword, setLoginPassword] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginCode, setLoginCode] = useState("");

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [codeCountdown, setCodeCountdown] = useState(0);

  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (getUser()) {
      router.push("/");
    }
  }, [router]);

  // Prefill username if redirected from registration
  useEffect(() => {
    const prefillUser = searchParams.get("prefill");
    if (prefillUser) {
      setLoginIdent(prefillUser);
    }
  }, [searchParams]);

  // Countdown timer logic
  useEffect(() => {
    if (codeCountdown <= 0) return;
    const timer = setInterval(() => {
      setCodeCountdown(prev => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [codeCountdown]);

  // Reset errors/success messages when switching login method
  useEffect(() => {
    setError("");
    setSuccess("");
  }, [loginMethod]);

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    if (!loginIdent || !loginPassword) {
      setError("请填写用户名/邮箱和密码");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginIdent, password: loginPassword })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "登录失败");
      
      setAuth(data.token, data.user);
      setSuccess("登录成功！正在跳转...");
      const redirect = searchParams.get("redirect") || "/";
      setTimeout(() => {
        router.push(redirect);
      }, 500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSendCode = async () => {
    if (!loginEmail) {
      setError("请先输入注册邮箱");
      return;
    }
    if (!/\S+@\S+\.\S+/.test(loginEmail)) {
      setError("请输入正确的邮箱格式");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch("/api/v1/auth/login/send-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "发送验证码失败");
      
      setSuccess("验证码已发送至您的邮箱，请注意查收");
      setCodeCountdown(60);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEmailCodeLogin = async (e) => {
    e.preventDefault();
    if (!loginEmail || !loginCode) {
      setError("请输入邮箱和验证码");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch("/api/v1/auth/login-by-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, code: loginCode })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "验证码登录失败");
      
      setAuth(data.token, data.user);
      setSuccess("登录成功！正在跳转...");
      const redirect = searchParams.get("redirect") || "/";
      setTimeout(() => {
        router.push(redirect);
      }, 500);
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
          
          {/* Tabs for Login Methods */}
          <div style={{ display: 'flex', backgroundColor: '#eff3f8', padding: '6px', borderRadius: '48px', marginBottom: '28px' }}>
            <div 
              style={{ flex: 1, textAlign: 'center', padding: '12px 0', borderRadius: '40px', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s', backgroundColor: loginMethod === "password" ? "#0a2b4e" : "transparent", color: loginMethod === "password" ? "#ffffff" : "#596c80" }}
              onClick={() => setLoginMethod("password")}
            >
              账户密码登录
            </div>
            <div 
              style={{ flex: 1, textAlign: 'center', padding: '12px 0', borderRadius: '40px', fontSize: '0.95rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s', backgroundColor: loginMethod === "emailcode" ? "#0a2b4e" : "transparent", color: loginMethod === "emailcode" ? "#ffffff" : "#596c80" }}
              onClick={() => setLoginMethod("emailcode")}
            >
              邮箱验证码登录
            </div>
          </div>

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

          {loginMethod === "password" ? (
            /* Password Login Form */
            <form onSubmit={handlePasswordLogin} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>用户名 / 邮箱</label>
                <input 
                  type="text" 
                  placeholder="请输入用户名或邮箱" 
                  value={loginIdent}
                  onChange={e => setLoginIdent(e.target.value)}
                  disabled={loading}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none' }}
                  autoFocus
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>密码</label>
                <input 
                  type="password" 
                  placeholder="请输入密码" 
                  value={loginPassword}
                  onChange={e => setLoginPassword(e.target.value)}
                  disabled={loading}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none' }}
                />
              </div>
              <button type="submit" disabled={loading} style={{ minHeight: '50px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '24px', fontSize: '1rem', fontWeight: 'bold', cursor: 'pointer', marginTop: '12px', transition: 'background 0.2s' }} className="btn-primary">
                {loading ? "登录中..." : "登 录"}
              </button>
            </form>
          ) : (
            /* Email Verification Code Login Form */
            <form onSubmit={handleEmailCodeLogin} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>注册邮箱</label>
                <input 
                  type="email" 
                  placeholder="请输入注册邮箱" 
                  value={loginEmail}
                  onChange={e => setLoginEmail(e.target.value)}
                  disabled={loading}
                  style={{ width: '100%', padding: '12px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none' }}
                  autoFocus
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>验证码</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input 
                    type="text" 
                    placeholder="请输入6位验证码" 
                    value={loginCode}
                    onChange={e => setLoginCode(e.target.value)}
                    disabled={loading}
                    style={{ flex: 1, padding: '12px 16px', borderRadius: '20px', border: '1px solid #cbd5e1', outline: 'none' }}
                  />
                  <button 
                    type="button"
                    onClick={handleSendCode} 
                    disabled={loading || codeCountdown > 0} 
                    style={{ padding: '0 16px', height: '48px', borderRadius: '20px', border: '1px solid #cbd5e1', background: '#f1f5f9', fontWeight: 500, fontSize: '0.85rem', cursor: (loading || codeCountdown > 0) ? 'not-allowed' : 'pointer' }}
                  >
                    {codeCountdown > 0 ? `${codeCountdown} 秒后获取` : "获取验证码"}
                  </button>
                </div>
              </div>
              <button type="submit" disabled={loading} style={{ minHeight: '50px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '24px', fontSize: '1rem', fontWeight: 'bold', cursor: 'pointer', marginTop: '12px', transition: 'background 0.2s' }}>
                {loading ? "登录中..." : "登 录"}
              </button>
            </form>
          )}

          <div style={{ marginTop: '24px', textAlign: 'right', color: '#6f8298', fontSize: '0.85rem' }}>
            <span>没有账号？<span style={{ color: '#0a2b4e', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => router.push("/register")}>立即注册</span></span>
          </div>

        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>}>
      <LoginContent />
    </Suspense>
  );
}
