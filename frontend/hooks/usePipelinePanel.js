import { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../lib/api";
import {
  ADMIN_ACTOR_STORAGE_KEY,
  ADMIN_TOKEN_STORAGE_KEY,
  applySpiderSelection,
  combineTaskLists,
  defaultBackfillForm,
  isActiveTaskState,
  mergeSpiderCsv,
  mergeTaskDetail,
  normalizeRuntimeStatus,
  parseSpiderCsv,
  resolveActiveTaskState,
  serializeSpiderPreset,
  selectActiveTask,
  selectVisibleTasks,
  validatePipelineRequestForm
} from "../lib/pipeline";

export function usePipelinePanel() {
  const [adminToken, setAdminToken] = useState("");
  const [adminActor, setAdminActor] = useState("");
  const [taskSummary, setTaskSummary] = useState(null);
  const [monitorSummary, setMonitorSummary] = useState(null);
  const [taskMonitorSummary, setTaskMonitorSummary] = useState(null);
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskDetails, setTaskDetails] = useState({});
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [highlightTaskId, setHighlightTaskId] = useState(null);
  const [taskLimit, setTaskLimit] = useState(5);
  const [showRunningOnly, setShowRunningOnly] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [panelError, setPanelError] = useState("");
  const [backfillForm, setBackfillForm] = useState(defaultBackfillForm);
  const [availableSpiders, setAvailableSpiders] = useState([]);

  useEffect(() => {
    setAdminToken(window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || "");
    setAdminActor(window.localStorage.getItem(ADMIN_ACTOR_STORAGE_KEY) || "");
  }, []);

  const loadMetadata = useCallback(async () => {
    if (!adminToken) return;
    const [spiderData] = await Promise.all([
      request("/api/v1/pipeline/spiders", { adminToken, adminActor })
    ]);

    setAvailableSpiders(spiderData.spiders || []);
  }, [adminActor, adminToken]);

  const loadStatus = useCallback(async () => {
    if (!adminToken) return;
    
    const tasks = [];
    // overview needs monitor and runtime
    if (activeTab === "overview") {
      tasks.push(request("/api/v1/pipeline/monitor", { adminToken, adminActor }));
      tasks.push(request("/api/v1/pipeline/runtime", { adminToken, adminActor }));
    } 
    // control needs runtime (for warnings)
    else if (activeTab === "control") {
      tasks.push(request("/api/v1/pipeline/runtime", { adminToken, adminActor }));
    }
    // logs needs groups (task list)
    else if (activeTab === "logs") {
      tasks.push(request("/api/v1/pipeline/groups", {
        adminToken,
        adminActor,
        query: { limit: taskLimit * 2 }
      }));
    }

    if (tasks.length === 0) return;

    const results = await Promise.all(tasks);
    
    if (activeTab === "overview") {
      const [monitorData, runtimeData] = results;
      setTaskSummary(monitorData.pipeline || null);
      setMonitorSummary(monitorData.crawl || null);
      setTaskMonitorSummary(monitorData.tasks || null);
      setRuntimeStatus(normalizeRuntimeStatus(runtimeData));
    } else if (activeTab === "control") {
      const [runtimeData] = results;
      setRuntimeStatus(normalizeRuntimeStatus(runtimeData));
    } else if (activeTab === "logs") {
      const [groupsTaskData] = results;
      const mergedTasks = combineTaskLists(groupsTaskData.items || []);
      setTasks(mergedTasks);
      if (!activeTaskId && mergedTasks.length) {
        setActiveTaskId(mergedTasks[0].task_id);
      }
    }
  }, [activeTab, activeTaskId, adminActor, adminToken, taskLimit]);

  const loadPanel = useCallback(
    async (full = false) => {
      if (!adminToken && !full) {
        if (typeof window !== "undefined" && window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)) {
          return;
        }
        setPanelError("管理面板需要有效的 Admin Token");
        setTaskSummary(null);
        setMonitorSummary(null);
        setTaskMonitorSummary(null);
        setRuntimeStatus(null);
        setTasks([]);
        return;
      }
      try {
        if (full) {
          // Full load still fetches everything to ensure consistency
          const [monitorData, runtimeData, groupsTaskData, spiderData] = await Promise.all([
            request("/api/v1/pipeline/monitor", { adminToken, adminActor }),
            request("/api/v1/pipeline/runtime", { adminToken, adminActor }),
            request("/api/v1/pipeline/groups", { adminToken, adminActor, query: { limit: taskLimit * 2 } }),
            request("/api/v1/pipeline/spiders", { adminToken, adminActor })
          ]);
          
          setTaskSummary(monitorData.pipeline || null);
          setMonitorSummary(monitorData.crawl || null);
          setTaskMonitorSummary(monitorData.tasks || null);
          setRuntimeStatus(normalizeRuntimeStatus(runtimeData));
          
          const mergedTasks = combineTaskLists(groupsTaskData.items || []);
          setTasks(mergedTasks);
          if (!activeTaskId && mergedTasks.length) {
            setActiveTaskId(mergedTasks[0].task_id);
          }

          setAvailableSpiders(spiderData.spiders || []);
        } else {
          await loadStatus();
        }
        setPanelError("");
      } catch (panelLoadError) {
        setPanelError(panelLoadError.message);
      }
    },
    [activeTaskId, adminActor, adminToken, loadStatus, taskLimit]
  );

  const loadTaskDetail = useCallback(async (taskId) => {
    if (!taskId || !adminToken) return;
    try {
      const detail = await request(`/api/v1/pipeline/tasks/${taskId}`, { adminToken, adminActor });
      setTaskDetails((prev) => ({ ...prev, [taskId]: detail }));
      setTasks((prev) => mergeTaskDetail(prev, taskId, detail));
    } catch (detailError) {
      setPanelError(detailError.message);
    }
  }, [adminActor, adminToken]);

  async function onIngest() {
    const spiders = parseSpiderCsv(backfillForm.spiders_text);
    if (!spiders.length) {
      setPanelError("请至少选择一个爬虫");
      return;
    }
    const data = await request("/api/v1/pipeline/ingest", {
      method: "POST",
      body: { spiders },
      adminToken,
      adminActor
    });
    setPanelError("");
    setActiveTaskId(data.task_id);
    setHighlightTaskId(data.task_id);
    await loadPanel(true);
  }

  async function onProcessGlobal() {
    const data = await request("/api/v1/pipeline/process/global", {
      method: "POST",
      body: {
        limit: backfillForm.translate_limit,
        force: backfillForm.force_translate,
        target_language: backfillForm.target_language
      },
      adminToken,
      adminActor
    });
    setPanelError("");
    setActiveTaskId(data.task_id);
    setHighlightTaskId(data.task_id);
    await loadPanel(true);
  }

  async function onProcessDomestic() {
    const data = await request("/api/v1/pipeline/process/domestic", {
      method: "POST",
      body: {
        limit: backfillForm.translate_limit,
        force: backfillForm.force_translate
      },
      adminToken,
      adminActor
    });
    setPanelError("");
    setActiveTaskId(data.task_id);
    setHighlightTaskId(data.task_id);
    await loadPanel(true);
  }

  async function onProcessEmbed() {
    const data = await request("/api/v1/pipeline/process/embed", {
      method: "POST",
      body: {
        limit: backfillForm.embed_limit,
        force: backfillForm.force_embed
      },
      adminToken,
      adminActor
    });
    setPanelError("");
    setActiveTaskId(data.task_id);
    setHighlightTaskId(data.task_id);
    await loadPanel(true);
  }

  async function cancelTask(taskId, quiet = false) {
    if (!quiet && !window.confirm(`确认取消任务 ${taskId} 吗？`)) return;
    await request(`/api/v1/pipeline/tasks/${taskId}/cancel`, {
      method: "POST",
      adminToken,
      adminActor
    });
    if (!quiet) {
      setActiveTaskId(taskId);
      setHighlightTaskId(taskId);
      await loadPanel(true);
    }
  }

  async function batchCancelTasks(taskIds) {
    if (!taskIds.length) return;
    if (!window.confirm(`确认批量取消这 ${taskIds.length} 个任务吗？`)) return;
    
    await Promise.allSettled(taskIds.map(id => cancelTask(id, true)));
    await loadPanel(true);
  }

  async function retryTask(taskId, quiet = false) {
    if (!quiet && !window.confirm(`确认按原参数重试任务 ${taskId} 吗？`)) return;
    const data = await request(`/api/v1/pipeline/tasks/${taskId}/retry`, {
      method: "POST",
      adminToken,
      adminActor
    });
    if (!quiet) {
      setActiveTaskId(data.task_id);
      setHighlightTaskId(data.task_id);
      await loadPanel(true);
    }
  }

  async function batchRetryTasks(taskIds) {
    if (!taskIds.length) return;
    if (!window.confirm(`确认批量重试这 ${taskIds.length} 个任务吗？`)) return;
    
    await Promise.allSettled(taskIds.map(id => retryTask(id, true)));
    await loadPanel(true);
  }

  function updateBackfillForm(name, value) {
    setBackfillForm((prev) => {
      if (name === "append_spiders") {
        return { ...prev, spiders_text: mergeSpiderCsv(prev.spiders_text, value) };
      }
      return { ...prev, [name]: value };
    });
  }

  function persistAdminToken() {
    window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminToken);
  }

  function persistAdminActor() {
    window.localStorage.setItem(ADMIN_ACTOR_STORAGE_KEY, adminActor);
  }

  function useSpiderInPipeline(spiderName, mode = "replace") {
    setBackfillForm((prev) => applySpiderSelection(prev, spiderName, mode));
    setPanelError("");
  }

  useEffect(() => {
    loadPanel(true);
  }, [loadPanel]);

  useEffect(() => {
    if (!autoRefresh || !adminToken) return undefined;
    const timer = window.setInterval(() => {
      loadPanel(false);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [adminToken, autoRefresh, loadPanel]);

  const activeTaskState = useMemo(() => {
    return resolveActiveTaskState(activeTaskId, taskDetails, tasks);
  }, [activeTaskId, taskDetails, tasks]);

  useEffect(() => {
    if (!activeTaskId || !adminToken || activeTab !== "logs") return undefined;
    loadTaskDetail(activeTaskId);
    if (!isActiveTaskState(activeTaskState)) return undefined;
    const timer = window.setInterval(() => {
      loadTaskDetail(activeTaskId);
      loadPanel(false);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeTaskId, activeTaskState, activeTab, adminToken, loadPanel, loadTaskDetail]);

  useEffect(() => {
    if (!highlightTaskId) return undefined;
    const timer = window.setTimeout(() => setHighlightTaskId(null), 6000);
    return () => window.clearTimeout(timer);
  }, [highlightTaskId]);

  const visibleTasks = useMemo(() => {
    return selectVisibleTasks(tasks, showRunningOnly);
  }, [showRunningOnly, tasks]);

  const activeTask = useMemo(() => selectActiveTask(tasks), [tasks]);

  return {
    adminActor,
    adminToken,
    activeTab,
    activeTask,
    activeTaskId,
    autoRefresh,
    backfillForm,
    highlightTaskId,
    panelError,
    showRunningOnly,
    taskDetails,
    taskLimit,
    monitorSummary,
    runtimeStatus,
    taskMonitorSummary,
    taskSummary,
    tasks: visibleTasks,
    batchCancelTasks,
    batchRetryTasks,
    cancelTask,
    loadPanel,
    retryTask,
    setActiveTab,
    setActiveTaskId,
    setAdminActor,
    setAdminToken,
    setAutoRefresh,
    setShowRunningOnly,
    setTaskLimit,
    availableSpiders,
    onIngest,
    onProcessGlobal,
    onProcessDomestic,
    onProcessEmbed,
    updateBackfillForm,
    persistAdminActor,
    persistAdminToken,
    useSpiderInPipeline
  };
}
