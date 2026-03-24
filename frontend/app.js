// In production, set this to your deployed backend URL (e.g. "https://citation-analysis.onrender.com")
// In development or when served by FastAPI, leave as ""
const API_BASE = "";

const state = {
  clusters: [],
  periods: [],
  series: {},
  likelyClusters: [],
  risingClusters: [],
  likedClusterIds: [],
  likedPaperIds: [],
  recommendations: [],
  clusterPapers: {},
  venuePapers: [],
  allVenuePapers: [],
  venues: [],
  selectedVenue: "",
  selectedVenues: [],
  selectedVenueYear: "",
  activeClusterId: null,
  venueScopedClusters: [],
  showMoreVenues: false,
  venueSearchTerm: "",
  modalPapers: [],
  modalSearch: null,
  likedPanelOpen: false,
  visibleClusterCount: 8,
};

const els = {
  heroMetrics: document.getElementById("heroMetrics"),
  clusterList: document.getElementById("clusterList"),
  paperSearchInput: document.getElementById("paperSearchInput"),
  paperSearchBtn: document.getElementById("paperSearchBtn"),
  paperNameSearchInput: document.getElementById("paperNameSearchInput"),
  paperNameSearchBtn: document.getElementById("paperNameSearchBtn"),
  venueButtons: document.getElementById("venueButtons"),
  moreVenueButtons: document.getElementById("moreVenueButtons"),
  venueSearchWrap: document.getElementById("venueSearchWrap"),
  venueSearchInput: document.getElementById("venueSearchInput"),
  venueYearFilter: document.getElementById("venueYearFilter"),
  searchInput: document.getElementById("searchInput"),
  trendFilter: document.getElementById("trendFilter"),
  sortFilter: document.getElementById("sortFilter"),
  emptyState: document.getElementById("emptyState"),
  clusterDetail: document.getElementById("clusterDetail"),
  detailTrendBadge: document.getElementById("detailTrendBadge"),
  detailName: document.getElementById("detailName"),
  detailDescription: document.getElementById("detailDescription"),
  detailStats: document.getElementById("detailStats"),
  likelySubtitle: document.getElementById("likelySubtitle"),
  timelineChart: document.getElementById("timelineChart"),
  timelineTooltip: document.getElementById("timelineTooltip"),
  venueList: document.getElementById("venueList"),
  signalList: document.getElementById("signalList"),
  paperList: document.getElementById("paperList"),
  papersPanelTitle: document.getElementById("papersPanelTitle"),
  papersPanelSubtitle: document.getElementById("papersPanelSubtitle"),
  likelyList: document.getElementById("likelyList"),
  likedPapers: document.getElementById("likedPapers"),
  recommendationList: document.getElementById("recommendationList"),
  clearLikesBtn: document.getElementById("clearLikesBtn"),
  clusterMoreBtn: document.getElementById("clusterMoreBtn"),
  likedPanelToggleBtn: document.getElementById("likedPanelToggleBtn"),
  likedPanelCloseBtn: document.getElementById("likedPanelCloseBtn"),
  likedSidePanel: document.getElementById("likedSidePanel"),
  paperModal: document.getElementById("paperModal"),
  modalBackdrop: document.getElementById("modalBackdrop"),
  modalCloseBtn: document.getElementById("modalCloseBtn"),
  modalTitle: document.getElementById("modalTitle"),
  modalSubtitle: document.getElementById("modalSubtitle"),
  modalRefineInput: document.getElementById("modalRefineInput"),
  modalSortSelect: document.getElementById("modalSortSelect"),
  modalPaperList: document.getElementById("modalPaperList"),
  modalMoreBtn: document.getElementById("modalMoreBtn"),
};

const fmt = new Intl.NumberFormat("en-US");
let timelineTooltipTimer = null;

function setButtonLoading(button, isLoading, loadingLabel = "Searching...") {
  if (!button) {
    return;
  }
  if (isLoading) {
    if (!button.dataset.originalLabel) {
      button.dataset.originalLabel = button.textContent.trim();
    }
    button.disabled = true;
    button.classList.add("is-loading");
    button.innerHTML = `<span class="button-spinner" aria-hidden="true"></span><span>${loadingLabel}</span>`;
    return;
  }
  button.disabled = false;
  button.classList.remove("is-loading");
  button.textContent = button.dataset.originalLabel || button.textContent;
}

