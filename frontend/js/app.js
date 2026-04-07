'use strict';

// ─── Constants ────────────────────────────────────────────────────────────────
const API_ARTICLES    = '/api/articles';
const API_SCRAPE      = '/api/scrape';
const LS_SAVED_KEY    = 'footy_saved_ids';
const AUTO_REFRESH_MS = 24 * 60 * 60 * 1000;

const SOURCE_LABELS = {
  bbc_sport: 'BBC Sport',
  fotmob:    'Fotmob',
};

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  articles:     [],
  savedIds:     new Set(),
  activeFilter: 'all',
  lastUpdated:  null,
  loading:      false,
  refreshTimer: null,
};

// ─── DOM ──────────────────────────────────────────────────────────────────────
const $grid         = document.getElementById('articles-grid');
const $count        = document.getElementById('article-count');
const $lastUpdated  = document.getElementById('last-updated-text');
const $btnRefresh   = document.getElementById('btn-refresh');
const $toastCont    = document.getElementById('toast-container');
const $savedList    = document.getElementById('saved-list');
const $sectionTitle = document.getElementById('section-title');
const $breadcrumb   = document.getElementById('breadcrumb-label');

const $statTotal  = document.getElementById('stat-total');
const $statBbc    = document.getElementById('stat-bbc');
const $statFotmob = document.getElementById('stat-fotmob');
const $statSaved  = document.getElementById('stat-saved');

const $badgeAll    = document.getElementById('badge-all');
const $badgeBbc    = document.getElementById('badge-bbc');
const $badgeFotmob = document.getElementById('badge-fotmob');
const $badgeSaved  = document.getElementById('badge-saved');

