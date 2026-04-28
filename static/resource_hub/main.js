/* =============================================
   Resource Hub — main.js
   Handles: search, filters, bookmarks, progress,
            YouTube search, skill gaps
   ============================================= */

const API = {
  BASE: '/api',
  CSRF: () => document.querySelector('[name=csrfmiddlewaretoken]')?.value
    || getCookie('csrftoken'),

  async get(path) {
    const r = await fetch(`${API.BASE}${path}`, {
      headers: { 'Accept': 'application/json' }
    });
    if (!r.ok) throw new Error(`GET ${path} failed: ${r.status}`);
    return r.json();
  },

  async post(path, body = {}) {
    const r = await fetch(`${API.BASE}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': API.CSRF()
      },
      body: JSON.stringify(body)
    });
    return r;
  },

  async delete(path) {
    const r = await fetch(`${API.BASE}${path}`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': API.CSRF() }
    });
    return r;
  }
};

function getCookie(name) {
  const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return v ? v[2] : null;
}

/* ---- Loading overlay ---- */
const loading = {
  el: document.getElementById('loading-overlay'),
  show() { this.el?.classList.add('active'); },
  hide() { this.el?.classList.remove('active'); }
};

/* ---- Toast notifications ---- */
function toast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `alert alert-${type}`;
  t.style.cssText = `
    position:fixed; bottom:24px; right:24px; z-index:9999;
    min-width:260px; animation:fadeUp .3s ease;
    box-shadow:0 8px 32px rgba(0,0,0,0.4);
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

/* ================================================
   INDEX PAGE — search + filters + resource cards
   ================================================ */
class IndexPage {
  constructor() {
    this.searchInput = document.getElementById('search-input');
    this.searchBtn   = document.getElementById('search-btn');
    this.categorySel = document.getElementById('filter-category');
    this.levelSel    = document.getElementById('filter-level');
    this.platformSel = document.getElementById('filter-platform');
    this.typeSel     = document.getElementById('filter-type');
    this.resultsGrid = document.getElementById('resources-grid');
    this.resultsCount= document.getElementById('results-count');
    this.ytGrid      = document.getElementById('yt-grid');
    this.ytSection   = document.getElementById('yt-section');
    this.ytSearchBtn = document.getElementById('yt-search-btn');

    if (!this.searchInput) return;
    this.init();
  }

  init() {
    // Search on enter or button
    this.searchInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') this.runSearch();
    });
    this.searchBtn?.addEventListener('click', () => this.runSearch());

    // Filter chips
    document.querySelectorAll('.filter-chip[data-filter]').forEach(chip => {
      chip.addEventListener('click', () => {
        const group = chip.dataset.group;
        document.querySelectorAll(`.filter-chip[data-group="${group}"]`)
          .forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.runSearch();
      });
    });

    // Selects auto-search
    [this.categorySel, this.levelSel, this.platformSel, this.typeSel]
      .filter(Boolean)
      .forEach(el => el.addEventListener('change', () => this.runSearch()));

    // YouTube search button
    this.ytSearchBtn?.addEventListener('click', () => {
      const q = this.searchInput.value.trim();
      if (q) this.runYouTubeSearch(q);
    });

    // Initial load
    this.runSearch();
  }

  buildParams() {
    const p = new URLSearchParams();
    const q = this.searchInput?.value.trim();
    if (q) p.set('search', q);
    if (this.categorySel?.value) p.set('category', this.categorySel.value);
    if (this.levelSel?.value)    p.set('level',    this.levelSel.value);
    if (this.platformSel?.value) p.set('platform', this.platformSel.value);
    if (this.typeSel?.value)     p.set('resource_type', this.typeSel.value);

    // Active filter chips
    document.querySelectorAll('.filter-chip.active[data-value]').forEach(chip => {
      p.set(chip.dataset.filter, chip.dataset.value);
    });

    return p.toString();
  }

  async runSearch() {
    loading.show();
    try {
      const params = this.buildParams();
      const data = await API.get(`/resources/?${params}`);
      const results = Array.isArray(data) ? data : (data.results ?? []);
      this.renderResources(results);
      if (this.resultsCount)
        this.resultsCount.textContent = `${results.length} resource${results.length !== 1 ? 's' : ''}`;
    } catch (e) {
      console.error(e);
      toast('Failed to load resources', 'error');
    } finally {
      loading.hide();
    }
  }

  renderResources(list) {
    if (!this.resultsGrid) return;
    if (!list.length) {
      this.resultsGrid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="empty-icon">🔍</div>
          <h3>No resources found</h3>
          <p>Try different keywords or remove some filters</p>
        </div>`;
      return;
    }
    this.resultsGrid.innerHTML = list.map((r, i) => resourceCardHTML(r, i)).join('');
    attachBookmarkListeners(this.resultsGrid);
    attachProgressListeners(this.resultsGrid);
  }

  async runYouTubeSearch(q) {
    if (!this.ytGrid) return;
    loading.show();
    try {
      const data = await API.get(`/youtube/search/?q=${encodeURIComponent(q)}`);
      const videos = data.videos ?? data ?? [];
      if (this.ytSection) this.ytSection.style.display = 'block';
      this.ytGrid.innerHTML = videos.length
        ? videos.map(v => `
            <a class="yt-card" href="https://youtube.com/watch?v=${v.video_id}" target="_blank" rel="noopener">
              <img class="yt-thumb" src="${v.thumbnail}" alt="${escapeHTML(v.title)}"
                   onerror="this.parentElement.innerHTML='<div class=yt-thumb-placeholder>▶️</div>'">
              <div class="yt-card-body">
                <div class="yt-title">${escapeHTML(v.title)}</div>
                <div class="yt-channel">${escapeHTML(v.channel || '')}</div>
              </div>
            </a>`).join('')
        : '<p style="color:var(--text-muted);font-size:13px">No YouTube results found.</p>';
    } catch (e) {
      toast('YouTube search unavailable', 'error');
    } finally {
      loading.hide();
    }
  }
}

/* ================================================
   BOOKMARKS PAGE
   ================================================ */
class BookmarksPage {
  constructor() {
    this.grid = document.getElementById('bookmarks-grid');
    if (!this.grid) return;
    this.load();
  }

  async load() {
    loading.show();
    try {
      const data = await API.get('/bookmarks/');
      const list = Array.isArray(data) ? data : (data.results ?? []);
      if (!list.length) {
        this.grid.innerHTML = `
          <div class="empty-state" style="grid-column:1/-1">
            <div class="empty-icon">🔖</div>
            <h3>No bookmarks yet</h3>
            <p>Start exploring resources and save the ones you like</p>
            <a href="/" class="btn-primary" style="margin-top:16px;display:inline-flex">Browse Resources</a>
          </div>`;
        return;
      }
      // bookmarks API returns [{resource: {...}}, ...]
      const resources = list.map(b => b.resource ?? b);
      this.grid.innerHTML = resources.map((r, i) => resourceCardHTML(r, i)).join('');
      attachBookmarkListeners(this.grid);
    } catch (e) {
      toast('Failed to load bookmarks', 'error');
    } finally {
      loading.hide();
    }
  }
}

/* ================================================
   SKILL GAPS PAGE
   ================================================ */
class SkillGapsPage {
  constructor() {
    this.cloud   = document.getElementById('skills-cloud');
    this.input   = document.getElementById('skill-input');
    this.addBtn  = document.getElementById('add-skill-btn');
    this.recGrid = document.getElementById('skill-rec-grid');
    if (!this.cloud) return;
    this.skills = [];
    this.load();
    this.addBtn?.addEventListener('click', () => this.addSkill());
    this.input?.addEventListener('keydown', e => { if (e.key === 'Enter') this.addSkill(); });
  }

  async load() {
    try {
      const data = await API.get('/skill-gaps/');
      this.skills = Array.isArray(data) ? data : (data.results ?? []);
      this.render();
      if (this.skills.length) this.loadRecs();
    } catch (e) { console.error(e); }
  }

  render() {
    if (!this.cloud) return;
    if (!this.skills.length) {
      this.cloud.innerHTML = '<p style="color:var(--text-muted);font-size:13px">No skill gaps added yet.</p>';
      return;
    }
    this.cloud.innerHTML = this.skills.map(s => `
      <span class="skill-tag" data-id="${s.id}">
        ${escapeHTML(s.skill_name)}
        <button class="remove-btn" onclick="skillGapsPage.removeSkill(${s.id})">×</button>
      </span>`).join('');
  }

  async addSkill() {
    const name = this.input?.value.trim();
    if (!name) return;
    try {
      const r = await API.post('/skill-gaps/', { skill_name: name });
      if (r.ok) {
        this.input.value = '';
        await this.load();
        toast(`Added: ${name}`, 'success');
      } else {
        const err = await r.json();
        toast(err.skill_name?.[0] || 'Could not add skill', 'error');
      }
    } catch (e) { toast('Error adding skill', 'error'); }
  }

  async removeSkill(id) {
    try {
      const r = await API.delete(`/skill-gaps/${id}/`);
      if (r.ok) {
        this.skills = this.skills.filter(s => s.id !== id);
        this.render();
        toast('Skill removed', 'info');
      }
    } catch (e) { toast('Error removing skill', 'error'); }
  }

  async loadRecs() {
    if (!this.recGrid) return;
    const names = this.skills.map(s => s.skill_name).join(',');
    try {
      const data = await API.get(`/resources/?search=${encodeURIComponent(names)}`);
      const list = Array.isArray(data) ? data : (data.results ?? []);
      this.recGrid.innerHTML = list.slice(0, 6).map((r, i) => resourceCardHTML(r, i)).join('');
      attachBookmarkListeners(this.recGrid);
    } catch (e) { console.error(e); }
  }
}

/* ================================================
   SHARED HELPERS
   ================================================ */

function resourceCardHTML(r, i = 0) {
 const thumbIcon = platformIcon(r.platform);
 const thumb = r.thumbnail_url
    ? `<img class="resource-thumbnail" src="${escapeHTML(r.thumbnail_url)}" alt=""
         onerror="this.parentNode.innerHTML='<div class=resource-thumbnail>${thumbIcon.replace(/'/g, '').replace(/"/g, '')}</div>'">`
    : `<div class="resource-thumbnail" style="display:flex;align-items:center;justify-content:center">${thumbIcon}</div>`; 
  const bookmarked = r.is_bookmarked ? 'bookmarked' : '';
  const progress = r.user_progress?.status ?? 'not_started';
  const progPct = progress === 'completed' ? 100 : progress === 'in_progress' ? 50 : 0;
  const tags = Array.isArray(r.tags_list) ? r.tags_list.slice(0, 3) : [];

  return `
  <div class="resource-card fade-up fade-up-${Math.min(i + 1, 5)}" data-id="${r.id}">
    <div class="resource-card-top">
      ${thumb}
      <div style="flex:1;min-width:0">
        <div class="resource-badge-row">
          ${r.is_free ? '<span class="badge badge-free">Free</span>' : '<span class="badge badge-paid">Paid</span>'}
          ${r.level ? `<span class="badge badge-level">${capitalize(r.level)}</span>` : ''}
          ${r.resource_type ? `<span class="badge badge-type">${capitalize(r.resource_type)}</span>` : ''}
        </div>
      </div>
      <button class="bookmark-btn ${bookmarked}" data-id="${r.id}" title="Bookmark">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="${r.is_bookmarked ? 'currentColor' : 'none'}" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="1.7"/>
        </svg>
      </button>
    </div>

    <div class="resource-title">${escapeHTML(r.title)}</div>
    <div class="resource-desc">${escapeHTML(r.description || '')}</div>

    ${tags.length ? `<div style="display:flex;gap:5px;flex-wrap:wrap">${tags.map(t => `<span style="font-size:11px;padding:2px 8px;border-radius:999px;background:rgba(255,255,255,0.05);color:var(--text-muted)">#${escapeHTML(t)}</span>`).join('')}</div>` : ''}

    ${progPct > 0 ? `
    <div>
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:4px">
        <span style="display:flex;align-items:center;gap:4px">
          ${progress === 'completed'
            ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="#3FB950" stroke-width="2" stroke-linecap="round"/></svg> Completed`
            : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> In Progress`
          }
        </span>
        <span>${progPct}%</span>
      </div>
      <div class="progress-bar-wrap">
        <div class="progress-bar-fill" style="width:${progPct}%"></div>
      </div>
    </div>` : ''}

    <div class="resource-meta">
      <span style="display:flex;align-items:center;gap:4px">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/></svg>
        ${r.view_count ?? 0}
      </span>
      ${r.duration ? `<span style="display:flex;align-items:center;gap:4px">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        ${escapeHTML(r.duration)}
      </span>` : ''}
    </div>

    <div class="resource-footer">
      <span class="platform-pill">${escapeHTML(r.platform || 'Web')}</span>
      <div style="display:flex;gap:8px;align-items:center">
        <select class="progress-sel" data-id="${r.id}" style="padding:5px 10px;background:var(--bg-card);border:1px solid var(--border-glass);border-radius:var(--radius-sm);color:var(--text-muted);font-size:11px;outline:none;cursor:pointer">
          <option value="not_started" ${progress==='not_started'?'selected':''}>Not Started</option>
          <option value="in_progress" ${progress==='in_progress'?'selected':''}>In Progress</option>
          <option value="completed"   ${progress==='completed'?'selected':''}>Completed</option>
        </select>
        <a class="btn-visit" href="${escapeHTML(r.url)}" target="_blank" rel="noopener">Visit ↗</a>
      </div>
    </div>
  </div>`;
}

function attachBookmarkListeners(container) {
  container.querySelectorAll('.bookmark-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const isBookmarked = btn.classList.contains('bookmarked');
      try {
        let r;
        if (isBookmarked) {
          r = await API.delete(`/resources/${id}/bookmark/`);
        } else {
          r = await API.post(`/resources/${id}/bookmark/`);
        }
        if (r.ok) {
          btn.classList.toggle('bookmarked');
         const svg = btn.querySelector('svg');
        if (svg) svg.setAttribute('fill', btn.classList.contains('bookmarked') ? 'currentColor' : 'none');
          toast(isBookmarked ? 'Bookmark removed' : 'Bookmarked! ', isBookmarked ? 'info' : 'success');
        }
      } catch (e) { toast('Login required to bookmark', 'error'); }
    });
  });
}