async function fetchJson(url) {
  const response = await fetch(API_BASE + url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(API_BASE + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json();
}

function trendClass(label) {
  return `trend-pill trend-${label || "stable"}`;
}

function hideTimelineTooltip() {
  if (timelineTooltipTimer) {
    window.clearTimeout(timelineTooltipTimer);
    timelineTooltipTimer = null;
  }
  els.timelineTooltip?.classList.add("hidden");
  els.timelineTooltip?.setAttribute("aria-hidden", "true");
}

function showTimelineTooltip(event, text) {
  hideTimelineTooltip();
  timelineTooltipTimer = window.setTimeout(() => {
    if (!els.timelineTooltip || !els.timelineChart) {
      return;
    }
    const chartRect = els.timelineChart.getBoundingClientRect();
    const x = event.clientX - chartRect.left + 10;
    const y = event.clientY - chartRect.top - 12;
    els.timelineTooltip.textContent = text;
    els.timelineTooltip.style.left = `${x}px`;
    els.timelineTooltip.style.top = `${Math.max(y, 12)}px`;
    els.timelineTooltip.classList.remove("hidden");
    els.timelineTooltip.setAttribute("aria-hidden", "false");
  }, 3000);
}

function currentScopeLabel() {
  if (!state.selectedVenues.length || state.selectedVenues.includes("All")) {
    return state.selectedVenueYear ? `All venues in ${state.selectedVenueYear}` : "All venues";
  }
  const label = state.selectedVenues.length <= 2
    ? state.selectedVenues.join(", ")
    : `${state.selectedVenues.slice(0, 2).join(", ")} +${state.selectedVenues.length - 2}`;
  return state.selectedVenueYear ? `${label} ${state.selectedVenueYear}` : label;
}

function currentClusterSource() {
  return state.venueScopedClusters.length ? state.venueScopedClusters : state.clusters;
}

function activeScopeParams() {
  const params = new URLSearchParams();
  if (state.selectedVenues.length && !state.selectedVenues.includes("All")) {
    params.set("venues", state.selectedVenues.join(","));
  } else if (state.selectedVenue && state.selectedVenue !== "All") {
    params.set("venue", state.selectedVenue);
  }
  if (state.selectedVenueYear) {
    params.set("year", state.selectedVenueYear);
  }
  return params;
}

function renderHeroMetrics() {
  if (!els.heroMetrics) {
    return;
  }
  const scopedClusters = currentClusterSource();
  const risingCount = scopedClusters.filter((cluster) => cluster.trend_label === "rising" || cluster.trend_label === "hot").length;
  const totalCitations = scopedClusters.reduce((sum, cluster) => sum + (cluster.total_citations || 0), 0);
  const totalPapers = scopedClusters.reduce((sum, cluster) => sum + (cluster.paper_count || 0), 0);
  const strongest = [...scopedClusters]
    .sort((a, b) => (b.trend_score || 0) - (a.trend_score || 0))
    .slice(0, 1)[0];

  const metrics = [
    ["Clusters", fmt.format(scopedClusters.length)],
    ["Rising Themes", fmt.format(risingCount)],
    ["Papers", fmt.format(totalPapers)],
    ["Top Momentum", strongest ? strongest.name : "N/A"],
    ["Citations", fmt.format(totalCitations)],
    ["Scope", currentScopeLabel()],
  ];

  els.heroMetrics.innerHTML = metrics
    .map(
      ([label, value]) => `
        <article class="metric-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `,
    )
    .join("");
}

function getFilteredClusters() {
  const q = els.searchInput.value.trim().toLowerCase();
  const trend = els.trendFilter.value;
  const sort = els.sortFilter.value;
  const trendPriority = { hot: 4, rising: 3, stable: 2, declining: 1 };

  let clusters = currentClusterSource().filter((cluster) => cluster.enabled !== false);
  if (trend) {
    clusters = clusters.filter((cluster) => cluster.trend_label === trend);
  }
  if (q) {
    clusters = clusters.filter((cluster) => {
      return cluster.name.toLowerCase().includes(q) || cluster.description.toLowerCase().includes(q);
    });
  }

  const sorters = {
    trend: (a, b) =>
      (trendPriority[b.trend_label] || 0) - (trendPriority[a.trend_label] || 0) ||
      (b.trend_score || 0) - (a.trend_score || 0) ||
      (b.total_citations || 0) - (a.total_citations || 0),
    citations: (a, b) => (b.total_citations || 0) - (a.total_citations || 0),
    papers: (a, b) => (b.paper_count || 0) - (a.paper_count || 0),
    name: (a, b) => a.name.localeCompare(b.name),
  };

  return clusters.sort(sorters[sort]);
}

function renderClusterList() {
  const filteredClusters = getFilteredClusters();
  const clusters = filteredClusters.slice(0, state.visibleClusterCount);
  els.clusterList.innerHTML = clusters
    .map((cluster) => {
      const active = cluster.id === state.activeClusterId ? "active" : "";
      const shortDescription =
        cluster.description.length > 180 ? `${cluster.description.slice(0, 177)}...` : cluster.description;
      return `
        <article class="cluster-item ${active}" data-cluster-id="${cluster.id}">
          <p class="${trendClass(cluster.trend_label)}">${cluster.trend_label} · score ${cluster.trend_score.toFixed(2)}</p>
          <h3>${cluster.name}</h3>
          <p>${shortDescription}</p>
          <div class="cluster-meta">
            <span>${fmt.format(cluster.paper_count)} papers</span>
            <span>${fmt.format(cluster.total_citations)} citations</span>
            <span>Peak ${cluster.peak_period || "N/A"}</span>
          </div>
          <div class="paper-actions">
            <button class="like-btn ${state.likedClusterIds.includes(cluster.id) ? "active" : ""}" data-cluster-like="${cluster.id}">
              ${state.likedClusterIds.includes(cluster.id) ? "Liked Direction" : "Like Direction"}
            </button>
          </div>
        </article>
      `;
    })
    .join("");

  els.clusterList.querySelectorAll(".cluster-item").forEach((item) => {
    item.addEventListener("click", () => {
      state.activeClusterId = Number(item.dataset.clusterId);
      renderClusterList();
      renderClusterDetail();
    });
  });
  els.clusterList.querySelectorAll("[data-cluster-like]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleLikedCluster(Number(button.dataset.clusterLike));
    });
  });
  if (els.clusterMoreBtn) {
    const hasMore = filteredClusters.length > clusters.length;
    els.clusterMoreBtn.classList.toggle("hidden", !hasMore);
  }
}