// ─── localStorage ─────────────────────────────────────────────────────────────
function loadSavedIds() {
  try {
    const raw = localStorage.getItem(LS_SAVED_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch { return new Set(); }
}

function persistSavedIds() {
  try {
    localStorage.setItem(LS_SAVED_KEY, JSON.stringify([...state.savedIds]));
  } catch (e) { console.warn('localStorage write failed:', e); }
}

// ─── API ──────────────────────────────────────────────────────────────────────
async function fetchArticles() {
  const r = await fetch(API_ARTICLES);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function triggerScrape() {
  const r = await fetch(API_SCRAPE, { method: 'POST' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ─── Load ─────────────────────────────────────────────────────────────────────
async function loadData(showSkel = true) {
  if (state.loading) return;
  state.loading = true;
  if (showSkel) renderSkeletons(9);
  try {
    const payload = await fetchArticles();
    applyPayload(payload);
  } catch (err) {
    console.error(err);
    renderEmpty('Could not load articles', 'Is the server running? Try: python3 tools/server.py');
    showToast('⚠️ Failed to load articles', 'error');
  } finally {
    state.loading = false;
  }
}

async function handleRefresh() {
  if (state.loading) return;
  state.loading = true;
  $btnRefresh.classList.add('loading');
  $btnRefresh.disabled = true;
  showToast('🔄 Fetching latest articles…', 'info');
  try {
    const payload = await triggerScrape();
    applyPayload(payload);
    scheduleAutoRefresh();
    showToast('✅ Feed updated!', 'success');
  } catch (err) {
    console.error(err);
    showToast('❌ Refresh failed', 'error');
  } finally {
    $btnRefresh.classList.remove('loading');
    $btnRefresh.disabled = false;
    state.loading = false;
  }
}

// ─── Apply Payload ────────────────────────────────────────────────────────────
function applyPayload(payload) {
  state.articles    = (payload.articles || []).map(a => ({ ...a, saved: state.savedIds.has(a.id) }));
  state.lastUpdated = payload.last_updated;
  updateStats();
  updateLastUpdated(payload.last_updated);
  render();
  renderSavedSidebar();
}

// ─── Stats ────────────────────────────────────────────────────────────────────
function updateStats() {
  const total = state.articles.length;
  const bbc   = state.articles.filter(a => a.source === 'bbc_sport').length;
  const fm    = state.articles.filter(a => a.source === 'fotmob').length;
  const saved = state.savedIds.size;

  animCount($statTotal,  total);
  animCount($statBbc,    bbc);
  animCount($statFotmob, fm);
  animCount($statSaved,  saved);

  $badgeAll.textContent    = total;
  $badgeBbc.textContent    = bbc;
  $badgeFotmob.textContent = fm;
  $badgeSaved.textContent  = saved;
}

function animCount(el, target) {
  if (!el) return;
  const start = parseInt(el.textContent) || 0;
  if (start === target) { el.textContent = target; return; }
  let step = 0, steps = 18;
  const t = setInterval(() => {
    step++;
    el.textContent = Math.round(start + (target - start) * (step / steps));
    if (step >= steps) { el.textContent = target; clearInterval(t); }
  }, 380 / steps);
}

// ─── Timestamp ────────────────────────────────────────────────────────────────
function updateLastUpdated(iso) {
  if (!iso) { $lastUpdated.textContent = 'Never refreshed'; return; }
  $lastUpdated.textContent = `Updated ${fmtRel(new Date(iso))}`;
}

function fmtRel(date) {
  const s = (Date.now() - date.getTime()) / 1000;
  if (s < 60)    return 'just now';
  if (s < 3600)  return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return date.toLocaleDateString();
}

// ─── Filter ───────────────────────────────────────────────────────────────────
function setFilter(filter) {
  state.activeFilter = filter;
  document.querySelectorAll('.nav-item').forEach(btn => {
    const active = btn.dataset.filter === filter;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });

  const labels = {
    all:       'Latest Articles',
    bbc_sport: 'BBC Sport',
    fotmob:    'Fotmob',
    saved:     'Saved Articles',
  };
  $sectionTitle.textContent = labels[filter] || 'Articles';
  $breadcrumb.textContent   = labels[filter] || 'Articles';
  render();
}

function filtered() {
  const { articles, activeFilter, savedIds } = state;
  if (activeFilter === 'bbc_sport') return articles.filter(a => a.source === 'bbc_sport');
  if (activeFilter === 'fotmob')    return articles.filter(a => a.source === 'fotmob');
  if (activeFilter === 'saved')     return articles.filter(a => savedIds.has(a.id));
  return articles;
}

// ─── Save ─────────────────────────────────────────────────────────────────────
function toggleSave(id) {
  const was = state.savedIds.has(id);
  was ? state.savedIds.delete(id) : state.savedIds.add(id);
  persistSavedIds();
  updateStats();
  renderSavedSidebar();
  showToast(was ? 'Removed from saved' : '⭐ Saved!', was ? 'info' : 'success');

  // Update cards with this id
  $grid.querySelectorAll(`[data-id="${id}"]`).forEach(card => applyCardSave(card, !was));

  // If viewing saved and unsaving — animate out
  if (state.activeFilter === 'saved' && was) {
    $grid.querySelectorAll(`[data-id="${id}"]`).forEach(card => {
      card.style.transition = 'opacity .2s, transform .2s';
      card.style.opacity    = '0';
      card.style.transform  = 'scale(0.95) translateY(8px)';
      setTimeout(render, 230);
    });
  }
}

function applyCardSave(card, saved) {
  card.classList.toggle('saved', saved);
  const btn = card.querySelector('.card-save');
  if (btn) {
    btn.classList.toggle('active', saved);
    btn.textContent = saved ? '⭐' : '🔖';
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from saved' : 'Save article');
  }
}

// ─── Sidebar saved list ────────────────────────────────────────────────────
function renderSavedSidebar() {
  const savedArticles = state.articles.filter(a => state.savedIds.has(a.id));
  if (savedArticles.length === 0) {
    $savedList.innerHTML = '<li class="saved-empty">No saved articles yet</li>';
    return;
  }

  $savedList.innerHTML = savedArticles.map(a => `
    <li class="saved-list-item" data-url="${esc(a.url)}" tabindex="0" role="listitem">
      ${a.image_url
        ? `<img class="saved-list-thumb" src="${esc(a.image_url)}" alt="" loading="lazy" />`
        : `<div class="saved-list-thumb" style="display:flex;align-items:center;justify-content:center;font-size:18px;opacity:.4">⚽</div>`
      }
      <span class="saved-list-title">${esc(a.title)}</span>
    </li>
  `).join('');

  $savedList.querySelectorAll('.saved-list-item').forEach(item => {
    item.addEventListener('click', () => window.open(item.dataset.url, '_blank', 'noopener'));
  });
}

// ─── Render ───────────────────────────────────────────────────────────────────
function render() {
  const arts = filtered();
  $count.textContent = `(${arts.length})`;

  if (arts.length === 0) {
    if (state.activeFilter === 'saved') {
      renderEmpty('No saved articles', 'Hit the 🔖 icon on any card to save it here.');
    } else {
      renderEmpty('No articles found', 'Try refreshing — articles older than 24h are hidden.');
    }
    return;
  }

  $grid.innerHTML = '';
  arts.forEach((a, i) => {
    const card = buildCard(a);
    card.style.animationDelay = `${Math.min(i * 35, 350)}ms`;
    $grid.appendChild(card);
  });
}

function renderSkeletons(n) {
  $grid.innerHTML = '';
  for (let i = 0; i < n; i++) {
    $grid.innerHTML += `
      <div class="skeleton">
        <div class="skeleton-img"><div class="skel img"></div></div>
        <div class="skeleton-body">
          <div class="skel h14 w100"></div>
          <div class="skel h14 w100"></div>
          <div class="skel h14 w70"></div>
          <div class="skel h12 w45" style="margin-top:4px"></div>
        </div>
      </div>`;
  }
}

function renderEmpty(title, sub = '') {
  $grid.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">⚽</div>
      <p class="empty-title">${esc(title)}</p>
      ${sub ? `<p class="empty-sub">${esc(sub)}</p>` : ''}
    </div>`;
}

// ─── Build Card ───────────────────────────────────────────────────────────────
function buildCard(a) {
  const saved       = state.savedIds.has(a.id);
  const sourceLabel = SOURCE_LABELS[a.source] || a.source;
  const timeAgo     = fmtTime(a.published_at);

  const card = document.createElement('article');
  card.className = `article-card${saved ? ' saved' : ''}`;
  card.dataset.id = a.id;
  card.setAttribute('role', 'article');

  card.innerHTML = `
    <div class="card-img-wrap">
      ${a.image_url
        ? `<img class="card-img" src="${esc(a.image_url)}" alt="${esc(a.title)}" loading="lazy" />`
        : `<div class="card-no-img">⚽</div>`}
      <span class="card-source source-${esc(a.source)}">${esc(sourceLabel)}</span>
      <button
        class="card-save${saved ? ' active' : ''}"
        data-id="${esc(a.id)}"
        aria-label="${saved ? 'Remove from saved' : 'Save article'}"
        aria-pressed="${saved}"
      >${saved ? '⭐' : '🔖'}</button>
      <div class="card-saved-bar" aria-hidden="true"></div>
    </div>
    <div class="card-body">
      <h2 class="card-title">${esc(a.title)}</h2>
      ${a.summary ? `<p class="card-summary">${esc(a.summary)}</p>` : ''}
      <div class="card-footer">
        <span class="card-time">🕐 ${esc(timeAgo)}</span>
        <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer" class="card-link"
           aria-label="Read full article">Read more →</a>
      </div>
    </div>`;

  card.querySelector('.card-save').addEventListener('click', e => {
    e.stopPropagation();
    toggleSave(a.id);
  });

  card.addEventListener('click', evt => {
    if (!evt.target.closest('.card-save') && !evt.target.closest('.card-link')) {
      window.open(a.url, '_blank', 'noopener,noreferrer');
    }
  });

  return card;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmtTime(iso) {
  try { return fmtRel(new Date(iso)); } catch { return ''; }
}

function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  $toastCont.appendChild(t);
  setTimeout(() => { t.classList.add('exit'); setTimeout(() => t.remove(), 250); }, 3000);
}

// ─── Auto-refresh ─────────────────────────────────────────────────────────────
function scheduleAutoRefresh() {
  clearTimeout(state.refreshTimer);
  state.refreshTimer = setTimeout(() => handleRefresh(), AUTO_REFRESH_MS);
}

// ─── Event Listeners ─────────────────────────────────────────────────────────
$btnRefresh.addEventListener('click', handleRefresh);

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => setFilter(btn.dataset.filter));
});

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  state.savedIds = loadSavedIds();
  await loadData(true);
  scheduleAutoRefresh();
  // Refresh timestamps every 60s
  setInterval(() => {
    updateLastUpdated(state.lastUpdated);
    $grid.querySelectorAll('time').forEach(el =>
      el.textContent = fmtRel(new Date(el.getAttribute('datetime')))
    );
  }, 60_000);
}

init();
