/* ═══════════════════════════════════════════════
   Interactive checklist with localStorage persistence
   ═══════════════════════════════════════════════ */

(function () {
  const STORAGE_KEY = 'warp0716_customjobs_checklist';

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  }

  function saveState(state) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function updateProgress(card) {
    const items = card.querySelectorAll('input[type="checkbox"]');
    const checked = card.querySelectorAll('input[type="checkbox"]:checked').length;
    const total = items.length;

    const fill = card.querySelector('.checklist-progress-fill');
    const label = card.querySelector('.checklist-progress-label');

    if (fill) fill.style.width = total > 0 ? (checked / total * 100) + '%' : '0%';
    if (label) label.textContent = checked + ' / ' + total;
  }

  function init() {
    const state = loadState();
    const checkboxes = document.querySelectorAll('.checklist input[type="checkbox"]');

    checkboxes.forEach(function (cb) {
      var id = cb.getAttribute('data-id');
      if (!id) return;

      // Restore state
      if (state[id]) {
        cb.checked = true;
        cb.closest('li').classList.add('checked-item');
      }

      // Click handler
      cb.addEventListener('change', function () {
        var currentState = loadState();
        var li = cb.closest('li');

        if (cb.checked) {
          currentState[id] = true;
          li.classList.add('checked-item');
        } else {
          delete currentState[id];
          li.classList.remove('checked-item');
        }

        saveState(currentState);
        updateProgress(cb.closest('.checklist-card'));
      });

      // Let clicking the li text also toggle
      cb.closest('li').addEventListener('click', function (e) {
        if (e.target === cb) return; // already handled
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      });
    });

    // Reset buttons
    document.querySelectorAll('.checklist-reset').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var card = btn.closest('.checklist-card');
        var cbs = card.querySelectorAll('input[type="checkbox"]');
        var currentState = loadState();

        cbs.forEach(function (cb) {
          cb.checked = false;
          cb.closest('li').classList.remove('checked-item');
          delete currentState[cb.getAttribute('data-id')];
        });

        saveState(currentState);
        updateProgress(card);
      });
    });

    // Initial progress bars
    document.querySelectorAll('.checklist-card').forEach(updateProgress);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
