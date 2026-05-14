"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getUser, clearAuth } from "../lib/auth";

export default function AppHeader({
  title = "全球政治经济数据库",
  subtitle = "搜索、筛选和文章详情的正式入口。任务调度与监控已迁移到 /admin。",
}) {
  const [user, setUser] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);
  const router = useRouter();

  useEffect(() => {
    setUser(getUser());
    
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    clearAuth();
    router.push("/login");
  };

  return (
    <section className="topbar">
      <div className="brand">
        <div className="brand-mark">◎</div>
        <div>
          <div className="title">{title}</div>
        </div>
      </div>
      <div className="topbar-user" style={{ position: 'relative' }} ref={dropdownRef}>
        {user ? (
          <>
            <div 
              style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
              onClick={() => setShowDropdown(!showDropdown)}
            >
              <span>{user.nickname || user.username}</span>
              <span className="topbar-avatar">
                {(user.nickname || user.username || "?")[0].toUpperCase()}
              </span>
            </div>
            
            {showDropdown && (
              <div className="user-dropdown">
                <div style={{ padding: '10px 14px', borderBottom: '1px solid #f1f5f9', marginBottom: '4px' }}>
                   <div style={{ fontSize: '12px', color: '#64748b' }}>当前账号</div>
                   <div style={{ fontSize: '14px', color: '#18324b', fontWeight: 'bold', marginTop: '2px' }}>
                     {user.nickname || user.username}
                   </div>
                   <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                     角色: {user.role === 'admin' ? '管理员' : '普通用户'}
                   </div>
                </div>
                <div className="dropdown-logout" onClick={handleLogout}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                  </svg>
                  <span>退出登录</span>
                </div>
              </div>
            )}
          </>
        ) : (
          <span style={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={() => router.push("/login")}>
            登录
          </span>
        )}
      </div>
    </section>
  );
}
