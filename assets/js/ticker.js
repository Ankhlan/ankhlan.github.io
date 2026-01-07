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

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function formatClock(now) {
    // UB is UTC+8 (no DST). Keep it simple.
    const utc = `${pad2(now.getUTCHours())}:${pad2(now.getUTCMinutes())} UTC`;
    const ubHours = (now.getUTCHours() + 8) % 24;
    const ub = `${pad2(ubHours)}:${pad2(now.getUTCMinutes())} UB`;
    return `${ub} · ${utc}`;
  }

  function buildText(items) {
    const sep = '   •   ';
    const base = items.filter(Boolean).join(sep);
    // Repeat so the scroll feels continuous even on wide screens.
    return `${base}${sep}${base}${sep}${base}`;
  }

  function normalizeTickerItems(data) {
    if (!Array.isArray(data)) return null;
    return data
      .map(x => {
        if (typeof x === 'string') return x;
        if (x && typeof x === 'object' && typeof x.text === 'string') return x.text;
        return null;
      })
      .filter(Boolean);
  }

  function normalizePrices(data) {
    if (!data || typeof data !== 'object') return {};
    // Accept either { key: "value" } or { values: { key: "value" } }
    const values = (data.values && typeof data.values === 'object') ? data.values : data;
    const out = {};
    for (const [k, v] of Object.entries(values)) {
      if (typeof v === 'string' || typeof v === 'number') out[String(k)] = String(v);
    }
    return out;
  }

  function applyTokens(str, tokens) {
    if (!str) return str;

    let s = str;
    if (tokens.TIME) s = s.replaceAll('{TIME}', tokens.TIME);

    // {PRICE:BTCUSD}
    s = s.replace(/\{PRICE:([^}]+)\}/g, (m, key) => {
      const k = String(key || '').trim();
      if (!k) return m;
      return Object.prototype.hasOwnProperty.call(tokens.PRICES, k) ? tokens.PRICES[k] : m;
    });

    return s;
  }

  function initOne(el) {
    const track = el.querySelector('.ticker-track');
    if (!track) return;

    let items = null;
    let prices = {};

    const tickerSrc = el.getAttribute('data-ticker-src') || '/data/ticker.json';
    const pricesSrc = el.getAttribute('data-prices-src') || '/data/prices.json';

    function render() {
      const now = new Date();
      const clock = formatClock(now);

      const tokens = { TIME: clock, PRICES: prices };

      const fallback = [
        '📌 Notebook ticker: notes • prices • weather',
        `🕰️ ${clock}`,
        '✨ Tip: hover to pause'
      ];

      const effective = (items && items.length ? items : fallback).map(s => applyTokens(s, tokens));

      track.textContent = buildText(effective);
    }

    Promise.all([loadJson(tickerSrc), loadJson(pricesSrc)]).then(([tickerData, pricesData]) => {
      items = normalizeTickerItems(tickerData);
      prices = normalizePrices(pricesData);
      render();
      // Update time once a minute.
      setInterval(render, 60 * 1000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-ticker]').forEach(initOne);
  });
})();
