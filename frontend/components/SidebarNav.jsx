"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SidebarNav() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <Link className={`nav-item ${pathname === "/" ? "active" : ""}`} href="/">
        <span className="nav-icon">◉</span>
        <span>全球政治经济数据库</span>
      </Link>
      <Link className={`nav-item ${pathname === "/domestic" ? "active" : ""}`} href="/domestic">
        <span className="nav-icon">⚑</span>
        <span>国内政治经济数据</span>
      </Link>
      <Link className={`nav-item ${pathname === "/admin" ? "active" : ""}`} href="/admin">
        <span className="nav-icon">▣</span>
        <span>任务与运行管理</span>
      </Link>
    </aside>
  );
}
