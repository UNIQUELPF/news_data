"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getUser } from "../lib/auth";
import { useEffect, useState } from "react";

export default function SidebarNav() {
  const pathname = usePathname();
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  const isAdmin = user?.role === "admin";

  return (
    <aside className="sidebar">
      <Link className={`nav-item ${pathname === "/" ? "active" : ""}`} href="/">
        <span className="nav-icon">◉</span>
        <span>国际政治经济数据库</span>
      </Link>
      <Link className={`nav-item ${pathname === "/domestic" ? "active" : ""}`} href="/domestic">
        <span className="nav-icon">⚑</span>
        <span>国内政治经济数据库</span>
      </Link>
      <Link className={`nav-item ${pathname === "/chat" ? "active" : ""}`} href="/chat">
        <span className="nav-icon">🤖</span>
        <span>政经小助手</span>
      </Link>
      {isAdmin && (
        <>
          <Link className={`nav-item ${pathname === "/admin" ? "active" : ""}`} href="/admin">
            <span className="nav-icon">▣</span>
            <span>任务与运行管理</span>
          </Link>
          <Link className={`nav-item ${pathname === "/admin/users" ? "active" : ""}`} href="/admin/users">
            <span className="nav-icon">👤</span>
            <span>用户管理</span>
          </Link>
        </>
      )}
    </aside>
  );
}
