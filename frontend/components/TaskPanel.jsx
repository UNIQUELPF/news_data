import { useState } from "react";
import { formatDate, stateClass } from "../lib/formatters";
import ActiveTaskCard from "./ActiveTaskCard";
import TaskHistoryList from "./TaskHistoryList";
import TaskPanelForm from "./TaskPanelForm";
import TaskSchedulesPanel from "./TaskSchedulesPanel";

export default function TaskPanel({
  adminActor,
  adminToken,
  activeTask,
  activeTaskId,
  autoRefresh,
  backfillForm,
  highlightTaskId,
  monitorSummary,
  panelError,
  runtimeStatus,
  showRunningOnly,
  taskMonitorSummary,
  taskDetails,
  taskLimit,
  taskSummary,
  tasks,
  onActiveTaskChange,
  onAdminActorBlur,
  onAdminActorChange,
  onAdminTokenBlur,
  onAdminTokenChange,
  onAutoRefreshChange,
  onBackfillFormChange,
  onBatchCancelTasks,
  onBatchRetryTasks,
  onCancelTask,
  onRetryTask,
  spiderPresets,
  onShowRunningOnlyChange,
  onIngest,
  onProcessGlobal,
  onProcessDomestic,
  onProcessEmbed,
  onTaskLimitToggle,
  onUseSpiderInPipeline,
  persistAdminActor,
  persistAdminToken,
  loadPanel,
  availableSpiders
}) {
  const [activeTab, setActiveTab] = useState("overview");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [toast, setToast] = useState(null); // { message, type: 'success' | 'error' }

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleTaskTrigger = async (triggerFn, taskName) => {
    try {
      await triggerFn();
      showToast(`${taskName} 任务已成功提交`, 'success');
      // 自动切换到日志选项卡，方便查看进度
      setActiveTab('logs');
    } catch (err) {
      showToast(`提交失败: ${err.message || '未知错误'}`, 'error');
    }
  };

  return (
    <div className="panel">
      <div className="panel-head" style={{ marginBottom: '16px' }}>
        <h2>流程任务与运行管理</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.85rem', color: '#64748b' }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => onAutoRefreshChange(e.target.checked)} />
            自动刷新 (10s)
          </label>
          <button 
            className="secondary compact-button" 
            onClick={() => setIsSettingsOpen(true)}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              padding: '4px 10px',
              borderColor: adminToken ? '#059669' : '#cbd5e1',
              color: adminToken ? '#059669' : '#64748b'
            }}
          >
            <span>{adminToken ? '🔒' : '🔓'} Token 设置</span>
          </button>
        </div>
      </div>

      {/* --- Toast Notification --- */}
      {toast && (
        <div className={`toast-container ${toast.type}`}>
          <span className="toast-icon">{toast.type === 'success' ? '✅' : '❌'}</span>
          <span className="toast-message">{toast.message}</span>
        </div>
      )}

      {/* --- Settings Modal --- */}
      {isSettingsOpen && (
        <div className="modal-overlay" onClick={() => setIsSettingsOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🔐 管理鉴权配置</h3>
              <button className="close-btn" onClick={() => setIsSettingsOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="field">
                <label>Admin API Token</label>
                <div style={{ position: 'relative' }}>
                  <input 
                    type={showToken ? "text" : "password"} 
                    value={adminToken} 
                    placeholder="输入有效的管理 Token..."
                    onChange={(e) => onAdminTokenChange(e.target.value)} 
                    onBlur={onAdminTokenBlur} 
                    style={{ paddingRight: '40px' }}
                  />
                  <button 
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    style={{
                      position: 'absolute',
                      right: '8px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      padding: '4px',
                      cursor: 'pointer',
                      fontSize: '1.1rem',
                      lineHeight: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title={showToken ? "隐藏 Token" : "显示 Token"}
                  >
                    {showToken ? '👁️' : '🕶️'}
                  </button>
                </div>
              </div>
              <div className="field" style={{ marginTop: '16px' }}>
                <label>操作人 (Actor)</label>
                <input 
                  value={adminActor} 
                  placeholder="输入操作人名字，用于审计..."
                  onChange={(e) => onAdminActorChange(e.target.value)} 
                  onBlur={onAdminActorBlur} 
                />
              </div>
              <p className="hint">
                * 凭据将存储在浏览器的 LocalStorage 中，仅用于当前站点的管理接口调用。
              </p>
            </div>
            <div className="modal-footer">
              <button className="primary" onClick={() => {
                persistAdminToken();
                persistAdminActor();
                setIsSettingsOpen(false);
                loadPanel(true);
              }}>确认</button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', borderBottom: '2px solid var(--border-color, #e2e8f0)', marginBottom: '24px' }}>
        <button 
          onClick={() => setActiveTab('overview')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'overview' ? '#1890ff' : 'transparent',
            color: activeTab === 'overview' ? 'white' : 'var(--text-color, #1e293b)',
            border: 'none',
            borderRadius: '6px 6px 0 0',
            fontWeight: activeTab === 'overview' ? 'bold' : 'normal',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
        >
          📊 运行总览
        </button>
        <button 
          onClick={() => setActiveTab('control')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'control' ? '#1890ff' : 'transparent',
            color: activeTab === 'control' ? 'white' : 'var(--text-color, #1e293b)',
            border: 'none',
            borderRadius: '6px 6px 0 0',
            fontWeight: activeTab === 'control' ? 'bold' : 'normal',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
        >
          ⚙️ 任务控制台
        </button>
        <button 
          onClick={() => setActiveTab('logs')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'logs' ? '#1890ff' : 'transparent',
            color: activeTab === 'logs' ? 'white' : 'var(--text-color, #1e293b)',
            border: 'none',
            borderRadius: '6px 6px 0 0',
            fontWeight: activeTab === 'logs' ? 'bold' : 'normal',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
        >
          📝 任务执行日志
        </button>
        <button 
          onClick={() => setActiveTab('schedules')}
          style={{ 
            padding: '12px 24px', 
            background: activeTab === 'schedules' ? '#1890ff' : 'transparent',
            color: activeTab === 'schedules' ? 'white' : 'var(--text-color, #1e293b)',
            border: 'none',
            borderRadius: '6px 6px 0 0',
            fontWeight: activeTab === 'schedules' ? 'bold' : 'normal',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
        >
          🕒 定时自动任务
        </button>
      </div>

      {activeTab === 'schedules' && (
        <div className="tab-pane fade-in">
          <TaskSchedulesPanel adminToken={adminToken} adminActor={adminActor} />
        </div>
      )}

      {activeTab === 'control' && (
        <div className="tab-pane fade-in">
          <TaskPanelForm
            adminActor={adminActor}
            adminToken={adminToken}
            autoRefresh={autoRefresh}
            backfillForm={backfillForm}
            currentTaskId={activeTaskId}
            showRunningOnly={showRunningOnly}
            taskLimit={taskLimit}
            onAdminActorBlur={onAdminActorBlur}
            onAdminActorChange={onAdminActorChange}
            onAdminTokenBlur={onAdminTokenBlur}
            onAdminTokenChange={onAdminTokenChange}
            onAutoRefreshChange={onAutoRefreshChange}
            onBackfillFormChange={onBackfillFormChange}
            spiderPresets={spiderPresets}
            onShowRunningOnlyChange={onShowRunningOnlyChange}
            onIngest={() => handleTaskTrigger(onIngest, "数据抓取")}
            onProcessGlobal={() => handleTaskTrigger(onProcessGlobal, "全球资讯处理")}
            onProcessDomestic={() => handleTaskTrigger(onProcessDomestic, "国内政经识别")}
            onProcessEmbed={() => handleTaskTrigger(onProcessEmbed, "向量索引生成")}
            onTaskLimitToggle={onTaskLimitToggle}
            availableSpiders={availableSpiders}
          />
          {panelError ? <div className="error" style={{ marginTop: 12 }}>{panelError}</div> : null}
          
          {(runtimeStatus?.warnings || []).length ? (
            <div className="runtime-warning-list" style={{ marginTop: 24 }}>
              {runtimeStatus.warnings.map((warning) => (
                <div key={warning} className="runtime-warning-item">{warning}</div>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {activeTab === 'overview' && (
        <div className="tab-pane fade-in">
          <div className="summary-grid">
            <div className="summary-card">
              <div className="muted">生产就绪</div>
              <strong>{runtimeStatus?.production_ready ? "是" : "否"}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">翻译模式</div>
              <strong>{runtimeStatus?.translation?.mode || "—"}</strong>
              <div className="muted">{runtimeStatus?.translation?.model || "未配置模型"}</div>
            </div>
            <div className="summary-card">
              <div className="muted">向量 Provider</div>
              <strong>{runtimeStatus?.embedding?.provider || "—"}</strong>
              <div className="muted">{runtimeStatus?.embedding?.model || "未配置模型"}</div>
            </div>
            <div className="summary-card">
              <div className="muted">Hybrid 权重</div>
              <strong>
                {runtimeStatus?.search?.hybrid_weights
                  ? `${runtimeStatus.search.hybrid_weights.keyword.toFixed(2)} / ${runtimeStatus.search.hybrid_weights.semantic.toFixed(2)}`
                  : "—"}
              </strong>
              <div className="muted">关键词 / 语义</div>
            </div>
          </div>

          <div className="summary-grid">
            <div className="summary-card">
              <div className="muted">总文章</div>
              <strong>{taskSummary?.total_articles ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">翻译完成</div>
              <strong>{taskSummary?.translation_completed ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">向量完成</div>
              <strong>{taskSummary?.embedding_completed ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">翻译待处理</div>
              <strong>{taskSummary?.translation_pending ?? 0}</strong>
            </div>
          </div>

          <div className="summary-grid">
            <div className="summary-card">
              <div className="muted">翻译处理中</div>
              <strong>{taskSummary?.translation_processing ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">翻译失败</div>
              <strong>{taskSummary?.translation_failed ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">向量处理中</div>
              <strong>{taskSummary?.embedding_processing ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">向量失败</div>
              <strong>{taskSummary?.embedding_failed ?? 0}</strong>
            </div>
          </div>

          <div className="summary-grid">
            <div className="summary-card">
              <div className="muted">24h 抓取任务</div>
              <strong>{monitorSummary?.crawl_jobs_24h ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">24h 抓取成功</div>
              <strong>{monitorSummary?.crawl_success_24h ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">24h 抓取失败</div>
              <strong>{monitorSummary?.crawl_failed_24h ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">24h 抓取条数</div>
              <strong>{monitorSummary?.items_scraped_24h ?? 0}</strong>
            </div>
          </div>

          <div className="summary-grid">
            <div className="summary-card">
              <div className="muted">抓取运行中</div>
              <strong>{monitorSummary?.crawl_running_now ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">任务排队中</div>
              <strong>{(taskMonitorSummary?.pending_tasks ?? 0) + (taskMonitorSummary?.retry_tasks ?? 0)}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">运行中回填</div>
              <strong>{taskMonitorSummary?.backfill_active ?? 0}</strong>
            </div>
            <div className="summary-card">
              <div className="muted">运行中完整流程</div>
              <strong>{taskMonitorSummary?.pipeline_run_active ?? 0}</strong>
            </div>
          </div>

          <div className="monitor-grid">
            <div className="summary-card">
              <div className="panel-head">
                <h2>最近抓取</h2>
                <span className="muted">最近 5 次</span>
              </div>
              <div className="monitor-list">
                {(monitorSummary?.latest_crawls || []).length ? (
                  monitorSummary.latest_crawls.map((item, index) => (
                    <div key={`${item.spider_name}-${item.started_at}-${index}`} className="monitor-item">
                      <div>
                        <strong>{item.spider_name}</strong>
                        <div className="muted">{formatDate(item.started_at)} / {item.items_scraped ?? 0} 条</div>
                      </div>
                      <span className={stateClass(item.status)}>{item.status}</span>
                    </div>
                  ))
                ) : (
                  <div className="empty">暂无抓取记录</div>
                )}
              </div>
            </div>
            <div className="summary-card">
              <div className="panel-head">
                <h2>失败 Spider Top</h2>
                <span className="muted">近 24 小时</span>
              </div>
              <div className="monitor-list">
                {(monitorSummary?.failed_spiders_24h || []).length ? (
                  monitorSummary.failed_spiders_24h.map((item) => (
                    <div key={item.spider_name} className="monitor-item">
                      <div>
                        <strong>{item.spider_name}</strong>
                      </div>
                      <div className="inline-actions">
                        <span className="state-pill state-failure">{item.failed_count}</span>
                        <button className="secondary compact-button" type="button" onClick={() => onUseSpiderInPipeline(item.spider_name, "replace")}>
                          覆盖运行
                        </button>
                        <button className="secondary compact-button" type="button" onClick={() => onUseSpiderInPipeline(item.spider_name, "append")}>
                          追加
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty">近 24 小时无失败记录</div>
                )}
              </div>
            </div>
          </div>

          <div className="monitor-grid">
            <div className="summary-card">
              <div className="panel-head">
                <h2>Spider 健康度</h2>
                <span className="muted">近 24 小时</span>
              </div>
              <div className="monitor-list">
                {(monitorSummary?.spider_health_24h || []).length ? (
                  monitorSummary.spider_health_24h.map((item) => (
                    <div key={item.spider_name} className="monitor-item monitor-item-stack">
                      <div>
                        <strong>{item.spider_name}</strong>
                        <div className="muted">
                          成功 {item.success_count ?? 0} / 失败 {item.failed_count ?? 0} / 总计 {item.total_count ?? 0}
                        </div>
                      </div>
                      <span className={stateClass((item.failed_count || 0) > 0 ? "FAILURE" : "SUCCESS")}>
                        {(item.success_rate ?? 0)}%
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="empty">近 24 小时暂无 spider 健康数据</div>
                )}
              </div>
            </div>
            <div className="summary-card">
              <div className="panel-head">
                <h2>最近失败摘要</h2>
                <span className="muted">最近 5 次</span>
              </div>
              <div className="monitor-list">
                {(monitorSummary?.recent_failures || []).length ? (
                  monitorSummary.recent_failures.map((item, index) => (
                    <div key={`${item.spider_name}-${item.started_at}-${index}`} className="monitor-item monitor-item-stack">
                      <div>
                        <strong>{item.spider_name}</strong>
                        <div className="muted">{formatDate(item.started_at)} / {item.items_scraped ?? 0} 条</div>
                        <div className="monitor-error">
                          {item.error_message || "无错误摘要"}
                        </div>
                      </div>
                      <div className="inline-actions">
                        <span className="state-pill state-failure">failed</span>
                        <button className="secondary compact-button" type="button" onClick={() => onUseSpiderInPipeline(item.spider_name, "replace")}>
                          覆盖运行
                        </button>
                        <button className="secondary compact-button" type="button" onClick={() => onUseSpiderInPipeline(item.spider_name, "append")}>
                          追加
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty">暂无失败摘要</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="tab-pane fade-in">
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '16px', 
            padding: '8px 12px', 
            background: '#f8fafc',
            borderRadius: '6px',
            border: '1px solid #e2e8f0'
          }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
              <input type="checkbox" checked={showRunningOnly} onChange={e => onShowRunningOnlyChange(e.target.checked)} />
              仅显示运行中任务
            </label>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <span className="muted" style={{ fontSize: '0.85rem' }}>显示上限: <strong>{taskLimit}</strong></span>
              <button className="secondary compact-button" onClick={onTaskLimitToggle}>
                切换数量 (5/20)
              </button>
            </div>
          </div>

          <ActiveTaskCard activeTask={activeTask} taskDetail={taskDetails[activeTask?.task_id]} onCancelTask={onCancelTask} />

          <TaskHistoryList
            activeTaskId={activeTaskId}
            highlightTaskId={highlightTaskId}
            taskDetails={taskDetails}
            tasks={tasks}
            onActiveTaskChange={onActiveTaskChange}
            onBatchCancelTasks={onBatchCancelTasks}
            onBatchRetryTasks={onBatchRetryTasks}
            onCancelTask={onCancelTask}
            onRetryTask={onRetryTask}
          />
        </div>
      )}

      <style jsx>{`
        .toast-container {
          position: fixed;
          top: 24px;
          right: 24px;
          padding: 12px 20px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          gap: 12px;
          z-index: 2000;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
          animation: slideIn 0.3s ease-out;
          color: white;
          font-weight: 500;
        }
        .toast-container.success {
          background: #10b981;
          border-left: 5px solid #059669;
        }
        .toast-container.error {
          background: #ef4444;
          border-left: 5px solid #dc2626;
        }
        .toast-icon {
          font-size: 1.2rem;
        }

        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.4);
          backdrop-filter: blur(4px);
          display: flex;
          justify-content: center;
          align-items: center;
          z-index: 1000;
          animation: fadeIn 0.2s ease-out;
        }
        .modal-content {
          background: white;
          width: 450px;
          border-radius: 12px;
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .modal-header {
          padding: 16px 20px;
          border-bottom: 1px solid #e2e8f0;
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: #f8fafc;
        }
        .modal-header h3 {
          margin: 0;
          font-size: 1.1rem;
          color: #1e293b;
        }
        .close-btn {
          background: none;
          border: none;
          font-size: 1.5rem;
          color: #94a3b8;
          cursor: pointer;
          padding: 0;
          line-height: 1;
        }
        .close-btn:hover {
          color: #64748b;
        }
        .modal-body {
          padding: 24px 20px;
        }
        .modal-footer {
          padding: 12px 20px;
          border-top: 1px solid #e2e8f0;
          display: flex;
          justify-content: flex-end;
          background: #f8fafc;
        }
        .hint {
          margin-top: 16px;
          font-size: 0.8rem;
          color: #94a3b8;
          font-style: italic;
          line-height: 1.4;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
