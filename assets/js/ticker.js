(function () {
  'use strict';

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

  async function loadTickerItems() {
    try {
      const res = await fetch('/data/ticker.json', { cache: 'no-store' });
      if (!res.ok) return null;
      const data = await res.json();
      if (!Array.isArray(data)) return null;
      return data.map(x => (typeof x === 'string' ? x : null)).filter(Boolean);
    } catch {
      return null;
    }
  }

  function initOne(el) {
    const track = el.querySelector('.ticker-track');
    if (!track) return;

    let items = null;

    function render() {
      const now = new Date();
      const clock = formatClock(now);

      const fallback = [
        '📌 Notebook ticker: notes • prices • weather',
        `🕰️ ${clock}`,
        '✨ Tip: hover to pause'
      ];

      const effective = (items && items.length ? items : fallback).map(s => {
        return s.replace('{TIME}', clock);
      });

      track.textContent = buildText(effective);
    }

    loadTickerItems().then(loaded => {
      items = loaded;
      render();
      // Update time once a minute.
      setInterval(render, 60 * 1000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-ticker]').forEach(initOne);
  });
})();
