import { useState, useEffect } from "react";
import { formatDate } from "../lib/formatters";

export default function TaskSchedulesPanel({ adminToken, adminActor }) {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editCron, setEditCron] = useState("");

  const loadSchedules = async () => {
    try {
      const res = await fetch("/api/v1/pipeline/schedules", {
        headers: {
          "x-admin-token": adminToken || ""
        }
      });
      if (!res.ok) throw new Error("加载定时任务失败");
      const data = await res.json();
      setSchedules(data.items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSchedules();
  }, [adminToken]);

  const toggleSchedule = async (id, isEnabled) => {
    try {
      const res = await fetch(`/api/v1/pipeline/schedules/${id}/toggle`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-token": adminToken || "",
          "x-admin-actor": adminActor || ""
        },
        body: JSON.stringify({ is_enabled: isEnabled })
      });
      if (!res.ok) throw new Error("切换状态失败");
      loadSchedules();
    } catch (e) {
      alert(e.message);
    }
  };

  const updateSchedule = async (id) => {
    try {
      const res = await fetch(`/api/v1/pipeline/schedules/${id}/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-token": adminToken || "",
          "x-admin-actor": adminActor || ""
        },
        body: JSON.stringify({ cron_expr: editCron })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "更新失败");
      }
      setEditingId(null);
      loadSchedules();
    } catch (e) {
      alert(e.message);
    }
  };

  const triggerSchedule = async (id, name) => {
    if (!confirm(`确定要立刻执行一次 "${name}" 吗？`)) return;
    try {
      const res = await fetch(`/api/v1/pipeline/schedules/${id}/trigger`, {
        method: "POST",
        headers: {
          "x-admin-token": adminToken || "",
          "x-admin-actor": adminActor || ""
        }
      });
      if (!res.ok) throw new Error("触发失败");
      const data = await res.json();
      alert(`任务已提交，Task ID: ${data.task_id}`);
      loadSchedules();
    } catch (e) {
      alert(e.message);
    }
  };

  const startEditing = (sch) => {
    setEditingId(sch.id);
    setEditCron(sch.cron_expr);
  };

  const presets = [
    { label: "每分钟", value: "* * * * *" },
    { label: "每5分钟", value: "*/5 * * * *" },
    { label: "每30分钟", value: "*/30 * * * *" },
    { label: "每小时", value: "0 * * * *" },
    { label: "每天凌晨2点", value: "0 2 * * *" }
  ];

  if (loading) return <div>加载中...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="task-schedules-panel" style={{ marginTop: 16 }}>
      <p className="muted" style={{ marginBottom: 24 }}>配置数据库驱动的 Celery 自动化调度，可直接在不重启服务的情况下热更新定时规则。</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {schedules.map(sch => (
          <div key={sch.id} style={{ border: "1px solid #cbd5e1", borderRadius: "14px", padding: "24px", background: "#fff", display: "flex", justifyContent: "space-between", alignItems: "flex-start", boxShadow: "0 2px 8px rgba(0,0,0,0.02)" }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "4px" }}>
                <h3 style={{ margin: 0, fontSize: "17px", color: "var(--navy)", fontWeight: "800" }}>{sch.name}</h3>
                <span className={`state-pill ${sch.is_enabled ? 'state-success' : 'state-error'}`} style={{ padding: "3px 10px", fontSize: "11px", fontWeight: "700" }}>
                  {sch.is_enabled ? 'Active 运行中' : 'Paused 已暂停'}
                </span>
              </div>
              
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "12px" }}>
                <span className="muted" style={{ fontSize: "12px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px" }}>Cron Pattern:</span>
                {editingId === sch.id ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <input 
                      type="text" 
                      value={editCron} 
                      onChange={e => setEditCron(e.target.value)} 
                      style={{ padding: "6px 12px", border: "1px solid var(--primary)", borderRadius: "6px", width: "140px", fontSize: "14px", fontWeight: "700" }}
                    />
                    <select 
                      onChange={e => setEditCron(e.target.value)}
                      style={{ padding: "6px 12px", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "13px" }}
                      value=""
                    >
                      <option value="" disabled>快速预设...</option>
                      {presets.map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                    <button className="secondary" style={{ minHeight: "32px", padding: "0 12px", fontSize: "12px" }} onClick={() => updateSchedule(sch.id)}>保存</button>
                    <button style={{ minHeight: "32px", border: "none", background: "#f1f5f9", color: "#64748b", padding: "0 12px", fontSize: "12px", borderRadius: "6px", cursor: "pointer" }} onClick={() => setEditingId(null)}>取消</button>
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <code style={{ fontSize: "16px", color: "var(--primary)", fontWeight: "800", background: "var(--primary-soft)", padding: "2px 8px", borderRadius: "5px" }}>{sch.cron_expr}</code>
                    <button className="text-button" style={{ border: "none", background: "none", color: "var(--primary)", cursor: "pointer", fontSize: "12px", fontWeight: "700", opacity: 0.8 }} onClick={() => startEditing(sch)}>
                      [ 更改规则 ]
                    </button>
                  </div>
                )}
              </div>

              <div style={{ marginTop: "16px" }}>
                <span className="muted" style={{ fontSize: "12px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px", display: "block", marginBottom: "4px" }}>Execution Target:</span>
                <code style={{ fontSize: "12px", color: "#475569", background: "#f8fafc", padding: "4px 8px", borderRadius: "4px", border: "1px solid #e2e8f0" }}>{sch.task_path}</code>
              </div>
            </div>

                 <div style={{ textAlign: "right" }}>
                    <div className="muted" style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase" }}>Last Dispatched</div>
                    <div style={{ fontSize: "13px", color: "var(--text)", fontWeight: "600" }}>{sch.last_run_at ? formatDate(sch.last_run_at) : 'Never triggered'}</div>
                    <div className="muted" style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", marginTop: "8px" }}>Next Execution</div>
                    <div style={{ fontSize: "13px", color: "var(--primary)", fontWeight: "700" }}>{sch.next_run_at ? formatDate(sch.next_run_at) : (sch.is_enabled ? 'Calculating...' : 'Paused')}</div>
                    <div className="muted" style={{ fontSize: "10px", marginTop: "6px" }}>累计运行: <strong>{sch.total_run_count || 0}</strong> 次</div>
                 </div>
                 
                 <div style={{ display: "flex", gap: "8px" }}>
                    <button 
                      onClick={() => triggerSchedule(sch.id, sch.name)}
                      style={{ 
                        background: "#f0fdf4", 
                        color: "#166534", 
                        border: "1px solid #bbf7d0", 
                        borderRadius: "8px", 
                        padding: "8px 12px", 
                        fontSize: "12px", 
                        cursor: "pointer", 
                        fontWeight: "700",
                        transition: "all 0.2s"
                      }}
                      title="跳过 Cron 计划，立即在后台启动该任务"
                    >
                      ⚡ 立刻触发一次
                    </button>
                    <button 
                      onClick={() => toggleSchedule(sch.id, !sch.is_enabled)}
                      style={{ 
                        background: sch.is_enabled ? "#fff" : "var(--primary)", 
                        color: sch.is_enabled ? "var(--danger)" : "#fff", 
                        border: sch.is_enabled ? "1px solid var(--danger)" : "none", 
                        borderRadius: "8px", 
                        padding: "8px 16px", 
                        fontSize: "13px", 
                        cursor: "pointer", 
                        fontWeight: "800",
                        transition: "all 0.2s"
                      }}
                    >
                      {sch.is_enabled ? 'STOP' : 'ACTIVATE'}
                    </button>
                 </div>
          </div>
        ))}
      </div>
    </div>
  );
}
