document.addEventListener('DOMContentLoaded', function () {
  const sizes = ['compact', 'comfortable', 'large'];
  const labels = { compact: 'A–', comfortable: 'A', large: 'A+' };
  const root = document.documentElement;

  function applySize(size) {
    sizes.forEach(s => root.classList.remove('reader-' + s));
    root.classList.add('reader-' + size);
    localStorage.setItem('readerFontSize', size);
    // update buttons
    document.querySelectorAll('.reader-controls button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.size === size);
    });
  }

  // create controls
  const header = document.querySelector('.site-header');
  if (!header) return;
  const wrap = document.createElement('div');
  wrap.className = 'reader-controls';
  sizes.forEach(size => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.dataset.size = size;
    btn.textContent = labels[size];
    btn.title = size;
    btn.addEventListener('click', () => applySize(size));
    wrap.appendChild(btn);
  });

  // insert controls into header (right side)
  header.appendChild(wrap);

  // inject minimal styles (fallback if CSS not loaded)
  const style = document.createElement('style');
  style.textContent = `
    .reader-controls{display:flex;gap:0.4rem;align-items:center;margin-left:1rem}
    .reader-controls button{background:transparent;border:1px solid #ddd;padding:0.25rem 0.5rem;border-radius:4px;cursor:pointer;font-family:inherit}
    .reader-controls button.active{background:#111;color:#fff;border-color:#111}
  `;
  document.head.appendChild(style);

  const saved = localStorage.getItem('readerFontSize') || 'comfortable';
  applySize(saved);
});