function renderDirectionCards(target, clusters) {
  if (!target) {
    return;
  }
  if (!clusters.length) {
    target.innerHTML = `
      <article class="rising-item empty-card">
        <strong>No directions yet</strong>
        <span>Like a paper or click "Like Direction" on a domain card.</span>
        <span>Then this panel will start learning your preferences and surface likely research directions.</span>
      </article>
    `;
    return;
  }
  target.innerHTML = clusters
    .map(
      (cluster) => `
        <article class="rising-item" data-cluster-id="${cluster.id}">
          <p class="${trendClass(cluster.trend_label)}">${cluster.trend_label} · ${cluster.trend_score.toFixed(2)}</p>
          <strong>${cluster.name}</strong>
          <span>${fmt.format(cluster.paper_count)} papers · ${fmt.format(cluster.total_citations)} citations</span>
          <button class="like-btn ${state.likedClusterIds.includes(cluster.id) ? "active" : ""}" data-cluster-like="${cluster.id}">
            ${state.likedClusterIds.includes(cluster.id) ? "Liked Direction" : "Like Direction"}
          </button>
        </article>
      `,
    )
    .join("");

  target.querySelectorAll(".rising-item").forEach((item) => {
    item.addEventListener("click", () => {
      state.activeClusterId = Number(item.dataset.clusterId);
      renderClusterList();
      renderClusterDetail();
    });
  });
  target.querySelectorAll("[data-cluster-like]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleLikedCluster(Number(button.dataset.clusterLike));
    });
  });
}

function renderRisingDirections() {
  const hasLikes = state.likedPaperIds.length > 0;
  const sourceClusters = currentClusterSource();
  const scopeIsFiltered = (!state.selectedVenues.includes("All") && state.selectedVenues.length > 0) || Boolean(state.selectedVenueYear);
  const hasDirectionLikes = state.likedClusterIds.length > 0;
  els.likelySubtitle.textContent = hasLikes || hasDirectionLikes
    ? "Based on the papers you liked so far"
    : scopeIsFiltered
      ? `No personal directions yet for ${currentScopeLabel()}`
      : "No personal directions yet. Like papers or directions first.";
  const likedDirections = sourceClusters.filter((cluster) => state.likedClusterIds.includes(cluster.id));
  renderDirectionCards(
    els.likelyList,
    likedDirections.length ? likedDirections : [],
  );
}

function trendExplanation(cluster) {
  if (cluster.trend_label === "hot") {
    return "This direction is hot. It already has large paper volume and citation weight, and it is still near its recent peak.";
  }
  if (cluster.trend_label === "rising") {
    return "This direction is rising. Recent paper output is clearly above its historical baseline and attention is building.";
  }
  if (cluster.trend_label === "stable") {
    return "This direction is stable. It remains important and active without a sharp acceleration.";
  }
  return "This direction is declining. It still matters, but recent activity is below its earlier peak.";
}

