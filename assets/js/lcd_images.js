(function () {
  'use strict';

  async function loadJsonArray(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) return null;
      const data = await res.json();
      if (!Array.isArray(data)) return null;
      return data.map(x => (typeof x === 'string' ? x.trim() : '')).filter(Boolean);
    } catch {
      return null;
    }
  }

  function setSquare(el, url) {
    if (!url) {
      el.classList.remove('is-image');
      el.style.backgroundImage = '';
      return;
    }

    // Keep the first layer as the image, second as the subtle dot grid.
    el.classList.add('is-image');
    el.style.backgroundImage = `url("${url}"), radial-gradient(rgba(255, 255, 255, 0.08) 1px, rgba(0, 0, 0, 0) 1px)`;
  }

  function initOne(container) {
    const src = container.getAttribute('data-images-src') || '/data/lcd_images.json';
    const squares = Array.from(container.querySelectorAll('.lcd-square'));
    if (squares.length === 0) return;

    let urls = [];
    let idx = 0;

    function render() {
      if (!urls.length) {
        squares.forEach(s => setSquare(s, ''));
        return;
      }

      for (let i = 0; i < squares.length; i++) {
        const url = urls[(idx + i) % urls.length];
        setSquare(squares[i], url);
      }
      idx = (idx + squares.length) % urls.length;
    }

    loadJsonArray(src).then(list => {
      urls = list || [];
      render();
      // Rotate images periodically.
      setInterval(render, 12 * 1000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-lcd-images]').forEach(initOne);
  });
})();
