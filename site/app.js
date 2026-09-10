(() => {
  const search = document.querySelector('#search');
  const problemsOnly = document.querySelector('#problems-only');
  const rows = [...document.querySelectorAll('.repo-row')];
  const groups = [...document.querySelectorAll('.group')];

  const localDateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
  const localDateFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  });

  for (const element of document.querySelectorAll('time[data-local-time]')) {
    const date = new Date(element.dateTime);
    if (!Number.isNaN(date.getTime())) {
      element.textContent = localDateTimeFormatter.format(date);
      element.title = element.dateTime;
    }
  }

  const repositoryCheckItem = [...document.querySelectorAll('.refresh-meta__item')]
    .find((item) => item.querySelector('.refresh-meta__label')?.textContent.trim() === 'Repository check');
  const repositoryCheckValue = repositoryCheckItem?.querySelector('.refresh-meta__value');
  if (repositoryCheckValue) {
    repositoryCheckValue.textContent = 'scheduled hourly at :11';
    repositoryCheckValue.title = 'Best-effort GitHub schedule for 11 minutes past every hour; scheduled runs may be delayed or missed.';
  }

  function relativeLabel(date, now = new Date()) {
    const seconds = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000));
    if (seconds < 60) return 'just now';

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    if (days <= 99) return `${days}d ago`;

    return '>99d ago';
  }

  function updateRelativeTimes() {
    const now = new Date();
    for (const element of document.querySelectorAll('time[data-relative-time]')) {
      const date = new Date(element.dateTime);
      if (!Number.isNaN(date.getTime())) {
        element.textContent = relativeLabel(date, now);
        element.title = localDateFormatter.format(date);
      }
    }
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function formatDuration(value) {
    if (value === null || value === undefined || value === '') return '—';
    const seconds = Number(value);
    if (!Number.isFinite(seconds)) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;

    const minutes = seconds / 60;
    if (minutes < 60) return `${minutes < 10 ? minutes.toFixed(1) : Math.round(minutes)}m`;

    const hours = minutes / 60;
    return `${hours < 10 ? hours.toFixed(1) : Math.round(hours)}h`;
  }

  function formatPercent(value) {
    if (value === null || value === undefined || value === '') return '—';
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(number % 1 ? 1 : 0)}%` : '—';
  }

  function metricCard(label, value, title = '') {
    return `<div class="metric-card"${title ? ` title="${escapeHtml(title)}"` : ''}><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
  }

  function metricRows(items, workflowRows = false) {
    return items.map((item) => {
      const label = workflowRows
        ? `${escapeHtml(item.repository)} · ${escapeHtml(item.name)}`
        : escapeHtml(item.name);
      const href = escapeHtml(item.url || '#');
      return `<tr>
        <td><a href="${href}" target="_blank" rel="noopener">${label}</a></td>
        <td class="metrics-number">${escapeHtml(item.runs)}</td>
        <td class="metrics-number">${formatPercent(item.success_rate)}</td>
        <td class="metrics-number">${escapeHtml(item.failed)}</td>
        <td class="metrics-number">${escapeHtml(item.cancelled)}</td>
        <td class="metrics-number">${formatDuration(item.runtime_seconds)}</td>
        <td class="metrics-number">${formatDuration(item.avg_runtime_seconds)}</td>
        <td class="metrics-number">${formatDuration(item.avg_queue_seconds)}</td>
      </tr>`;
    }).join('');
  }

  function renderActionMetrics(metrics) {
    const anchor = document.querySelector('.summary-grid');
    const summary = metrics?.summary;
    if (!anchor || !summary) return;

    const windowDays = Number(metrics.window_days) || 30;
    const repositories = Array.isArray(metrics.repositories) ? metrics.repositories : [];
    const workflows = Array.isArray(metrics.workflows) ? metrics.workflows.slice(0, 30) : [];
    const section = document.createElement('section');
    section.className = 'group metrics-group';
    section.innerHTML = `
      <h2>Actions metrics</h2>
      <p class="group-note">Last ${windowDays} days · collected at most once per UTC day · derived from workflow run history. Runtime is wall-clock workflow duration, not billable Actions minutes.</p>
      <div class="metrics-grid">
        ${metricCard('Runs', summary.runs)}
        ${metricCard('Success rate', formatPercent(summary.success_rate), 'Success divided by success plus failure-like conclusions; cancelled and neutral runs are shown separately.')}
        ${metricCard('Failed', summary.failed)}
        ${metricCard('Cancelled', summary.cancelled)}
        ${metricCard('Runtime', formatDuration(summary.runtime_seconds))}
        ${metricCard('Avg runtime', formatDuration(summary.avg_runtime_seconds))}
        ${metricCard('Avg queue', formatDuration(summary.avg_queue_seconds))}
      </div>
      <details class="metrics-details">
        <summary>By repository</summary>
        <div class="table-wrap metrics-table-wrap"><table class="metrics-table">
          <thead><tr><th>Repository</th><th>Runs</th><th>Success</th><th>Failed</th><th>Cancelled</th><th>Runtime</th><th>Avg runtime</th><th>Avg queue</th></tr></thead>
          <tbody>${metricRows(repositories)}</tbody>
        </table></div>
      </details>
      <details class="metrics-details">
        <summary>Top workflows by runtime</summary>
        <div class="table-wrap metrics-table-wrap"><table class="metrics-table">
          <thead><tr><th>Workflow</th><th>Runs</th><th>Success</th><th>Failed</th><th>Cancelled</th><th>Runtime</th><th>Avg runtime</th><th>Avg queue</th></tr></thead>
          <tbody>${metricRows(workflows, true)}</tbody>
        </table></div>
      </details>`;
    anchor.insertAdjacentElement('afterend', section);
  }

  async function loadActionMetrics() {
    try {
      const metricsUrl = new URL('action-metrics.json', window.location.href);
      metricsUrl.searchParams.set('_check', Date.now().toString());
      const response = await fetch(metricsUrl, { cache: 'no-store' });
      if (!response.ok) return;
      renderActionMetrics(await response.json());
    } catch (error) {
      // Metrics are supplemental; keep the main status dashboard usable if unavailable.
    }
  }

  updateRelativeTimes();
  window.setInterval(updateRelativeTimes, 30_000);
  loadActionMetrics();

  const generatedElement = document.querySelector('time[data-dashboard-generated]');
  const checkButton = document.querySelector('#check-dashboard');
  const lastCheckedElement = document.querySelector('#last-checked');
  const currentGeneratedAt = generatedElement ? new Date(generatedElement.dateTime).getTime() : 0;

  function markChecked() {
    if (!lastCheckedElement) return;
    const now = new Date();
    lastCheckedElement.dateTime = now.toISOString();
    lastCheckedElement.textContent = localDateTimeFormatter.format(now);
    lastCheckedElement.title = `Checked ${localDateTimeFormatter.format(now)} whether a newer deployed dashboard page is available; repository data was not queried.`;
  }

  async function checkForDashboardUpdate(showFeedback = false) {
    if (showFeedback && checkButton) {
      checkButton.disabled = true;
      checkButton.textContent = 'Checking…';
    }

    try {
      const checkUrl = new URL(window.location.href);
      checkUrl.searchParams.set('_check', Date.now().toString());

      const response = await fetch(checkUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      markChecked();

      const source = await response.text();
      const documentCopy = new DOMParser().parseFromString(source, 'text/html');
      const candidate = documentCopy.querySelector('time[data-dashboard-generated]');
      const candidateTime = candidate ? new Date(candidate.dateTime).getTime() : 0;

      if (candidateTime > currentGeneratedAt) {
        const reloadUrl = new URL(window.location.href);
        reloadUrl.searchParams.set('_v', candidateTime.toString());
        window.location.replace(reloadUrl.toString());
        return;
      }

      if (showFeedback && checkButton) {
        checkButton.textContent = 'Up to date';
        window.setTimeout(() => {
          checkButton.textContent = 'Check for update';
          checkButton.disabled = false;
        }, 1800);
      }
    } catch (error) {
      markChecked();
      if (showFeedback && checkButton) {
        checkButton.textContent = 'Check failed';
        window.setTimeout(() => {
          checkButton.textContent = 'Check for update';
          checkButton.disabled = false;
        }, 2200);
      }
    }
  }

  markChecked();

  if (checkButton) {
    checkButton.addEventListener('click', () => checkForDashboardUpdate(true));
  }

  window.setInterval(() => checkForDashboardUpdate(false), 60_000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') checkForDashboardUpdate(false);
  });

  function applyFilters() {
    const term = (search.value || '').trim().toLowerCase();
    const problems = problemsOnly.checked;

    for (const row of rows) {
      const text = row.dataset.search || '';
      const matchesText = !term || text.includes(term);
      const matchesProblem = !problems || row.dataset.problem === 'true';
      row.classList.toggle('hidden', !(matchesText && matchesProblem));
    }

    for (const group of groups) {
      const visible = [...group.querySelectorAll('.repo-row')].some(row => !row.classList.contains('hidden'));
      group.classList.toggle('hidden', !visible);
    }
  }

  search.addEventListener('input', applyFilters);
  problemsOnly.addEventListener('change', applyFilters);
})();
