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

  // Load filters once, not on every page turn
  const loadFilters = useCallback(async () => {
    try {
      const filtersData = await request("/api/v1/filters");
      setMeta(filtersData);
    } catch (e) {
      console.error("Filters load failed:", e);
    }
  }, []);

  const loadArticles = useCallback(async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const articlesData = await request("/api/v1/articles", {
        query: buildArticleQuery({ filters, page, query, searchMode, fixedCountry, fixedCountryCode })
      });
      const normalized = normalizeArticleListResponse(articlesData);
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
    
    // Auto-open article if ID is provided in URL
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const articleId = params.get('article');
      if (articleId) {
        openArticle(articleId);
      }
    }
  }, [loadArticles]);

  // Load filters once on mount, not on every page turn
  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

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
