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

  function initWeather(container) {
    const src = container.getAttribute('data-weather-src') || '/data/weather.json';

    loadJson(src).then(data => {
      if (!data) return;

      const temp = container.querySelector('[class*="weather-value"]:nth-child(1)');
      const humidity = container.querySelector('[class*="weather-value"]:nth-child(2)');
      const wind = container.querySelector('[class*="weather-value"]:nth-child(3)');

      if (temp) temp.textContent = data.temp || '—°C';
      if (humidity) humidity.textContent = data.humidity || '—%';
      if (wind) wind.textContent = data.wind || '—';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-lcd-weather]').forEach(initWeather);
  });
})();
