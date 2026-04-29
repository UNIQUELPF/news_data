import { useCallback, useEffect, useState } from "react";
import { request } from "../lib/api";
import { buildArticleQuery, defaultFilters, normalizeArticleListResponse } from "../lib/articles";

export function useArticleSearch({ fixedCountry, fixedCountryCode } = {}) {
  const [filters, setFilters] = useState(() => ({
    ...defaultFilters,
    ...(fixedCountry ? { country: fixedCountry } : {}),
    ...(fixedCountryCode ? { countryCode: fixedCountryCode } : {})
  }));
  const [searchMode, setSearchMode] = useState("keyword");
  const [query, setQuery] = useState("");
  const [meta, setMeta] = useState({ categories: [], countries: [], organizations: [], companies: [], provinces: [], cities: [] });
  const [articles, setArticles] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, total: 0, total_pages: 0 });
  const [searchInfo, setSearchInfo] = useState({ mode: "keyword", query: null });
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [selectedArticleLoading, setSelectedArticleLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadArticles = useCallback(async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const [filtersData, articlesData] = await Promise.all([
        request("/api/v1/filters"),
        request("/api/v1/articles", {
          query: buildArticleQuery({ filters, page, query, searchMode, fixedCountry, fixedCountryCode })
        })
      ]);
      const normalized = normalizeArticleListResponse(articlesData);
      setMeta(filtersData);
      setArticles(normalized.items);
      setPagination(normalized.pagination);
      setSearchInfo(normalized.search);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [filters, fixedCountry, fixedCountryCode, query, searchMode]);

  async function openArticle(id) {
    setSelectedArticleLoading(true);
    setSelectedArticle(null);
    try {
      // Stage 1: Load core article data
      const data = await request(`/api/v1/articles/${id}`);
      setSelectedArticle(data);
      setSelectedArticleLoading(false);

      // Stage 2: Load recommendations asynchronously
      request(`/api/v1/articles/${id}/recommendations`)
        .then(recommendations => {
          setSelectedArticle(prev => {
            if (prev && prev.article && prev.article.id === id) {
              return { ...prev, ...recommendations };
            }
            return prev;
          });
        })
        .catch(err => console.error("Recommendations failed:", err));
    } catch (err) {
      console.error("Article load failed:", err);
      setSelectedArticleLoading(false);
    }
  }

  function updateFilter(name, value) {
    if ((name === "country" && fixedCountry) || (name === "countryCode" && fixedCountryCode)) {
      return;
    }
    setFilters((prev) => ({ ...prev, [name]: value }));
  }

  useEffect(() => {
    loadArticles(1);
  }, [loadArticles]);

  return {
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
  };
}
