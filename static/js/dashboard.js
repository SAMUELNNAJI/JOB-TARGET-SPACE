const dashboardMenu = document.querySelector('.dashboard-mobile-menu');
const dashboardSidebar = document.querySelector('.dashboard-sidebar');

dashboardMenu?.addEventListener('click', () => {
  dashboardSidebar?.classList.toggle('open');
});

document.addEventListener('click', event => {
  if (!dashboardSidebar?.classList.contains('open')) return;
  if (!dashboardSidebar.contains(event.target) && !dashboardMenu?.contains(event.target)) {
    dashboardSidebar.classList.remove('open');
  }
});

const dashboardLinks = [...document.querySelectorAll('.dashboard-nav a[href]')];
const activeDashboardLink = dashboardLinks
  .filter(link => {
    const linkPath = new URL(link.href, window.location.origin).pathname;
    return window.location.pathname === linkPath || window.location.pathname.startsWith(linkPath);
  })
  .sort((firstLink, secondLink) => secondLink.pathname.length - firstLink.pathname.length)[0];

if (activeDashboardLink) {
  dashboardLinks.forEach(link => link.classList.remove('active'));
  activeDashboardLink.classList.add('active');
}

document.querySelectorAll('[data-dashboard-action]').forEach(button => {
  button.addEventListener('click', () => {
    button.classList.toggle('is-active');
  });
});

/* ─────────────────────────────────────────────────────────────
   Topbar search — live results dropdown shared by the candidate,
   employer and admin dashboards.
   ───────────────────────────────────────────────────────────── */
