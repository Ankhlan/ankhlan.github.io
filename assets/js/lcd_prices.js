(function () {
  'use strict';

  async function loadJson(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  function initPrices(container) {
    const src = container.getAttribute('data-prices-src') || '/data/prices.json';

    loadJson(src).then(data => {
      if (!data || !data.values) return;

      const items = container.querySelectorAll('.price-item');
      const keys = ['BTCUSD', 'XAUUSD', 'EURUSD'];

      keys.forEach((key, idx) => {
        if (idx < items.length) {
          const val = data.values[key] || '—';
          items[idx].querySelector('.price-value').textContent = val;
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-lcd-prices]').forEach(initPrices);
  });
})();
