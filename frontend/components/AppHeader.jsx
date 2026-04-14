export default function AppHeader({
  title = "全球政治经济数据库",
  subtitle = "搜索、筛选和文章详情的正式入口。任务调度与监控已迁移到 /admin。",
  trailing = "Alexander Moro"
}) {
  return (
    <section className="topbar">
      <div className="brand">
        <div className="brand-mark">◎</div>
        <div>
          <div className="title">{title}</div>
        </div>
      </div>
      <div className="topbar-user">
        <span>{trailing}</span>
        <span className="topbar-avatar">◉</span>
      </div>
    </section>
  );
}
