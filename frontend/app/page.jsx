"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "../lib/auth";
import AppHeader from "../components/AppHeader";
import ArticleDetail from "../components/ArticleDetail";
import ArticlesTable from "../components/ArticlesTable";
import SearchPanel from "../components/SearchPanel";
import SidebarNav from "../components/SidebarNav";
import { useArticleSearch } from "../hooks/useArticleSearch";

export default function Page() {
  const router = useRouter();
  const [isAuthChecking, setIsAuthChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
    } else {
      setIsAuthChecking(false);
    }
  }, [router]);

  const {
    articles,
    error,
    filters,
    loading,
    meta,
    pagination,
    query,
    searchInfo,
    searchMode,
    selectedArticle,
    selectedArticleLoading,
    loadArticles,
    openArticle,
    setQuery,
    setSearchMode,
    setSelectedArticle,
    updateFilter
  } = useArticleSearch();

  if (isAuthChecking) {
    return <div style={{ background: '#0e2c4f', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>加载中...</div>;
  }

  return (
    <main className="shell">
      <AppHeader subtitle="搜索、筛选和文章详情的正式入口。" />

      <div className="main-grid">
        <SidebarNav />

        <section className="content-stack">
          <SearchPanel
            filters={filters}
            meta={meta}
            query={query}
            searchInfo={searchInfo}
            searchMode={searchMode}
            onFilterChange={updateFilter}
            onQueryChange={setQuery}
            onSearch={() => { setSelectedArticle(null); loadArticles(1); }}
            onSearchModeChange={setSearchMode}
            isDetailMode={!!selectedArticle}
            onBack={() => setSelectedArticle(null)}
          />

          {!selectedArticle ? (
            <ArticlesTable
              articles={articles}
              error={error}
              loading={loading}
              pagination={pagination}
              searchInfo={searchInfo}
              onOpenArticle={openArticle}
              onNextPage={() => loadArticles(pagination.page + 1)}
              onPrevPage={() => loadArticles(Math.max(1, pagination.page - 1))}
              onJumpPage={(p) => loadArticles(p)}
            />
          ) : (
            <ArticleDetail
              articleData={selectedArticle}
              loading={selectedArticleLoading}
              onOpenArticle={openArticle}
            />
          )}
        </section>
      </div>
    </main>
  );
}