function renderStatCards(cluster) {
  const stats = [
    ["Trend Score", cluster.trend_score.toFixed(2)],
    ["Papers", fmt.format(cluster.paper_count)],
    ["Citations", fmt.format(cluster.total_citations)],
    ["Peak Period", cluster.peak_period || "N/A"],
  ];
  els.detailStats.innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderSignals(cluster) {
  const signals = [
    `${cluster.trend_reason || trendExplanation(cluster)} Scope: ${currentScopeLabel()}.`,
    `Representative scale: ${fmt.format(cluster.paper_count)} papers and ${fmt.format(cluster.total_citations)} citations in this domain.`,
    `Peak activity period: ${cluster.peak_period || "not identified yet"}.`,
    cluster.related_clusters?.length
      ? `Related clusters: ${cluster.related_clusters.join(", ")}.`
      : "No related-cluster geometry yet because 2D UMAP coordinates are missing.",
  ];
  els.signalList.innerHTML = signals.map((item) => `<li>${item}</li>`).join("");
}

function extractPaperKeywords(paper) {
  const text = `${paper.title || ""} ${paper.abstract || ""}`.toLowerCase();
  const stop = new Set(["the", "and", "for", "with", "from", "into", "using", "towards", "through", "large", "language", "models", "model", "paper"]);
  const counts = new Map();
  for (const token of text.match(/\b[a-z][a-z-]{3,}\b/g) || []) {
    if (stop.has(token)) continue;
    counts.set(token, (counts.get(token) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([token]) => token);
}

function paperOneWordSummary(paper) {
  return extractPaperKeywords(paper)[0] || "Topic";
}

function bindPaperCardActions(container) {
  container.querySelectorAll(".like-btn").forEach((button) => {
    if (button.dataset.paperId) {
      button.addEventListener("click", () => toggleLikedPaper(button.dataset.paperId));
    }
    if (button.dataset.paperSimilar) {
      button.addEventListener("click", () => loadSimilarPapers(button.dataset.paperSimilar));
    }
  });
}

function paperCardsMarkup(papers) {
  return papers
    .map(
      (paper) => {
        const keywords = extractPaperKeywords(paper);
        return `
        <article class="paper-item">
          <div class="paper-meta">
            <span>${paperOneWordSummary(paper)}</span>
            ${keywords.map((keyword) => `<span>${keyword}</span>`).join("")}
          </div>
          <a href="${paper.url}" target="_blank" rel="noreferrer">${paper.title}</a>
          <div class="paper-meta">
            <span>${paper.year}</span>
            <span>${fmt.format(paper.citation_count)} citations</span>
            <span>${paper.paper_id}</span>
          </div>
          <div class="paper-actions">
            <button class="like-btn ${state.likedPaperIds.includes(paper.paper_id) ? "active" : ""}" data-paper-id="${paper.paper_id}">
              ${state.likedPaperIds.includes(paper.paper_id) ? "Liked" : "Like"}
            </button>
            <button class="like-btn" data-paper-similar="${paper.paper_id}">Find Similar</button>
          </div>
        </article>
      `;
      },
    )
    .join("");
}

function renderPaperCards(papers) {
  els.paperList.innerHTML = paperCardsMarkup(papers);
  bindPaperCardActions(els.paperList);
}

function updateModalMoreButton(total = 0, loaded = 0) {
  const hasMore = loaded < total;
  els.modalMoreBtn.classList.toggle("hidden", !hasMore);
  els.modalMoreBtn.textContent = hasMore ? `Load More (${fmt.format(total - loaded)} left)` : "All Loaded";
}

function openPaperModal(title, subtitle, papers, modalSearch = null, total = papers.length) {
  els.modalTitle.textContent = title;
  els.modalSubtitle.textContent = subtitle;
  state.modalPapers = papers;
  state.modalSearch = modalSearch ? { ...modalSearch, total } : null;
  els.modalRefineInput.value = "";
  if (els.modalSortSelect) {
    els.modalSortSelect.value = state.modalSearch?.sortBy || "score";
  }
  els.modalPaperList.innerHTML = paperCardsMarkup(papers);
  bindPaperCardActions(els.modalPaperList);
  updateModalMoreButton(total, papers.length);
  els.paperModal.classList.remove("closing");
  els.paperModal.classList.remove("hidden");
  els.paperModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closePaperModal() {
  if (els.paperModal.classList.contains("hidden") || els.paperModal.classList.contains("closing")) {
    return;
  }
  els.paperModal.classList.add("closing");
  window.setTimeout(() => {
    els.paperModal.classList.add("hidden");
    els.paperModal.classList.remove("closing");
    els.paperModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    els.modalPaperList.innerHTML = "";
    state.modalPapers = [];
    state.modalSearch = null;
    updateModalMoreButton(0, 0);
  }, 220);
}

function refineModalResults() {
  const query = els.modalRefineInput.value.trim().toLowerCase();
  const filtered = !query
    ? state.modalPapers
    : state.modalPapers.filter((paper) => {
        const haystack = `${paper.title || ""} ${paper.abstract || ""} ${paper.paper_id || ""}`.toLowerCase();
        return haystack.includes(query);
      });
  els.modalPaperList.innerHTML = paperCardsMarkup(filtered);
  bindPaperCardActions(els.modalPaperList);
}

async function loadMoreModalResults() {
  if (!state.modalSearch) {
    return;
  }
  const params = new URLSearchParams({
    q: state.modalSearch.query,
    limit: String(state.modalSearch.limit),
    offset: String(state.modalSearch.offset),
    sort_by: state.modalSearch.sortBy || "score",
  });
  activeScopeParams().forEach((value, key) => params.set(key, value));
  const response = await fetchJson(`/api/papers/discover?${params.toString()}`);
  state.modalPapers = [...state.modalPapers, ...response.papers];
  state.modalSearch.offset += response.papers.length;
  els.modalPaperList.innerHTML = paperCardsMarkup(state.modalPapers);
  bindPaperCardActions(els.modalPaperList);
  updateModalMoreButton(response.total, state.modalPapers.length);
  els.modalSubtitle.textContent = `${response.total} matched papers for "${state.modalSearch.query}" in ${currentScopeLabel()}`;
}

async function ensureClusterPapers(clusterId) {
  const venueKey = state.selectedVenues.includes("All") || !state.selectedVenues.length
    ? "All"
    : state.selectedVenues.slice().sort().join("|");
  const scopeKey = `${clusterId}::${venueKey}::${state.selectedVenueYear || ""}`;
  if (state.clusterPapers[scopeKey]) {
    return state.clusterPapers[scopeKey];
  }
  const params = new URLSearchParams({ limit: "5000" });
  if (state.selectedVenues.length && !state.selectedVenues.includes("All")) {
    params.set("venues", state.selectedVenues.join(","));
    params.set("venue", state.selectedVenues[0]);
  } else if (state.selectedVenue && state.selectedVenue !== "All") {
    params.set("venue", state.selectedVenue);
  }
  if (state.selectedVenueYear) {
    params.set("year", state.selectedVenueYear);
  }
  const response = await fetchJson(`/api/clusters/${clusterId}/papers?${params.toString()}`);
  state.clusterPapers[scopeKey] = response.papers;
  return response.papers;
}

async function renderDomainPapers(cluster) {
  els.papersPanelTitle.textContent = `Papers In ${cluster.name}`;
  els.papersPanelSubtitle.textContent = `Sorted from high citation to low citation · ${currentScopeLabel()}`;
  const papers = await ensureClusterPapers(cluster.id);
  renderPaperCards(papers);
}

function renderVenueButtons() {
  const preferred = ["ACL", "EMNLP", "NAACL", "EACL", "COLING", "TACL", "Findings of ACL", "Findings of EMNLP"];
  const ordered = [
    { venue: "All", years: [] },
    ...state.venues.filter((item) => preferred.includes(item.venue)),
    ...state.venues.filter((item) => !preferred.includes(item.venue)),
  ];
  const primary = ordered.filter((item) => item.venue === "All" || preferred.includes(item.venue)).slice(0, 7);
  const extras = ordered
    .filter((item) => !primary.some((base) => base.venue === item.venue))
    .filter((item) => item.venue.toLowerCase().includes(state.venueSearchTerm.toLowerCase()));

  els.venueButtons.innerHTML = [
    ...primary.map(
      (item) => `
        <button class="venue-button ${(item.venue === "All" ? state.selectedVenues.includes("All") : state.selectedVenues.includes(item.venue)) ? "active" : ""}" data-venue="${item.venue}">
          ${item.venue}
        </button>
      `,
    ),
    `<button class="venue-button ${state.showMoreVenues ? "active" : ""}" data-venue-more="true">More</button>`,
  ]
    .join("");

  els.moreVenueButtons.innerHTML = extras
    .map(
      (item) => `
        <button class="venue-button ${state.selectedVenues.includes(item.venue) ? "active" : ""}" data-venue="${item.venue}">
          ${item.venue}
        </button>
      `,
    )
    .join("");

  const attachVenueClick = (container) => {
    container.querySelectorAll("[data-venue]").forEach((button) => {
      button.addEventListener("click", async () => {
        const venue = button.dataset.venue;
        if (venue === "All") {
          state.selectedVenues = ["All"];
          state.selectedVenue = "All";
        } else {
          const current = new Set(state.selectedVenues.filter((item) => item !== "All"));
          if (current.has(venue)) {
            current.delete(venue);
          } else {
            current.add(venue);
          }
          state.selectedVenues = current.size ? [...current] : ["All"];
          state.selectedVenue = state.selectedVenues.includes("All") ? "All" : state.selectedVenues[0];
        }
        state.selectedVenueYear = "";
        renderVenueButtons();
        renderVenueYearOptions();
        await loadVenuePapers();
      });
    });
  };

  attachVenueClick(els.venueButtons);
  attachVenueClick(els.moreVenueButtons);

  els.venueButtons.querySelector('[data-venue-more="true"]')?.addEventListener("click", () => {
    state.showMoreVenues = !state.showMoreVenues;
    renderVenueButtons();
  });

  els.moreVenueButtons.classList.toggle("hidden", !state.showMoreVenues);
  els.venueSearchWrap.classList.toggle("hidden", !state.showMoreVenues);
}

function renderVenueYearOptions() {
  if (state.selectedVenues.includes("All") || !state.selectedVenues.length) {
    els.venueYearFilter.innerHTML = '<option value="">All years</option>';
    return;
  }
  const years = [...new Set(
    state.venues
      .filter((item) => state.selectedVenues.includes(item.venue))
      .flatMap((item) => item.years || []),
  )].sort((a, b) => a - b);
  els.venueYearFilter.innerHTML = [
    '<option value="">All years</option>',
    ...years.map((year) => `<option value="${year}" ${String(state.selectedVenueYear) === String(year) ? "selected" : ""}>${year}</option>`),
  ].join("");
}

async function loadVenuePapers() {
  if (!state.selectedVenues.length) {
    return;
  }
  const usingAll = state.selectedVenues.includes("All");
  const params = new URLSearchParams({ venue: usingAll ? "All" : state.selectedVenues[0], limit: "500" });
  const fullParams = new URLSearchParams({ venue: usingAll ? "All" : state.selectedVenues[0], limit: "50000" });
  if (!usingAll) {
    params.set("venues", state.selectedVenues.join(","));
    fullParams.set("venues", state.selectedVenues.join(","));
  }
  if (state.selectedVenueYear) {
    params.set("year", state.selectedVenueYear);
    fullParams.set("year", state.selectedVenueYear);
  }
  const [response, fullResponse, clustersResponse] = await Promise.all([
    fetchJson(`/api/papers/by-venue?${params.toString()}`),
    fetchJson(`/api/papers/by-venue?${fullParams.toString()}`),
    fetchJson(`/api/trends/by-venue?${params.toString()}`),
  ]);
  state.venuePapers = response.papers;
  state.allVenuePapers = fullResponse.papers;
  state.venueScopedClusters = clustersResponse.clusters;
  state.visibleClusterCount = 8;
  const availableIds = new Set(state.venueScopedClusters.map((cluster) => cluster.id));
  if (!availableIds.has(state.activeClusterId)) {
    state.activeClusterId = state.venueScopedClusters[0]?.id ?? null;
  }
  const scopeLabel = currentScopeLabel();
  els.papersPanelTitle.textContent = `${scopeLabel} Papers`;
  els.papersPanelSubtitle.textContent = `Sorted from high citation to low citation · ${fmt.format(response.total)} papers matched`;
  renderPaperCards(response.papers);
  renderHeroMetrics();
  renderRisingDirections();
  renderClusterList();
  els.emptyState.classList.add("hidden");
  els.clusterDetail.classList.remove("hidden");
  await renderClusterDetail();
}

function wireVenueBrowser() {
  els.venueYearFilter.addEventListener("change", async () => {
    state.selectedVenueYear = els.venueYearFilter.value;
    await loadVenuePapers();
  });
  els.venueSearchInput?.addEventListener("input", () => {
    state.venueSearchTerm = els.venueSearchInput.value.trim();
    renderVenueButtons();
  });
}

async function runPaperSearch() {
  const query = els.paperSearchInput.value.trim();
  if (!query) {
    return;
  }
  const params = new URLSearchParams({ q: query, limit: "20", offset: "0", sort_by: "score" });
  activeScopeParams().forEach((value, key) => params.set(key, value));
  const response = await fetchJson(`/api/papers/discover?${params.toString()}`);
  openPaperModal(
    "Paper Discovery Results",
    `${response.total} matched papers for "${query}" in ${currentScopeLabel()}`,
    response.papers,
    { title: "Paper Discovery Results", query, limit: 20, offset: response.papers.length, sortBy: response.sort_by || "score" },
    response.total,
  );
}

async function runPaperNameSearch() {
  const query = els.paperNameSearchInput.value.trim();
  if (!query) {
    return;
  }
  const params = new URLSearchParams({ q: query, limit: "20", offset: "0", sort_by: "score" });
  activeScopeParams().forEach((value, key) => params.set(key, value));
  const response = await fetchJson(`/api/papers/discover?${params.toString()}`);
  openPaperModal(
    "Paper Name Results",
    `${response.total} matched papers for "${query}" in ${currentScopeLabel()}`,
    response.papers,
    { title: "Paper Name Results", query, limit: 20, offset: response.papers.length, sortBy: response.sort_by || "score" },
    response.total,
  );
}

function saveLikes() {
  localStorage.setItem("likedPaperIds", JSON.stringify(state.likedPaperIds));
}

function loadLikes() {
  try {
    return JSON.parse(localStorage.getItem("likedPaperIds") || "[]");
  } catch {
    return [];
  }
}

function loadLikedClusters() {
  try {
    return JSON.parse(localStorage.getItem("likedClusterIds") || "[]");
  } catch {
    return [];
  }
}

function saveLikedClusters() {
  localStorage.setItem("likedClusterIds", JSON.stringify(state.likedClusterIds));
}

async function refreshRecommendations() {
  if (!state.likedPaperIds.length && !state.likedClusterIds.length) {
    state.recommendations = [];
    renderRecommendations();
    return;
  }
  const response = await postJson("/api/recommendations", {
    liked_paper_ids: state.likedPaperIds,
    liked_cluster_ids: state.likedClusterIds,
    limit: 10,
  });
  state.recommendations = response.papers;
  renderRecommendations();
}

function renderRecommendations() {
  const likedPaperChips = state.likedPaperIds
    .map((paperId) => {
      const cluster = state.clusters.find((item) =>
        item.top_papers?.some((paper) => paper.paper_id === paperId),
      );
      const paper = cluster?.top_papers?.find((item) => item.paper_id === paperId);
      const label = paper ? paper.title : paperId;
      return `
        <span class="liked-chip">
          ${label}
          <button data-paper-id="${paperId}">Remove</button>
        </span>
      `;
    })
    .join("");
  const likedDirectionChips = state.likedClusterIds
    .map((clusterId) => {
      const cluster = state.clusters.find((item) => item.id === clusterId);
      if (!cluster) {
        return "";
      }
      return `
        <span class="liked-chip">
          ${cluster.name}
          <button data-cluster-id="${clusterId}">Remove</button>
        </span>
      `;
    })
    .join("");
  els.likedPapers.innerHTML = (likedPaperChips || likedDirectionChips)
    ? `
      <div>
        <strong>Liked Papers</strong>
        <div class="paper-actions">${likedPaperChips || "<p>No liked papers yet.</p>"}</div>
      </div>
      <div>
        <strong>Liked Directions</strong>
        <div class="paper-actions">${likedDirectionChips || "<p>No liked directions yet.</p>"}</div>
      </div>
    `
    : "<p>No liked signals yet.</p>";
  els.likedPapers.querySelectorAll("[data-paper-id]").forEach((button) => {
    button.addEventListener("click", () => toggleLikedPaper(button.dataset.paperId));
  });
  els.likedPapers.querySelectorAll("[data-cluster-id]").forEach((button) => {
    button.addEventListener("click", () => toggleLikedCluster(Number(button.dataset.clusterId)));
  });

  if (!state.recommendations.length) {
    els.recommendationList.innerHTML = "<p>No recommendations yet. Like a few papers to start.</p>";
    return;
  }

  els.recommendationList.innerHTML = state.recommendations
    .map(
      (paper) => `
        <article class="paper-item">
          <a href="${paper.url}" target="_blank" rel="noreferrer">${paper.title}</a>
          <div class="paper-meta">
            <span>${paper.year}</span>
            <span>${fmt.format(paper.citation_count)} citations</span>
            <span>score ${paper.recommendation_score.toFixed(3)}</span>
          </div>
          <div class="paper-actions">
            <button class="like-btn ${state.likedPaperIds.includes(paper.paper_id) ? "active" : ""}" data-paper-id="${paper.paper_id}">
              ${state.likedPaperIds.includes(paper.paper_id) ? "Liked" : "Like"}
            </button>
          </div>
        </article>
      `,
    )
    .join("");

  els.recommendationList.querySelectorAll(".like-btn").forEach((button) => {
    button.addEventListener("click", () => toggleLikedPaper(button.dataset.paperId));
  });
}

function toggleLikedPaper(paperId) {
  if (state.likedPaperIds.includes(paperId)) {
    state.likedPaperIds = state.likedPaperIds.filter((id) => id !== paperId);
  } else {
    state.likedPaperIds = [paperId, ...state.likedPaperIds].slice(0, 12);
  }
  saveLikes();
  renderRisingDirections();
  renderClusterDetail();
  refreshRecommendations().catch((error) => console.error(error));
}

function toggleLikedCluster(clusterId) {
  if (state.likedClusterIds.includes(clusterId)) {
    state.likedClusterIds = state.likedClusterIds.filter((id) => id !== clusterId);
  } else {
    state.likedClusterIds = [clusterId, ...state.likedClusterIds].slice(0, 12);
  }
  saveLikedClusters();
  renderClusterList();
  renderRisingDirections();
  refreshRecommendations().catch((error) => console.error(error));
}

async function loadSimilarPapers(paperId) {
  const response = await fetchJson(`/api/recommendations/similar/${paperId}?limit=12`);
  openPaperModal("Similar Papers", `Papers similar to ${paperId}`, response.papers, null, response.papers.length);
}

function wireLikesToolbar() {
  els.clearLikesBtn?.addEventListener("click", () => {
    state.likedPaperIds = [];
    state.likedClusterIds = [];
    saveLikes();
    saveLikedClusters();
    renderClusterDetail();
    refreshRecommendations().catch((error) => console.error(error));
  });
  els.likedPanelToggleBtn?.addEventListener("click", () => {
    state.likedPanelOpen = !state.likedPanelOpen;
    renderLikedPanelState();
  });
  els.likedPanelCloseBtn?.addEventListener("click", () => {
    state.likedPanelOpen = false;
    renderLikedPanelState();
  });
}

function renderLikedPanelState() {
  els.likedSidePanel?.classList.toggle("open", state.likedPanelOpen);
  els.likedSidePanel?.setAttribute("aria-hidden", state.likedPanelOpen ? "false" : "true");
  document.body.classList.toggle("liked-panel-open", state.likedPanelOpen);
  if (els.likedPanelToggleBtn) {
    els.likedPanelToggleBtn.textContent = state.likedPanelOpen ? "Hide Likes" : "Show Likes";
  }
}

function wireModal() {
  els.modalCloseBtn?.addEventListener("click", closePaperModal);
  els.modalBackdrop?.addEventListener("click", closePaperModal);
  els.modalRefineInput?.addEventListener("input", refineModalResults);
  els.modalSortSelect?.addEventListener("change", async () => {
    if (!state.modalSearch) {
      return;
    }
    state.modalSearch.sortBy = els.modalSortSelect.value;
    state.modalSearch.offset = 0;
    const params = new URLSearchParams({
      q: state.modalSearch.query,
      limit: String(state.modalSearch.limit),
      offset: "0",
      sort_by: state.modalSearch.sortBy,
    });
    activeScopeParams().forEach((value, key) => params.set(key, value));
    const response = await fetchJson(`/api/papers/discover?${params.toString()}`);
    state.modalPapers = response.papers;
    state.modalSearch.offset = response.papers.length;
    state.modalSearch.total = response.total;
    els.modalSubtitle.textContent = `${response.total} matched papers for "${state.modalSearch.query}" in ${currentScopeLabel()}`;
    refineModalResults();
    updateModalMoreButton(response.total, state.modalPapers.length);
  });
  els.modalMoreBtn?.addEventListener("click", () => {
    loadMoreModalResults().catch((error) => console.error(error));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.paperModal.classList.contains("hidden")) {
      closePaperModal();
    }
  });
}

async function renderTimeline(clusterId) {
  const params = activeScopeParams();
  params.set("cluster_id", String(clusterId));
  let periods = [];
  let series = [];

  try {
    const response = await fetchJson(`/api/trends/timeline?${params.toString()}`);
    periods = response.periods || [];
    series = response.series || [];
  } catch (error) {
    console.error(error);
  }

  if (!series.length || !periods.length) {
    periods = (state.periods || []).map((period) => String(period).split("-")[0]);
    const totals = periods.map((_, index) =>
      Object.values(state.series).reduce((sum, items) => sum + (items[index]?.paper_count || 0), 0),
    );
    series = (state.series[String(clusterId)] || []).map((item, index) => ({
      paper_count: Number(item.paper_count || 0),
      total_count: Number(totals[index] || 0),
      share: totals[index] > 0 ? Number(item.paper_count || 0) / totals[index] : 0,
    }));
  }

  if (!series.length || !periods.length) {
    els.timelineChart.innerHTML = "<p>No timeline data available.</p>";
    hideTimelineTooltip();
    return;
  }

  const values = series.map((item) => Number((item.share || 0) * 100));
  const max = Math.max(...values, 1);
  const width = 760;
  const height = 230;
  const padding = 24;
  const step = (width - padding * 2) / Math.max(values.length - 1, 1);

  const points = values.map((value, index) => {
    const x = padding + index * step;
    const y = height - padding - (value / max) * (height - padding * 2);
    return [x, y];
  });

  const d = points
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`)
    .join(" ");

  const labels = periods
    .map((period, index) => {
      const x = padding + index * step;
      return `<text class="axis-label" x="${x}" y="${height - 4}" text-anchor="middle">${period}</text>`;
    })
    .join("");

  const dots = points
    .map(([x, y], index) => `
      <g
        class="timeline-point"
        data-period="${periods[index]}"
        data-share="${values[index].toFixed(2)}"
        data-paper-count="${Number(series[index].paper_count || 0)}"
        data-total-count="${Number(series[index].total_count || 0)}"
      >
        <circle class="point-dot" cx="${x}" cy="${y}" r="4"></circle>
      </g>
    `)
    .join("");

  els.timelineChart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Trend timeline">
      <path class="line-path" d="${d}"></path>
      ${dots}
      ${labels}
    </svg>
  `;
  els.timelineChart.querySelectorAll(".timeline-point").forEach((point) => {
    point.addEventListener("mouseenter", (event) => {
      showTimelineTooltip(
        event,
        `venue total: ${point.dataset.totalCount}\ndomain total: ${point.dataset.paperCount}\n${point.dataset.share}%`,
      );
    });
    point.addEventListener("mouseleave", hideTimelineTooltip);
  });
}

function renderVenues(cluster, papers = []) {
  const scopedCounts = new Map();
  papers.forEach((paper) => {
    const venue = paper.venue || "Unknown";
    scopedCounts.set(venue, (scopedCounts.get(venue) || 0) + 1);
  });
  const venues = (scopedCounts.size ? [...scopedCounts.entries()] : Object.entries(cluster.top_venues || {})).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...venues.map(([, count]) => count), 1);
  els.venueList.innerHTML = venues
    .slice(0, 6)
    .map(
      ([venue, count]) => `
        <div class="venue-row">
          <strong>${venue}</strong>
          <span>${fmt.format(count)} papers</span>
          <div class="venue-bar"><span style="width:${(count / max) * 100}%"></span></div>
        </div>
      `,
    )
    .join("");
}

async function renderClusterDetail() {
  const cluster = currentClusterSource().find((item) => item.id === state.activeClusterId);
  if (!cluster) {
    els.emptyState.classList.remove("hidden");
    els.clusterDetail.classList.add("hidden");
    return;
  }

  els.emptyState.classList.add("hidden");
  els.clusterDetail.classList.remove("hidden");
  els.detailTrendBadge.className = trendClass(cluster.trend_label);
  els.detailTrendBadge.textContent = `${cluster.trend_label} · score ${cluster.trend_score.toFixed(2)}`;
  els.detailName.textContent = cluster.name;
  els.detailDescription.textContent = cluster.description;

  renderStatCards(cluster);
  await renderTimeline(cluster.id);
  const papers = await ensureClusterPapers(cluster.id);
  renderVenues(cluster, papers);
  renderSignals(cluster);
  await renderDomainPapers(cluster);
  renderRecommendations();
}

function wireFilters() {
  [els.searchInput, els.trendFilter, els.sortFilter].forEach((element) => {
    element.addEventListener("input", () => {
      state.visibleClusterCount = 8;
      renderClusterList();
      const filtered = getFilteredClusters();
      if (!filtered.some((cluster) => cluster.id === state.activeClusterId)) {
        state.activeClusterId = filtered[0]?.id ?? null;
      }
      renderClusterList();
      renderClusterDetail();
    });
  });
}

function wireClusterMore() {
  els.clusterMoreBtn?.addEventListener("click", () => {
    state.visibleClusterCount += 8;
    renderClusterList();
  });
}

function wirePaperSearch() {
  els.paperSearchBtn.addEventListener("click", () => {
    setButtonLoading(els.paperSearchBtn, true);
    runPaperSearch()
      .catch((error) => console.error(error))
      .finally(() => setButtonLoading(els.paperSearchBtn, false));
  });
  els.paperSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      setButtonLoading(els.paperSearchBtn, true);
      runPaperSearch()
        .catch((error) => console.error(error))
        .finally(() => setButtonLoading(els.paperSearchBtn, false));
    }
  });
  els.paperNameSearchBtn.addEventListener("click", () => {
    runPaperNameSearch().catch((error) => console.error(error));
  });
  els.paperNameSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runPaperNameSearch().catch((error) => console.error(error));
    }
  });
}

