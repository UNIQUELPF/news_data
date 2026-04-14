"use client";

import AppHeader from "../components/AppHeader";
import ArticleDetail from "../components/ArticleDetail";
import ArticlesTable from "../components/ArticlesTable";
import SearchPanel from "../components/SearchPanel";
import SidebarNav from "../components/SidebarNav";
import { useArticleSearch } from "../hooks/useArticleSearch";

export default function Page() {
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

  return (
    <main className="shell">
      <AppHeader subtitle="搜索、筛选和文章详情的正式入口。任务调度与监控已迁移到 /admin。" />

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
              onNextPage={() => loadArticles(pagination.page + 1)}
              onOpenArticle={openArticle}
              onPrevPage={() => loadArticles(Math.max(1, pagination.page - 1))}
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
