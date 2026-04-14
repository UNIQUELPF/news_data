import { useState, useMemo } from "react";
import { formatDate, stateClass, summarizeCrawlResult, summarizeTaskResult } from "../lib/formatters";

function formatTaskNameFriendly(taskName) {
  const shortName = (taskName || "").split('.').pop();
  if (shortName === "run_end_to_end_pipeline") return "🕷️ 全球收割组 (End-to-End Crawler)";
  if (shortName === "run_translation_embedding_backfill") return "🔄 历史回填组 (Backfill)";
  if (shortName === "auto_translate_articles") return "⚙️ 后台自动翻译 (Auto Translate)";
  if (shortName === "auto_embed_articles") return "⚙️ 后台自动向量 (Auto Embed)";
  if (shortName === "run_all_spiders_automatic") return "🕷️ 全量自动爬虫巡航 (Crawler Auto-Run)";
  if (shortName === "manual_ingest_from_spiders") return "🚀 手动触发抓取 (Manual Ingest)";
  return `📦 ${shortName}`;
}

export default function TaskHistoryList({
  activeTaskId,
  highlightTaskId,
  taskDetails,
  tasks,
  onActiveTaskChange,
  onBatchCancelTasks,
  onBatchRetryTasks,
  onCancelTask,
  onRetryTask
}) {
  const [expandedGroups, setExpandedGroups] = useState({});

  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  // Group top-level tasks. A 'root' is either parentless OR a core business task flagged by backend.
  const groupedTasks = useMemo(() => {
    const groups = {};
    // A task is a root if it has no parent OR if the backend specifically flagged it as a business root (is_business_child)
    // We also exclude the pure scheduler task from appearing as a main group to keep the UI clean.
    const rootTasks = tasks.filter(t => (!t.parent_task_id || t.is_business_child) && t.task_name !== 'pipeline.tasks.orchestrate.dispatch_periodic_tasks');
    
    rootTasks.forEach(task => {
      const gName = task.task_name || "unknown_task";
      if (!groups[gName]) groups[gName] = [];
      groups[gName].push(task);
    });
    return groups;
  }, [tasks]);

  const childDict = useMemo(() => {
    const dict = {};
    tasks.forEach(t => {
      if (t.parent_task_id) {
          if (!dict[t.parent_task_id]) dict[t.parent_task_id] = [];
          dict[t.parent_task_id].push(t);
      }
    });
    return dict;
  }, [tasks]);

  const renderTaskRow = (task, depth = 0) => {
    const children = childDict[task.task_id] || [];
    const hasChildren = children.length > 0;
    const isExpanded = activeTaskId === task.task_id;
    const detail = taskDetails[task.task_id];
    const effectiveTask = detail ? { ...task, ...detail, error_message: detail.error || task.error_message } : task;
    const canCancel = effectiveTask.actions?.can_cancel ?? ["PENDING", "STARTED", "RETRY"].includes(String(effectiveTask.state || "").toUpperCase());
    const canRetry = effectiveTask.actions?.can_retry ?? (!canCancel && String(effectiveTask.state || "").toUpperCase() !== "SUCCESS");

    return (
      <div key={task.task_id} style={{ marginBottom: "8px", borderLeft: depth > 0 ? "2px solid #e2e8f0" : "none", paddingLeft: depth > 0 ? "16px" : "0" }}>
        <div className={`task-history-card ${isExpanded ? "expanded" : ""} ${highlightTaskId === task.task_id ? "highlighted" : ""}`} style={{ width: "100%", padding: "10px 14px", border: "1px solid #e2e8f0", borderRadius: "10px", background: "#fff" }}>
          <div className="panel-head" style={{ marginBottom: isExpanded ? "12px" : "0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className="muted" style={{ fontSize: "12px" }}>{depth > 0 ? "∟" : "•"}</span>
              <div>
                <button className="title-link" onClick={() => onActiveTaskChange(isExpanded ? null : task.task_id)} style={{ fontSize: depth > 0 ? "13px" : "14px" }}>
                  {depth === 0 ? `Execution: ${effectiveTask.task_id.split('-')[0]}` : effectiveTask.task_name.split('.').pop()}
                </button>
                <div className="task-meta" style={{ marginTop: "2px", fontSize: "12px" }}>
                  {depth > 0 && <><span style={{ color: "var(--primary)" }}>{effectiveTask.task_id.split('-')[0]}</span><span style={{ margin: "0 6px" }}>|</span></>}
                  <span>{formatDate(effectiveTask.created_at)}</span>
                  {depth === 0 && effectiveTask.requested_by && <><span style={{ margin: "0 6px" }}>|</span><span>操作人: {effectiveTask.requested_by}</span></>}
                </div>
              </div>
            </div>
            <span className={stateClass(effectiveTask.state)} style={{ transform: "scale(0.85)", transformOrigin: "right center" }}>{effectiveTask.state}</span>
          </div>

          {isExpanded && (
            <div className="task-detail" style={{ background: "rgba(255,255,255,0.5)", padding: "12px", borderRadius: "8px" }}>
              <pre style={{ fontSize: "11px", margin: "0 0 8px 0" }}>{JSON.stringify(effectiveTask.params || {}, null, 2)}</pre>
              {effectiveTask.error_message && <pre style={{ color: "#dc2626", fontSize: "11px", margin: "0 0 8px 0" }}>{effectiveTask.error_message}</pre>}
              <div className="inline-actions">
                {canRetry && <button className="secondary" style={{ padding: "4px 10px", fontSize: "12px", minHeight: "auto" }} onClick={() => onRetryTask(effectiveTask.task_id)}>重试</button>}
                {canCancel && <button className="danger" style={{ padding: "4px 10px", fontSize: "12px", minHeight: "auto" }} onClick={() => onCancelTask(effectiveTask.task_id)}>取消</button>}
              </div>
            </div>
          )}
        </div>

        {hasChildren && (
          <div style={{ marginTop: "4px" }}>
            {children.map(child => renderTaskRow(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const groupEntries = Object.entries(groupedTasks).sort((a, b) => b[1].length - a[1].length);

  return (
    <div style={{ marginTop: 14 }} className="task-history-list">
      <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: "16px" }}>
        {groupEntries.map(([taskName, groupTasks]) => {
          const isExpanded = expandedGroups[taskName];
          let cancellableIds = [];
          let retryableIds = [];
          let activeCount = 0;
          
          const traverse = (pTasks) => {
            pTasks.forEach(t => {
              const state = String(t.state || "").toUpperCase();
              if (["PENDING", "STARTED", "RETRY"].includes(state)) {
                cancellableIds.push(t.task_id);
                activeCount++;
              }
              if (["FAILURE", "ERROR"].includes(state) && ["backfill", "pipeline_run"].includes(t.task_type)) {
                retryableIds.push(t.task_id);
              }
              if (childDict[t.task_id]) {
                traverse(childDict[t.task_id]);
              }
            });
          };
          traverse(groupTasks);
          
          return (
            <div key={taskName} style={{ border: "1px solid #cbd5e1", borderRadius: "12px", overflow: "hidden", background: "#f8fafc" }}>
              <div 
                onClick={() => toggleGroup(taskName)}
                style={{ padding: "12px 16px", background: "#f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", borderBottom: isExpanded ? "1px solid #cbd5e1" : "none" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <strong style={{ fontSize: "15px", color: "var(--navy)" }}>{formatTaskNameFriendly(taskName)}</strong>
                  <span className="muted" style={{ fontSize: "13px" }}>({groupTasks.length} 次执行)</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <div className="inline-actions" onClick={e => e.stopPropagation()}>
                    {cancellableIds.length > 0 && (
                      <button className="danger compact-button" style={{ padding: "2px 8px", fontSize: "11px", minHeight: "auto" }} onClick={() => onBatchCancelTasks(cancellableIds)}>
                        全部取消 ({cancellableIds.length})
                      </button>
                    )}
                    {retryableIds.length > 0 && (
                      <button className="secondary compact-button" style={{ padding: "2px 8px", fontSize: "11px", minHeight: "auto" }} onClick={() => onBatchRetryTasks(retryableIds)}>
                        全部重试 ({retryableIds.length})
                      </button>
                    )}
                  </div>
                  {activeCount > 0 && <span className="state-pill state-active" style={{ fontSize: "11px", padding: "2px 8px" }}>{activeCount} 运行中</span>}
                  <span style={{ color: "var(--muted)", transform: isExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>▼</span>
                </div>
              </div>

              {isExpanded && (
                <div style={{ padding: "16px", maxHeight: "600px", overflowY: "auto" }}>
                  {groupTasks.map(task => renderTaskRow(task, 0))}
                </div>
              )}
            </div>
          );
        })}
        {tasks.length === 0 && <div className="empty">暂无任务记录</div>}
      </div>
    </div>
  );
}