async function init() {
  const [clustersResponse, timelineResponse, likelyResponse, risingResponse, venuesResponse] = await Promise.all([
    fetchJson("/api/clusters?limit=500"),
    fetchJson("/api/trends/timeline"),
    fetchJson("/api/trends/likely?limit=6"),
    fetchJson("/api/trends/rising?limit=8"),
    fetchJson("/api/papers/venues"),
  ]);

  state.clusters = clustersResponse.clusters;
  state.periods = timelineResponse.periods;
  state.series = timelineResponse.series;
  state.likelyClusters = likelyResponse.clusters;
  state.risingClusters = risingResponse.clusters;
  state.venues = venuesResponse.venues;
  state.likedClusterIds = loadLikedClusters();
  state.likedPaperIds = loadLikes();
  state.selectedVenue = "All";
  state.selectedVenues = ["All"];
  state.activeClusterId = getFilteredClusters()[0]?.id ?? null;
  state.venueScopedClusters = [...state.clusters];

  renderHeroMetrics();
  wireFilters();
  wireVenueBrowser();
  wirePaperSearch();
  wireLikesToolbar();
  wireModal();
  wireClusterMore();
  renderLikedPanelState();
  renderVenueButtons();
  renderVenueYearOptions();
  renderRisingDirections();
  renderClusterList();
  await renderClusterDetail();
  await refreshRecommendations();
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<main class="page-shell"><section class="panel"><h1>Failed to load explorer</h1><p>${error.message}</p></section></main>`;
});
