(() => {
  const search = document.querySelector('#search');
  const problemsOnly = document.querySelector('#problems-only');
  const rows = [...document.querySelectorAll('.repo-row')];
  const groups = [...document.querySelectorAll('.group')];

  const localDateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  for (const element of document.querySelectorAll('time[data-local-time]')) {
    const date = new Date(element.dateTime);
    if (!Number.isNaN(date.getTime())) {
      element.textContent = localDateTimeFormatter.format(date);
      element.title = element.dateTime;
    }
  }

  function relativeLabel(date, now = new Date()) {
    const seconds = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000));
    if (seconds < 60) return 'just now';

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;

    return localDateTimeFormatter.format(date);
  }

  function updateRelativeTimes() {
    const now = new Date();
    for (const element of document.querySelectorAll('time[data-relative-time]')) {
      const date = new Date(element.dateTime);
      if (!Number.isNaN(date.getTime())) {
        element.textContent = relativeLabel(date, now);
        element.title = localDateTimeFormatter.format(date);
      }
    }
  }

  updateRelativeTimes();
  window.setInterval(updateRelativeTimes, 30_000);

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
