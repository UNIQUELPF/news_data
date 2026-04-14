export const defaultFilters = {
  category: "all",
  country: "all",
  countryCode: "all",
  organization: "all",
  province: "all",
  city: "all",
  timeRange: "all"
};

export function buildArticleQuery({ filters, page = 1, query = "", searchMode = "keyword", pageSize = 10, fixedCountry, fixedCountryCode }) {
  return {
    q: query,
    search_mode: searchMode,
    category: filters.category,
    country: fixedCountry || filters.country,
    country_code: fixedCountryCode || filters.countryCode,
    organization: filters.organization,
    province: filters.province,
    city: filters.city,
    time_range: filters.timeRange,
    page,
    page_size: pageSize
  };
}

export function normalizeArticleListResponse(payload) {
  return {
    items: payload?.items || [],
    pagination: payload?.pagination || { page: 1, total: 0, total_pages: 0 },
    search: payload?.search || { mode: "keyword", query: null, weights: null }
  };
}
