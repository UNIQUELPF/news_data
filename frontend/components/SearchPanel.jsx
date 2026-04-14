const timeOptions = [
  ["all", "全部时间"],
  ["1d", "近1天"],
  ["3d", "近3天"],
  ["7d", "近7天"],
  ["1m", "近1个月"],
  ["6m", "近半年"],
  ["1y", "近1年"]
];

export default function SearchPanel({
  filters,
  meta,
  query,
  searchMode,
  searchInfo,
  onQueryChange,
  onSearchModeChange,
  onFilterChange,
  onSearch,
  isDetailMode,
  onBack,
  hideCountryFilter = false,
  hideOrganizationFilter = false,
  categoryOptions,
  showProvinceCityFilters = false
}) {
  const categories = categoryOptions || meta.categories || [];

  return (
    <div className="search-panel">
      {searchInfo.mode === "hybrid" && searchInfo.weights && !isDetailMode ? (
        <div className="chips search-weight-chips">
          <span className="chip">关键词权重 {searchInfo.weights.keyword}</span>
          <span className="chip">语义权重 {searchInfo.weights.semantic}</span>
        </div>
      ) : null}
      <div className="search-toolbar">
        {isDetailMode ? (
          <button className="back-link" onClick={onBack}>← 返回列表</button>
        ) : (
          <div /> /* invisible spacer for space-between flex */
        )}
        {!isDetailMode && (
          <div className="search-input-shell compact-search">
            <span className="search-leading">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
            </span>
            <input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onSearch() }}
              placeholder="搜索标题、企业、关键词..."
            />
            <button className="search-submit compact-submit" onClick={onSearch}>→</button>
          </div>
        )}
      </div>
      {!isDetailMode && (
        <div className="filters-bar no-border">
          <div className="filter-pair">
            <span className="filter-pill-label">资讯类别</span>
            <select className="pill-select" value={filters.category} onChange={(event) => onFilterChange("category", event.target.value)}>
              <option value="all">全部类别</option>
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          {!hideCountryFilter ? (
            <div className="filter-pair">
              <span className="filter-pill-label">国别</span>
              <select className="pill-select" value={filters.country} onChange={(event) => onFilterChange("country", event.target.value)}>
                <option value="all">全部国家</option>
                {meta.countries?.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
          ) : null}
          {showProvinceCityFilters ? (
            <>
              <div className="filter-pair">
                <span className="filter-pill-label">所在省</span>
                <select className="pill-select" value={filters.province} onChange={(event) => onFilterChange("province", event.target.value)}>
                  <option value="all">全部省份</option>
                  {meta.provinces?.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </div>
              <div className="filter-pair">
                <span className="filter-pill-label">所在市</span>
                <select className="pill-select" value={filters.city} onChange={(event) => onFilterChange("city", event.target.value)}>
                  <option value="all">全部城市</option>
                  {meta.cities?.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </div>
            </>
          ) : null}
          {!hideOrganizationFilter ? (
            <div className="filter-pair">
              <span className="filter-pill-label">组织</span>
              <select className="pill-select" value={filters.organization} onChange={(event) => onFilterChange("organization", event.target.value)}>
                <option value="all">全部组织</option>
                {meta.organizations?.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
          ) : null}
          <div className="filter-pair filter-pair-time">
            <span className="filter-pill-label">时间筛选</span>
            <select className="pill-select" value={filters.timeRange} onChange={(event) => onFilterChange("timeRange", event.target.value)}>
              {timeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
