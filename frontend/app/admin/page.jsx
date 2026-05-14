"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken, getUser } from "../../lib/auth";
import AppHeader from "../../components/AppHeader";
import SidebarNav from "../../components/SidebarNav";
import TaskPanel from "../../components/TaskPanel";
import { usePipelinePanel } from "../../hooks/usePipelinePanel";

export default function AdminPage() {
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

  const {
    adminActor,
    adminToken,
    activeTab,
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
    revokeTask,
    retryTask,
    setActiveTab,
    setActiveTaskId,
    setAdminActor,
    setAdminToken,
    setAutoRefresh,
    setShowRunningOnly,
    setTaskLimit,
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

  if (isAuthChecking) {
    return <div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>;
  }

  return (
    <main className="shell">
      <AppHeader subtitle="管理员入口，用于回填、完整流程执行、运行监控和故障排查。" />

      <div className="main-grid">
        <SidebarNav />

        <section className="content-stack">
          <TaskPanel
            adminActor={adminActor}
            adminToken={adminToken}
            activeTab={activeTab}
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
            onActiveTabChange={setActiveTab}
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
            onRevokeTask={revokeTask}
            onRetryTask={retryTask}
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
