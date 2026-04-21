"use client";

import AppHeader from "../../components/AppHeader";
import ArticleDetail from "../../components/ArticleDetail";
import ArticlesTable from "../../components/ArticlesTable";
import SearchPanel from "../../components/SearchPanel";
import SidebarNav from "../../components/SidebarNav";
import { useArticleSearch } from "../../hooks/useArticleSearch";

const DOMESTIC_CATEGORY_OPTIONS = ["政治", "经济", "军事", "法规", "科技", "社会", "环境"];

export default function DomesticPage() {
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
  } = useArticleSearch({ fixedCountry: "中国", fixedCountryCode: "CHN" });

  return (
    <main className="shell">
      <AppHeader subtitle="国内政治经济数据 — 聚焦中国相关的政策、经济与产业动态。" />

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
            categoryOptions={DOMESTIC_CATEGORY_OPTIONS}
            hideCountryFilter={true}
            hideOrganizationFilter={true}
            showProvinceCityFilters={true}
          />

          {!selectedArticle ? (
            <ArticlesTable
              articles={articles}
              error={error}
              loading={loading}
              pagination={pagination}
              searchInfo={searchInfo}
              variant="domestic"
              onNextPage={() => loadArticles(pagination.page + 1)}
              onOpenArticle={openArticle}
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
