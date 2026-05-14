"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchWithAuth, getToken, getUser } from "../../../lib/auth";
import SidebarNav from "../../../components/SidebarNav";
import AppHeader from "../../../components/AppHeader";
import "../../globals.css";

export default function UserManagementPage() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    const user = getUser();
    if (!token) {
      router.push("/login");
    } else if (user?.role !== 'admin') {
      router.push("/");
    } else {
      setIsAuthChecking(false);
    }
  }, [router]);

  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [nicknameFilter, setNicknameFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("全部");
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    username: "",
    password: "",
    nickname: "",
    role: "user",
    phone: "",
    email: ""
  });

  const loadUsers = async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        page,
        page_size: pageSize,
        nickname: nicknameFilter,
        role: roleFilter
      }).toString();
      const res = await fetchWithAuth(`/api/v1/admin/users/?${query}`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data.items);
        setTotal(data.total);
      }
    } catch (e) {
      console.error("Failed to load users", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [page]);

  const handleSearch = () => {
    setPage(1);
    loadUsers();
  };

  const handleReset = () => {
    setNicknameFilter("");
    setRoleFilter("全部");
    setPage(1);
    if (page === 1) loadUsers();
  };

  const openAddModal = () => {
    setEditingUser(null);
    setFormData({
      username: "",
      password: "",
      nickname: "",
      role: "user",
      phone: "",
      email: ""
    });
    setShowModal(true);
  };

  const openEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      password: "",
      nickname: user.nickname,
      role: user.role,
      phone: user.phone || "",
      email: user.email || ""
    });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    const url = editingUser ? `/api/v1/admin/users/${editingUser.id}` : "/api/v1/admin/users/";
    const method = editingUser ? "PUT" : "POST";
    
    // Convert empty strings to null for optional fields
    const payload = { ...formData };
    if (!payload.phone) payload.phone = null;
    if (!payload.email) payload.email = null;
    
    try {
      const res = await fetchWithAuth(url, {
        method,
        body: payload
      });
      if (res.ok) {
        setShowModal(false);
        loadUsers();
      } else {
        const err = await res.json();
        const msg = typeof err.detail === 'string' ? err.detail : 
                    (Array.isArray(err.detail) ? err.detail.map(d => d.msg).join(', ') : JSON.stringify(err.detail));
        alert(msg || "保存失败");
      }
    } catch (e) {
      console.error("Failed to save user", e);
    }
  };

  const toggleStatus = async (user) => {
    try {
      const res = await fetchWithAuth(`/api/v1/admin/users/${user.id}/toggle`, { method: "PUT" });
      if (res.ok) {
        loadUsers();
      }
    } catch (e) {
      console.error("Failed to toggle user status", e);
    }
  };

  const roleMap = {
    "admin": "管理员",
    "user": "普通用户"
  };

  if (isAuthChecking) {
    return <div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>;
  }

  return (
    <main className="shell">
      <AppHeader title="系统配置" subtitle="用户管理" />
      
      <div className="main-grid">
        <SidebarNav />
        
        <section className="content-stack">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div style={{ fontSize: '14px', color: '#64748b' }}>
              系统配置 / <span style={{ color: '#1e293b', fontWeight: 'bold' }}>用户管理</span>
            </div>
            <button className="secondary" style={{ minHeight: '40px', borderRadius: '12px', background: '#008080' }} onClick={openAddModal}>
              + 添加用户
            </button>
          </div>

          <div className="search-toolbar" style={{ background: '#f8fafc', padding: '20px', borderRadius: '16px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end' }}>
              <div className="field">
                <label>姓名</label>
                <input 
                  type="text" 
                  placeholder="输入姓名" 
                  value={nicknameFilter}
                  onChange={e => setNicknameFilter(e.target.value)}
                  style={{ minHeight: '40px', width: '200px' }}
                />
              </div>
              <div className="field">
                <label>角色</label>
                <select 
                  value={roleFilter} 
                  onChange={e => setRoleFilter(e.target.value)}
                  style={{ minHeight: '40px', width: '160px' }}
                >
                  <option value="全部">全部</option>
                  <option value="admin">管理员</option>
                  <option value="user">普通用户</option>
                </select>
              </div>
              <button className="secondary" style={{ minHeight: '40px', background: '#008080', color: '#fff' }} onClick={handleSearch}>查询</button>
              <button className="secondary" style={{ minHeight: '40px' }} onClick={handleReset}>重置</button>
            </div>
          </div>

          <div className="table-wrap" style={{ flex: 1 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '60px' }}>序号</th>
                  <th>姓名</th>
                  <th>账号</th>
                  <th>角色</th>
                  <th>状态</th>
                  <th>最后登录</th>
                  <th>手机号</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user, index) => (
                  <tr key={user.id}>
                    <td>{(page - 1) * pageSize + index + 1}</td>
                    <td>{user.nickname}</td>
                    <td>{user.username}</td>
                    <td>{roleMap[user.role] || user.role}</td>
                    <td>
                      <span style={{ 
                        color: user.is_active ? '#10b981' : '#ef4444',
                        background: user.is_active ? '#ecfdf5' : '#fef2f2',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 'bold'
                      }}>
                        {user.is_active ? '启用' : '禁用'}
                      </span>
                    </td>
                    <td>{user.last_login_at || '-'}</td>
                    <td>{user.phone || '-'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '12px' }}>
                        <button style={{ background: 'none', border: 'none', color: '#008080', cursor: 'pointer', padding: 0 }} onClick={() => openEditModal(user)}>编辑</button>
                        <span style={{ color: '#e2e8f0' }}>|</span>
                        <button style={{ background: 'none', border: 'none', color: user.is_active ? '#ef4444' : '#10b981', cursor: 'pointer', padding: 0 }} onClick={() => toggleStatus(user)}>
                          {user.is_active ? '禁用' : '启用'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px' }}>
            <div style={{ fontSize: '14px', color: '#64748b' }}>共 {total} 条记录</div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="secondary compact-button" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
              <span style={{ padding: '0 12px', display: 'flex', alignItems: 'center', fontSize: '14px' }}>第 {page} 页 / 共 {Math.ceil(total / pageSize)} 页</span>
              <button className="secondary compact-button" disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          </div>
        </section>
      </div>

      {showModal && (
        <div style={{ 
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
          background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 
        }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '500px', overflow: 'hidden' }}>
            <div style={{ padding: '16px 24px', background: '#008080', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>{editingUser ? `编辑用户 - ${editingUser.nickname}` : "添加用户"}</h3>
              <button style={{ background: 'none', border: 'none', color: '#fff', fontSize: '24px', cursor: 'pointer' }} onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <form onSubmit={handleSave} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>姓名：</label>
                <input 
                  type="text" 
                  required
                  value={formData.nickname}
                  onChange={e => setFormData({...formData, nickname: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>账号：</label>
                <input 
                  type="text" 
                  required
                  disabled={!!editingUser}
                  value={formData.username}
                  onChange={e => setFormData({...formData, username: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px', background: editingUser ? '#f8fafc' : '#fff' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>密码：</label>
                <input 
                  type="password" 
                  required={!editingUser}
                  placeholder={editingUser ? "留空则不修改密码" : "请输入密码"}
                  value={formData.password}
                  onChange={e => setFormData({...formData, password: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>手机号：</label>
                <input 
                  type="text" 
                  value={formData.phone}
                  onChange={e => setFormData({...formData, phone: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>邮箱：</label>
                <input 
                  type="email" 
                  value={formData.email}
                  onChange={e => setFormData({...formData, email: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <label style={{ width: '60px', textAlign: 'right', fontSize: '14px' }}>角色：</label>
                <select 
                  value={formData.role}
                  onChange={e => setFormData({...formData, role: e.target.value})}
                  style={{ flex: 1, minHeight: '40px', borderRadius: '8px', border: '1px solid #e2e8f0', padding: '0 12px' }}
                >
                  <option value="user">普通用户</option>
                  <option value="admin">管理员</option>
                </select>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
                <button type="button" className="secondary" onClick={() => setShowModal(false)} style={{ minHeight: '40px' }}>取消</button>
                <button type="submit" className="secondary" style={{ minHeight: '40px', background: '#008080', color: '#fff' }}>保存</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
