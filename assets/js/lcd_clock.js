(function () {
  'use strict';

  function updateClock() {
    const clockEl = document.querySelector('[data-clock]');
    if (!clockEl) return;

    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    clockEl.textContent = `${hours}:${minutes}`;
    // Optional: show seconds in title/data attribute
    clockEl.setAttribute('data-seconds', seconds);
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateClock();
    // Update every second
    setInterval(updateClock, 1000);
  });
})();
