import { useEffect, useState } from "react";
import { formatDate } from "../lib/formatters";

export default function TaskSchedulesPanel({ adminToken, adminActor }) {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editCron, setEditCron] = useState("");

  async function parseErrorResponse(res, fallback) {
    try {
      const payload = await res.json();
      return payload?.detail ? `${fallback}: ${payload.detail}` : fallback;
    } catch {
      return fallback;
    }
  }

  async function loadSchedules() {
    setLoading(true);
    setError(null);

    try {
      if (!adminToken) {
        throw new Error("请先在右上角 Token 设置中填写 Admin API Token");
      }

      const res = await fetch("/api/v1/pipeline/schedules", {
        headers: {
          "x-admin-token": adminToken
        }
      });

      if (!res.ok) {
        const message =
          res.status === 401
            ? "Admin API Token 无效或未填写"
            : `加载定时任务失败 (${res.status})`;
        throw new Error(await parseErrorResponse(res, message));
      }

      const data = await res.json();
      setSchedules(data.items || []);
    } catch (err) {
      setError(err.message || "加载定时任务失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSchedules();
  }, [adminToken]);

  async function toggleSchedule(id, isEnabled) {
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
      if (!res.ok) {
        throw new Error(await parseErrorResponse(res, "切换定时任务状态失败"));
      }
      await loadSchedules();
    } catch (err) {
      alert(err.message || "切换定时任务状态失败");
    }
  }

  async function updateSchedule(id) {
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
        throw new Error(await parseErrorResponse(res, "更新定时规则失败"));
      }
      setEditingId(null);
      await loadSchedules();
    } catch (err) {
      alert(err.message || "更新定时规则失败");
    }
  }

  async function triggerSchedule(id, name) {
    if (!window.confirm(`确定要立即执行一次“${name}”吗？`)) return;

    try {
      const res = await fetch(`/api/v1/pipeline/schedules/${id}/trigger`, {
        method: "POST",
        headers: {
          "x-admin-token": adminToken || "",
          "x-admin-actor": adminActor || ""
        }
      });
      if (!res.ok) {
        throw new Error(await parseErrorResponse(res, "触发定时任务失败"));
      }
      const data = await res.json();
      alert(`任务已提交，Task ID: ${data.task_id}`);
      await loadSchedules();
    } catch (err) {
      alert(err.message || "触发定时任务失败");
    }
  }

  function startEditing(schedule) {
    setEditingId(schedule.id);
    setEditCron(schedule.cron_expr);
  }

  const presets = [
    { label: "每分钟", value: "* * * * *" },
    { label: "每 5 分钟", value: "*/5 * * * *" },
    { label: "每 30 分钟", value: "*/30 * * * *" },
    { label: "每小时", value: "0 * * * *" },
    { label: "每天凌晨 2 点", value: "0 2 * * *" }
  ];

  if (loading) return <div className="muted">正在加载定时任务...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="task-schedules-panel" style={{ marginTop: 16 }}>
      <p className="muted" style={{ marginBottom: 24 }}>
        配置数据库驱动的 Celery 定时任务，可在不重启服务的情况下更新调度规则。
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {schedules.map((schedule) => (
          <div
            key={schedule.id}
            style={{
              border: "1px solid #cbd5e1",
              borderRadius: 14,
              padding: 24,
              background: "#fff",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 16,
              boxShadow: "0 2px 8px rgba(0,0,0,0.02)"
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
                <h3 style={{ margin: 0, fontSize: 17, color: "var(--navy)", fontWeight: 800 }}>
                  {schedule.name}
                </h3>
                <span
                  className={`state-pill ${schedule.is_enabled ? "state-success" : "state-error"}`}
                  style={{ padding: "3px 10px", fontSize: 11, fontWeight: 700 }}
                >
                  {schedule.is_enabled ? "运行中" : "已暂停"}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
                <span className="muted" style={{ fontSize: 12, fontWeight: 600 }}>
                  Cron 规则:
                </span>
                {editingId === schedule.id ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <input
                      type="text"
                      value={editCron}
                      onChange={(event) => setEditCron(event.target.value)}
                      style={{
                        padding: "6px 12px",
                        border: "1px solid var(--primary)",
                        borderRadius: 6,
                        width: 140,
                        fontSize: 14,
                        fontWeight: 700
                      }}
                    />
                    <select
                      onChange={(event) => setEditCron(event.target.value)}
                      style={{ padding: "6px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }}
                      value=""
                    >
                      <option value="" disabled>
                        快速预设...
                      </option>
                      {presets.map((preset) => (
                        <option key={preset.value} value={preset.value}>
                          {preset.label}
                        </option>
                      ))}
                    </select>
                    <button className="secondary" style={{ minHeight: 32, padding: "0 12px", fontSize: 12 }} onClick={() => updateSchedule(schedule.id)}>
                      保存
                    </button>
                    <button className="secondary" style={{ minHeight: 32, padding: "0 12px", fontSize: 12 }} onClick={() => setEditingId(null)}>
                      取消
                    </button>
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <code
                      style={{
                        fontSize: 16,
                        color: "var(--primary)",
                        fontWeight: 800,
                        background: "var(--primary-soft)",
                        padding: "2px 8px",
                        borderRadius: 5
                      }}
                    >
                      {schedule.cron_expr}
                    </code>
                    <button className="text-button" style={{ border: "none", background: "none", color: "var(--primary)", cursor: "pointer", fontSize: 12, fontWeight: 700 }} onClick={() => startEditing(schedule)}>
                      修改规则
                    </button>
                  </div>
                )}
              </div>

              <div style={{ marginTop: 16 }}>
                <span className="muted" style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>
                  执行目标:
                </span>
                <code style={{ fontSize: 12, color: "#475569", background: "#f8fafc", padding: "4px 8px", borderRadius: 4, border: "1px solid #e2e8f0" }}>
                  {schedule.task_path}
                </code>
              </div>
            </div>

            <div style={{ textAlign: "right", minWidth: 150 }}>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700 }}>
                上次执行
              </div>
              <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>
                {schedule.last_run_at ? formatDate(schedule.last_run_at) : "尚未触发"}
              </div>
              <div className="muted" style={{ fontSize: 11, fontWeight: 700, marginTop: 8 }}>
                下次执行
              </div>
              <div style={{ fontSize: 13, color: "var(--primary)", fontWeight: 700 }}>
                {schedule.next_run_at ? formatDate(schedule.next_run_at) : schedule.is_enabled ? "计算中..." : "已暂停"}
              </div>
              <div className="muted" style={{ fontSize: 10, marginTop: 6 }}>
                累计运行: <strong>{schedule.total_run_count || 0}</strong> 次
              </div>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button className="secondary" style={{ minHeight: 34, padding: "0 12px", fontSize: 12 }} onClick={() => triggerSchedule(schedule.id, schedule.name)}>
                立即触发一次
              </button>
              <button
                onClick={() => toggleSchedule(schedule.id, !schedule.is_enabled)}
                style={{
                  background: schedule.is_enabled ? "#fff" : "var(--primary)",
                  color: schedule.is_enabled ? "var(--danger)" : "#fff",
                  border: schedule.is_enabled ? "1px solid var(--danger)" : "none",
                  borderRadius: 8,
                  padding: "8px 16px",
                  fontSize: 13,
                  cursor: "pointer",
                  fontWeight: 800
                }}
              >
                {schedule.is_enabled ? "暂停" : "启用"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