(() => {
  const root = document.querySelector('[data-dashboard-search]');
  if (!root) return;

  const input    = root.querySelector('[data-dashboard-search-input]');
  const panel    = root.querySelector('[data-dashboard-search-results]');
  const spinner  = root.querySelector('[data-dashboard-search-spinner]');
  const endpoint = root.dataset.searchUrl || '/dashboard/search/';

  if (!input || !panel) return;

  const MIN_CHARS   = 2;
  const DEBOUNCE_MS = 220;
  const MAX_ROWS    = 12;

  let timer       = null;
  let controller  = null;
  let lastQuery   = '';
  let activeIndex = -1;

  const ICONS = {
    candidate:    '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    employer:     '<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    match:        '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    request:      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    shortlist:    '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    profile:      '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    payment:      '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
    log:          '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
    notification: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  };

  const icon = kind =>
    `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[kind] || ICONS.profile}</svg>`;

  /* Escape user data before injecting it into innerHTML */
  const escapeHtml = value => String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const setBusy = busy => {
    if (spinner) spinner.hidden = !busy;
    root.classList.toggle('is-busy', busy);
  };

  const closePanel = () => {
    panel.hidden = true;
    panel.innerHTML = '';
    root.classList.remove('is-open');
    input.setAttribute('aria-expanded', 'false');
    activeIndex = -1;
  };

  const highlight = (text, term) => {
    const safe   = escapeHtml(text);
    const needle = String(term || '').trim();
    if (needle.length < MIN_CHARS) return safe;
    const pattern = new RegExp(`(${needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
    return safe.replace(pattern, '<mark>$1</mark>');
  };

  const renderMessage = (message, term) => {
    panel.innerHTML = `
      <div class="dashboard-search-empty">
        <span>${escapeHtml(message)}</span>
        <small>${term
          ? `No matches for &ldquo;${escapeHtml(term)}&rdquo;`
          : 'Type at least 2 characters to search.'}</small>
      </div>`;
    panel.hidden = false;
    root.classList.add('is-open');
    input.setAttribute('aria-expanded', 'true');
    activeIndex = -1;
  };

  const renderResults = (data, term) => {
    const results = Array.isArray(data.results) ? data.results : [];
    if (!results.length) {
      renderMessage('No results found', term);
      return;
    }

    const groups = Array.isArray(data.groups) && data.groups.length
      ? data.groups
      : [{ kind: results[0].kind, label: 'Results' }];

    let html  = '';
    let built = 0;

    groups.forEach(group => {
      const items = results.filter(r => r.kind === group.kind);
      if (!items.length) return;

      html += `<div class="dashboard-search-group">`
            + `<span class="dashboard-search-group-label">${escapeHtml(group.label)}</span>`;

      items.forEach(item => {
        if (built >= MAX_ROWS) return;
        html += `
          <a class="dashboard-search-row" role="option" aria-selected="false"
             data-index="${built}" href="${escapeHtml(item.url)}">
            <span class="dashboard-search-row-icon">${icon(item.kind)}</span>
            <span class="dashboard-search-row-text">
              <strong>${highlight(item.title, term)}</strong>
              ${item.subtitle ? `<small>${highlight(item.subtitle, term)}</small>` : ''}
            </span>
            ${item.badge ? `<span class="dashboard-search-row-badge">${escapeHtml(item.badge)}</span>` : ''}
          </a>`;
        built += 1;
      });

      html += '</div>';
    });

    panel.innerHTML = html;
    panel.hidden    = false;
    root.classList.add('is-open');
    input.setAttribute('aria-expanded', 'true');
    activeIndex = -1;
  };

  const runSearch = term => {
    if (controller) controller.abort();
    controller = new AbortController();
    setBusy(true);

    fetch(`${endpoint}?q=${encodeURIComponent(term)}`, {
      signal      : controller.signal,
      credentials : 'same-origin',
      headers     : { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(response => (response.ok ? response.json() : Promise.reject(response)))
      .then(data => renderResults(data, term))
      .catch(error => { if (error.name !== 'AbortError') closePanel(); })
      .finally(() => setBusy(false));
  };

  const setActiveRow = next => {
    const options = panel.querySelectorAll('.dashboard-search-row');
    if (!options.length) return;

    if (activeIndex >= 0 && options[activeIndex]) {
      options[activeIndex].classList.remove('is-active');
      options[activeIndex].setAttribute('aria-selected', 'false');
    }
    activeIndex = Math.max(0, Math.min(next, options.length - 1));
    options[activeIndex].classList.add('is-active');
    options[activeIndex].setAttribute('aria-selected', 'true');
    options[activeIndex].scrollIntoView({ block: 'nearest' });
  };

  input.addEventListener('input', () => {
    const term = input.value.trim();
    clearTimeout(timer);

    if (term.length < MIN_CHARS) {
      lastQuery = term;
      setBusy(false);
      renderMessage('', term);
      return;
    }
    if (term === lastQuery && panel.querySelector('.dashboard-search-row')) return;

    lastQuery = term;
    setBusy(true);
    timer = setTimeout(() => runSearch(term), DEBOUNCE_MS);
  });

  input.addEventListener('keydown', event => {
    const term = input.value.trim();

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (panel.hidden || !panel.querySelector('.dashboard-search-row')) {
        if (term.length >= MIN_CHARS) runSearch(term);
        return;
      }
      setActiveRow(event.key === 'ArrowDown' ? activeIndex + 1 : activeIndex - 1);

    } else if (event.key === 'Enter') {
      const options = panel.querySelectorAll('.dashboard-search-row');
      if (activeIndex >= 0 && options[activeIndex]) {
        event.preventDefault();
        window.location.href = options[activeIndex].getAttribute('href');
      } else if (term.length >= MIN_CHARS) {
        event.preventDefault();
        runSearch(term);
      }

    } else if (event.key === 'Escape') {
      if (!panel.hidden) { event.preventDefault(); closePanel(); }
    }
  });

  input.addEventListener('focus', () => {
    if (input.value.trim().length >= MIN_CHARS) runSearch(input.value.trim());
  });

  /* Close when clicking anywhere outside the search widget */
  document.addEventListener('click', event => {
    if (!root.contains(event.target)) closePanel();
  });

  /* Close when focus leaves the widget entirely (keyboard tabbing) */
  root.addEventListener('focusout', event => {
    if (!root.contains(event.relatedTarget)) closePanel();
  });
})();



/* ─────────────────────────────────────────────────────────────
   Notification bell dropdown — works on all 3 dashboards
   ───────────────────────────────────────────────────────────── */
(() => {
  const wrap = document.querySelector('[data-notif-bell]');
  if (!wrap) return;

  const btn      = wrap.querySelector('.notif-bell-btn');
  const panel    = document.getElementById('notif-bell-panel');
  const listEl   = wrap.querySelector('[data-notif-list]');
  const countEl  = wrap.querySelector('[data-notif-count]');
  const markAllBtn = wrap.querySelector('[data-notif-mark-all]');

  const FETCH_URL = wrap.dataset.fetchUrl;
  const READ_URL  = wrap.dataset.readUrl;

  let loaded   = false;  // fetched at least once
  let isOpen   = false;

  /* ── icon SVG paths per kind ── */
  const ICONS = {
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>',
    link:   '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    star:   '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    card:   '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
    user:   '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    bell:   '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  };

  const esc = v => String(v == null ? '' : v)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');

  const svgIcon = key =>
    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[key] || ICONS.bell}</svg>`;

  /* ── update badge count ── */
  function setBadge(n) {
    if (!countEl) return;
    countEl.textContent = n || '';
    countEl.classList.toggle('is-hidden', !n);
    if (n > 0) {
      countEl.classList.remove('pop');
      void countEl.offsetWidth; // reflow to restart animation
      countEl.classList.add('pop');
    }
  }

  /* ── render a single notification row ── */
  function buildItem(notif) {
    return `
      <div class="notif-drop-item ${notif.is_read ? '' : 'is-unread'}" data-notif-id="${notif.id}">
        <div class="notif-drop-icon notif-drop-icon--${esc(notif.kind)}">
          ${svgIcon(notif.icon)}
        </div>
        <div class="notif-drop-body">
          <div class="notif-drop-title">${esc(notif.title)}</div>
          <div class="notif-drop-msg">${esc(notif.message)}</div>
          <div class="notif-drop-meta">
            <span class="notif-drop-time">${esc(notif.time)}</span>
            ${!notif.is_read ? '<span class="notif-drop-unread-dot" aria-label="Unread"></span>' : ''}
          </div>
        </div>
      </div>`;
  }

  /* ── fetch and render notifications ── */
  function load() {
    if (!listEl) return;
    listEl.innerHTML = '<div class="notif-dropdown-loading"><span class="notif-spinner"></span></div>';

    fetch(FETCH_URL, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(r => r.ok ? r.json() : Promise.reject(r))
    .then(data => {
      const items = data.notifications || [];
      if (!items.length) {
        listEl.innerHTML = `
          <div class="notif-drop-empty">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span>You're all caught up!</span>
          </div>`;
      } else {
        listEl.innerHTML = items.map(buildItem).join('');
      }
      setBadge(data.unread || 0);
      loaded = true;
    })
    .catch(() => {
      listEl.innerHTML = '<div class="notif-drop-empty"><span>Could not load notifications.</span></div>';
    });
  }

  /* ── open / close ── */
  function openPanel() {
    panel.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    isOpen = true;
    if (!loaded) load();
  }

  function closePanel() {
    panel.hidden = true;
    btn.setAttribute('aria-expanded', 'false');
    isOpen = false;
  }

  /* ── toggle on bell click ── */
  btn.addEventListener('click', e => {
    e.stopPropagation();
    isOpen ? closePanel() : openPanel();
  });

  /* ── close on outside click ── */
  document.addEventListener('click', e => {
    if (isOpen && !wrap.contains(e.target)) closePanel();
  });

  /* ── close on Escape ── */
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isOpen) { closePanel(); btn.focus(); }
  });

  /* ── mark all read ── */
  function markAllRead() {
    if (!markAllBtn) return;
    markAllBtn.disabled = true;

    fetch(READ_URL, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
      },
      body: JSON.stringify({}),
    })
    .then(r => r.ok ? r.json() : Promise.reject(r))
    .then(data => {
      // Remove unread styling from all items in the panel
      listEl.querySelectorAll('.notif-drop-item.is-unread').forEach(el => {
        el.classList.remove('is-unread');
        const dot = el.querySelector('.notif-drop-unread-dot');
        if (dot) dot.remove();
      });
      setBadge(0);
      markAllBtn.disabled = false;
    })
    .catch(() => { markAllBtn.disabled = false; });
  }

  if (markAllBtn) markAllBtn.addEventListener('click', markAllRead);

  /* ── reload when the dropdown is opened again after navigating ── */
  // On browsers that cache pages (bfcache), reload when user returns
  window.addEventListener('pageshow', e => {
    if (e.persisted) { loaded = false; }
  });
})();
