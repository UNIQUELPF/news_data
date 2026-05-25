"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser, setAuth, clearAuth, fetchWithAuth } from "../../lib/auth";
import AppHeader from "../../components/AppHeader";
import SidebarNav from "../../components/SidebarNav";
import "../../app/globals.css";

export default function ProfilePage() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: "", text: "" });

  // Modals state
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showVipModal, setShowVipModal] = useState(false);

  // Edit fields
  const [editNickname, setEditNickname] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");

  // Change password fields
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");

  // VIP selection
  const [selectedPlan, setSelectedPlan] = useState("basic");

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
    } else {
      fetchProfile();
    }
  }, [router]);

  const fetchProfile = async () => {
    try {
      const res = await fetchWithAuth("/api/v1/auth/me");
      if (!res.ok) throw new Error("获取用户信息失败");
      const data = await res.json();
      setProfile(data);
      
      // Update local storage user object to keep in sync
      const currentToken = getToken();
      setAuth(currentToken, {
        id: data.id,
        username: data.username,
        nickname: data.nickname,
        role: data.role,
        email: data.email,
        phone: data.phone,
        vip_expire_at: data.vip_expire_at
      });

      // Populate edit fields
      setEditNickname(data.nickname || "");
      setEditEmail(data.email || "");
      setEditPhone(data.phone || "");

      setIsAuthChecking(false);
    } catch (err) {
      console.error(err);
      clearAuth();
      router.push("/login");
    }
  };

  const handleUpdateInfo = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: "", text: "" });
    try {
      const res = await fetchWithAuth("/api/v1/auth/me", {
        method: "PUT",
        body: {
          nickname: editNickname,
          email: editEmail || "",
          phone: editPhone || ""
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "修改信息失败");
      
      setMessage({ type: "success", text: "个人资料修改成功！" });
      setShowInfoModal(false);
      // Refresh profile data
      fetchProfile();
      // Reload page to update header component state
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setMessage({ type: "error", text: "新密码至少为 6 位" });
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setMessage({ type: "error", text: "两次输入的密码不一致" });
      return;
    }
    
    setLoading(true);
    setMessage({ type: "", text: "" });
    try {
      const res = await fetchWithAuth("/api/v1/auth/me", {
        method: "PUT",
        body: {
          old_password: oldPassword,
          new_password: newPassword
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "修改密码失败");
      
      setMessage({ type: "success", text: "密码修改成功！" });
      setShowPasswordModal(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleRenewVip = async () => {
    setLoading(true);
    setMessage({ type: "", text: "" });
    try {
      const res = await fetchWithAuth("/api/v1/auth/me/renew-vip", {
        method: "POST",
        body: { plan: selectedPlan }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "续费失败");
      
      setMessage({ type: "success", text: `续费成功！最新VIP期限为 ${data.vip_expire_at}` });
      setShowVipModal(false);
      fetchProfile();
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    if (confirm("确定要退出登录吗？")) {
      clearAuth();
      router.push("/login");
    }
  };

  const getVipBadge = () => {
    if (!profile || !profile.vip_expire_at) {
      return <span style={{ background: '#f1f5f9', color: '#64748b', padding: '4px 12px', borderRadius: '40px', fontSize: '0.8rem', fontWeight: 600 }}>普通用户</span>;
    }
    const expire = new Date(profile.vip_expire_at);
    const now = new Date();
    if (expire > now) {
      const days = Math.ceil((expire - now) / (1000 * 60 * 60 * 24));
      return <span style={{ background: '#fef3c7', color: '#d97706', border: '1px solid #fcd34d', padding: '4px 12px', borderRadius: '40px', fontSize: '0.8rem', fontWeight: 600 }}>VIP会员 (剩余 {days} 天)</span>;
    } else {
      return <span style={{ background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5', padding: '4px 12px', borderRadius: '40px', fontSize: '0.8rem', fontWeight: 600 }}>VIP已过期</span>;
    }
  };

  if (isAuthChecking || !profile) {
    return <div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>;
  }

  return (
    <main className="shell">
      <AppHeader subtitle="查看您的账号属性、修改绑定邮箱与密码，并可在此模拟续费体验。" />

      <div className="main-grid">
        <SidebarNav />

        <section className="content-stack">
          {/* Main User Card */}
          <div style={{ maxWidth: '640px', margin: '0 auto', width: '100%', padding: '24px 0' }}>
            
            {/* Header info */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '32px', paddingBottom: '20px', borderBottom: '1px solid #edf2f7' }}>
              <div style={{ width: '64px', height: '64px', background: 'linear-gradient(135deg, #12365e 0%, #0e2c4f 100%)', border: '2px solid #efc94c', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '28px', fontWeight: 'bold', boxShadow: '0 4px 10px rgba(0,0,0,0.1)' }}>
                {(profile.nickname || profile.username || "?")[0].toUpperCase()}
              </div>
              <div>
                <h2 style={{ fontSize: '1.6rem', color: '#0a2b4e', fontWeight: 'bold', margin: 0 }}>用户个人中心</h2>
                <p style={{ margin: '4px 0 0', color: '#6f8298', fontSize: '0.9rem' }}>管理您的账号详情、安全性与服务级别</p>
              </div>
            </div>

            {/* Notification Messages */}
            {message.text && (
              <div style={{ 
                padding: '12px 16px', 
                borderRadius: '12px', 
                marginBottom: '24px', 
                fontSize: '14px', 
                border: '1px solid',
                backgroundColor: message.type === "success" ? "#ecfdf5" : "#fee2e2",
                borderColor: message.type === "success" ? "#6ee7b7" : "#fca5a5",
                color: message.type === "success" ? "#059669" : "#dc2626"
              }}>
                {message.type === "success" ? "✓" : "⚠️"} {message.text}
              </div>
            )}

            {/* Profile Fields List */}
            <div style={{ backgroundColor: '#ffffff', borderRadius: '24px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.02)', overflow: 'hidden', marginBottom: '28px' }}>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>用户名</span>
                <span style={{ color: '#1e293b', fontWeight: 600 }}>{profile.username}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>昵称</span>
                <span style={{ color: '#1e293b' }}>{profile.nickname || <em style={{ color: '#94a3b8' }}>未设置</em>}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>绑定邮箱</span>
                <span style={{ color: '#1e293b' }}>{profile.email || <em style={{ color: '#94a3b8' }}>未绑定</em>}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>绑定手机号</span>
                <span style={{ color: '#1e293b' }}>{profile.phone || <em style={{ color: '#94a3b8' }}>未绑定</em>}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>会员状态</span>
                <div>{getVipBadge()}</div>
              </div>

              {profile.vip_expire_at && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                  <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>会员有效期至</span>
                  <span style={{ color: '#1e293b', fontFamily: 'monospace' }}>{profile.vip_expire_at}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px', borderBottom: '1px solid #edf2f7' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>注册时间</span>
                <span style={{ color: '#64748b' }}>{profile.created_at || "2026-05-01"}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 24px' }}>
                <span style={{ fontWeight: 'bold', color: '#475569', fontSize: '0.95rem' }}>系统权限组</span>
                <span style={{ color: '#0a2b4e', fontWeight: 600 }}>{profile.role === "admin" ? "🛡️ 系统管理员" : "👤 数据库研究员"}</span>
              </div>

            </div>

            {/* Quick Actions Buttons */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
              <button 
                onClick={() => { setMessage({ type: "", text: "" }); setShowInfoModal(true); }}
                style={{ flex: 1, minWidth: '130px', padding: '12px 20px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '18px', fontWeight: 'bold', cursor: 'pointer', transition: 'opacity 0.15s' }}
              >
                修改个人资料
              </button>
              <button 
                onClick={() => { setMessage({ type: "", text: "" }); setShowPasswordModal(true); }}
                style={{ flex: 1, minWidth: '130px', padding: '12px 20px', background: '#475569', color: '#fff', border: 'none', borderRadius: '18px', fontWeight: 'bold', cursor: 'pointer', transition: 'opacity 0.15s' }}
              >
                修改密码
              </button>
              <button 
                onClick={() => { setMessage({ type: "", text: "" }); setShowVipModal(true); }}
                style={{ flex: 1, minWidth: '130px', padding: '12px 20px', background: 'linear-gradient(135deg, #d97706 0%, #fbbf24 100%)', color: '#0a2b4e', border: 'none', borderRadius: '18px', fontWeight: 'bold', cursor: 'pointer', transition: 'opacity 0.15s' }}
              >
                👑 模拟VIP续费
              </button>
              <button 
                onClick={handleLogout}
                style={{ flex: 1, minWidth: '130px', padding: '12px 20px', background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5', borderRadius: '18px', fontWeight: 'bold', cursor: 'pointer', transition: 'opacity 0.15s' }}
              >
                退出登录
              </button>
            </div>

          </div>

          {/* Info Edit Modal */}
          {showInfoModal && (
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
              <div style={{ background: '#fff', width: '90%', maxWidth: '460px', borderRadius: '24px', padding: '28px', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0a2b4e', marginBottom: '20px' }}>修改资料</h3>
                <form onSubmit={handleUpdateInfo} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>显示昵称</label>
                    <input 
                      type="text" 
                      value={editNickname}
                      onChange={e => setEditNickname(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                      required
                    />
                  </div>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>绑定邮箱 (选填)</label>
                    <input 
                      type="email" 
                      placeholder="example@domain.com"
                      value={editEmail}
                      onChange={e => setEditEmail(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                    />
                  </div>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>绑定手机号 (选填)</label>
                    <input 
                      type="text" 
                      placeholder="请输入手机号"
                      value={editPhone}
                      onChange={e => setEditPhone(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
                    <button type="button" onClick={() => setShowInfoModal(false)} style={{ flex: 1, padding: '10px', background: '#e2e8f0', color: '#1e293b', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>取消</button>
                    <button type="submit" disabled={loading} style={{ flex: 1, padding: '10px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>
                      {loading ? "保存中..." : "保存修改"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Password Change Modal */}
          {showPasswordModal && (
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
              <div style={{ background: '#fff', width: '90%', maxWidth: '460px', borderRadius: '24px', padding: '28px', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0a2b4e', marginBottom: '20px' }}>修改账户密码</h3>
                <form onSubmit={handleUpdatePassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>当前密码</label>
                    <input 
                      type="password" 
                      placeholder="请输入原密码进行身份验证"
                      value={oldPassword}
                      onChange={e => setOldPassword(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                      required
                    />
                  </div>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>新密码</label>
                    <input 
                      type="password" 
                      placeholder="长度至少为 6 位"
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                      required
                    />
                  </div>
                  <div className="field">
                    <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#1e293b' }}>确认新密码</label>
                    <input 
                      type="password" 
                      placeholder="再次输入新密码"
                      value={confirmNewPassword}
                      onChange={e => setConfirmNewPassword(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: '12px', border: '1px solid #cbd5e1', outline: 'none' }}
                      required
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
                    <button type="button" onClick={() => setShowPasswordModal(false)} style={{ flex: 1, padding: '10px', background: '#e2e8f0', color: '#1e293b', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>取消</button>
                    <button type="submit" disabled={loading} style={{ flex: 1, padding: '10px', background: '#0a2b4e', color: '#fff', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>
                      {loading ? "修改中..." : "确认修改"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* VIP Renew Modal */}
          {showVipModal && (
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
              <div style={{ background: '#fff', width: '90%', maxWidth: '460px', borderRadius: '24px', padding: '28px', boxShadow: '0 10px 25px rgba(0,0,0,0.1)' }}>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0a2b4e', marginBottom: '20px' }}>VIP 续费模拟</h3>
                
                {/* Select VIP Plan */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
                  <div 
                    onClick={() => setSelectedPlan("basic")}
                    style={{ 
                      border: '2px solid',
                      borderColor: selectedPlan === "basic" ? "#d97706" : "#e2e8f0",
                      backgroundColor: selectedPlan === "basic" ? "#fffbeb" : "#fff",
                      borderRadius: '16px',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'all 0.15s'
                    }}
                  >
                    <h4 style={{ fontWeight: 'bold', color: '#0a2b4e', margin: '0 0 4px' }}>📊 海量数据库订阅</h4>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>解锁全球及国内政治经济历史数据</p>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#d97706', marginTop: '8px' }}>¥4.9 / 月</div>
                  </div>
                  <div 
                    onClick={() => setSelectedPlan("full")}
                    style={{ 
                      border: '2px solid',
                      borderColor: selectedPlan === "full" ? "#d97706" : "#e2e8f0",
                      backgroundColor: selectedPlan === "full" ? "#fffbeb" : "#fff",
                      borderRadius: '16px',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'all 0.15s'
                    }}
                  >
                    <h4 style={{ fontWeight: 'bold', color: '#0a2b4e', margin: '0 0 4px' }}>🚀 数据库 + 政经小助手 AI</h4>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>海量数据检索 + AI智能问答助手组合</p>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#d97706', marginTop: '8px' }}>¥6.9 / 月</div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button type="button" onClick={() => setShowVipModal(false)} style={{ flex: 1, padding: '10px', background: '#e2e8f0', color: '#1e293b', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>取消</button>
                  <button type="button" onClick={handleRenewVip} disabled={loading} style={{ flex: 1, padding: '10px', background: 'linear-gradient(135deg, #d97706 0%, #fbbf24 100%)', color: '#0a2b4e', border: 'none', borderRadius: '14px', fontWeight: 'bold', cursor: 'pointer' }}>
                    {loading ? "续费中..." : "模拟在线支付"}
                  </button>
                </div>
              </div>
            </div>
          )}

        </section>
      </div>
    </main>
  );
}
