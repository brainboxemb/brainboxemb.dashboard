(() => {
  const search = document.querySelector('#search');
  const problemsOnly = document.querySelector('#problems-only');
  const rows = [...document.querySelectorAll('.repo-row')];
  const groups = [...document.querySelectorAll('.group')];

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