function attachProgressListeners(container) {
  container.querySelectorAll('.progress-sel').forEach(sel => {
    sel.addEventListener('change', async () => {
      const id = sel.dataset.id;
      try {
        const r = await API.post(`/resources/${id}/progress/`, { status: sel.value });
        if (r.ok) toast('Progress updated ✓', 'success');
      } catch (e) { toast('Login required', 'error'); }
    });
  });
}

function platformIcon(platform) {
  const p = (platform || '').toLowerCase();
  const icons = {
    youtube:      `<svg width="22" height="22" viewBox="0 0 24 24" fill="#FF0000"><path d="M23 7s-.3-2-1.2-2.8c-1.1-1.2-2.4-1.2-3-1.3C16.1 2.8 12 2.8 12 2.8s-4.1 0-6.8.1c-.6.1-1.9.1-3 1.3C1.3 5 1 7 1 7S.7 9.1.7 11.3v2c0 2.1.3 4.3.3 4.3s.3 2 1.2 2.8c1.1 1.2 2.6 1.1 3.3 1.2C7.5 21.8 12 21.8 12 21.8s4.1 0 6.8-.2c.6-.1 1.9-.1 3-1.3.9-.8 1.2-2.8 1.2-2.8s.3-2.1.3-4.3v-2C23.3 9.1 23 7 23 7zm-13.5 8.7V8.3l8 3.7-8 3.7z"/></svg>`,
    freecodecamp: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M5 9l-3 3 3 3M19 9l3 3-3 3M14 4l-4 16" stroke="#00D4FF" stroke-width="2" stroke-linecap="round"/></svg>`,
    google:       `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/><path d="M3 12h18M12 3c-2.5 3-4 5.5-4 9s1.5 6 4 9M12 3c2.5 3 4 5.5 4 9s-1.5 6-4 9" stroke="currentColor" stroke-width="1.7"/></svg>`,
    kaggle:       `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 3v18h18" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><path d="M7 16l4-4 4 4 4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`,
    flutter:      `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M14 2L4 12l3 3 7-7zM14 22l-4-4 2-2 6 6z" stroke="#00D4FF" stroke-width="1.7"/></svg>`,
    aws:          `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M18 10a6 6 0 1 0-11.9 1A4 4 0 1 0 8 19h10a4 4 0 0 0 0-8h-.5z" stroke="currentColor" stroke-width="1.7"/></svg>`,
    'mit ocw':    `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="2" y="4" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.7"/><path d="M8 20h8M12 18v2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`,
    'harvard cs50':`<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 3L2 9l10 6 10-6-10-6zM2 15l10 6 10-6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    'khan academy':`<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" stroke="currentColor" stroke-width="1.7"/></svg>`,
    'fast.ai':    `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M13 2 4 14h7l-1 8 10-13h-7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`,
    'the odin project': `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.7"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`,
    'microsoft learn': `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.7"/><rect x="13" y="3" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.7"/><rect x="3" y="13" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.7"/><rect x="13" y="13" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.7"/></svg>`,
  };
  return icons[p] || `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 5h7a4 4 0 0 1 4 4v10H8a4 4 0 0 0-4 4z" stroke="currentColor" stroke-width="1.7"/><path d="M20 5h-7a4 4 0 0 0-4 4v10h7a4 4 0 0 1 4 4z" stroke="currentColor" stroke-width="1.7"/></svg>`;
}

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

/* ---- Boot ---- */
let skillGapsPage;
document.addEventListener('DOMContentLoaded', () => {
  new IndexPage();
  new BookmarksPage();
  skillGapsPage = new SkillGapsPage();
});