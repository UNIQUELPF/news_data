"use client";

import AppHeader from "../../components/AppHeader";
import SidebarNav from "../../components/SidebarNav";
import TaskPanel from "../../components/TaskPanel";
import { usePipelinePanel } from "../../hooks/usePipelinePanel";

export default function AdminPage() {
  const {
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
    taskMonitorSummary,
    showRunningOnly,
    taskDetails,
    taskLimit,
    taskSummary,
    tasks,
    batchCancelTasks,
    batchRetryTasks,
    cancelTask,
    retryTask,
    setActiveTaskId,
    setAdminActor,
    setAdminToken,
    setAutoRefresh,
    setShowRunningOnly,
    setTaskLimit,
    spiderPresets,
    onIngest,
    onProcessGlobal,
    onProcessDomestic,
    onProcessEmbed,
    updateBackfillForm,
    useSpiderInPipeline,
    availableSpiders,
    persistAdminActor,
    persistAdminToken,
    loadPanel
  } = usePipelinePanel();

  return (
    <main className="shell">
      <AppHeader subtitle="管理员入口，用于回填、完整流程执行、运行监控和故障排查。" />

      <div className="main-grid">
        <SidebarNav />

        <section className="content-stack">
          <TaskPanel
            adminActor={adminActor}
            adminToken={adminToken}
            activeTask={activeTask}
            activeTaskId={activeTaskId}
            autoRefresh={autoRefresh}
            backfillForm={backfillForm}
            highlightTaskId={highlightTaskId}
            monitorSummary={monitorSummary}
            panelError={panelError}
            runtimeStatus={runtimeStatus}
            showRunningOnly={showRunningOnly}
            taskMonitorSummary={taskMonitorSummary}
            taskDetails={taskDetails}
            taskLimit={taskLimit}
            taskSummary={taskSummary}
            tasks={tasks}
            onActiveTaskChange={setActiveTaskId}
            onAdminActorBlur={persistAdminActor}
            onAdminActorChange={setAdminActor}
            onAdminTokenBlur={persistAdminToken}
            onAdminTokenChange={setAdminToken}
            onAutoRefreshChange={setAutoRefresh}
            onBackfillFormChange={updateBackfillForm}
            onBatchCancelTasks={batchCancelTasks}
            onBatchRetryTasks={batchRetryTasks}
            onCancelTask={cancelTask}
            onRetryTask={retryTask}
            spiderPresets={spiderPresets}
            onShowRunningOnlyChange={setShowRunningOnly}
            onIngest={onIngest}
            onProcessGlobal={onProcessGlobal}
            onProcessDomestic={onProcessDomestic}
            onProcessEmbed={onProcessEmbed}
            onTaskLimitToggle={() => setTaskLimit((prev) => (prev > 5 ? 5 : 20))}
            onUseSpiderInPipeline={useSpiderInPipeline}
            availableSpiders={availableSpiders}
            persistAdminActor={persistAdminActor}
            persistAdminToken={persistAdminToken}
            loadPanel={loadPanel}
          />
        </section>
      </div>
    </main>
  );
}
