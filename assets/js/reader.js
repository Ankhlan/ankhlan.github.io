document.addEventListener('DOMContentLoaded', function () {
  const sizes = ['compact', 'comfortable', 'large'];
  const labels = { compact: 'A–', comfortable: 'A', large: 'A+' };
  const aligns = ['left', 'center'];
  const alignLabels = { left: 'Left', center: 'Center' };
  const root = document.documentElement;

  function applySize(size) {
    sizes.forEach(s => root.classList.remove('reader-' + s));
    root.classList.add('reader-' + size);
    localStorage.setItem('readerFontSize', size);
    // update buttons
    document.querySelectorAll('.reader-controls button[data-size]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.size === size);
    });
  }

  function applyAlign(align) {
    root.classList.remove('layout-left', 'layout-center');
    root.classList.add('layout-' + align);
    localStorage.setItem('readerAlign', align);

    // Apply a scoped inline style fallback so alignment always works,
    // even if page-specific CSS rules override margins.
    document.querySelectorAll('main.page > .intro, main.page > .section-block, main.page > article').forEach(el => {
      if (align === 'left') {
        el.style.marginLeft = '0';
        el.style.marginRight = 'auto';
      } else {
        el.style.marginLeft = 'auto';
        el.style.marginRight = 'auto';
      }
    });

    document.querySelectorAll('.reader-controls button[data-align]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.align === align);
    });
  }

  // create controls
  const header = document.querySelector('.site-header');
  if (!header) return;
  const wrap = document.createElement('div');
  wrap.className = 'reader-controls';

  const sizeRow = document.createElement('div');
  sizeRow.className = 'reader-row reader-row-size';
  sizes.forEach(size => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.dataset.size = size;
    btn.textContent = labels[size];
    btn.title = 'Font size: ' + size;
    btn.addEventListener('click', () => applySize(size));
    sizeRow.appendChild(btn);
  });

  const alignRow = document.createElement('div');
  alignRow.className = 'reader-row reader-row-align';
  aligns.forEach(align => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.dataset.align = align;
    btn.textContent = alignLabels[align];
    btn.title = 'Text column: ' + align;
    btn.addEventListener('click', () => applyAlign(align));
    alignRow.appendChild(btn);
  });

  wrap.appendChild(sizeRow);
  wrap.appendChild(alignRow);

  // insert controls into header (right side)
  const tickerBar = header.querySelector('.ticker-bar');
  if (tickerBar) {
    header.insertBefore(wrap, tickerBar);
  } else {
    header.appendChild(wrap);
  }

  // inject minimal styles (fallback if CSS not loaded)
  const style = document.createElement('style');
  style.textContent = `
    .reader-controls{display:flex;flex-direction:column;gap:0.35rem;align-items:flex-end;margin-left:1rem}
    .reader-row{display:flex;gap:0.4rem;align-items:center}
    .reader-controls button{background:transparent;border:1px solid #ddd;padding:0.25rem 0.5rem;border-radius:4px;cursor:pointer;font-family:inherit}
    .reader-controls button.active{background:#111;color:#fff;border-color:#111}
  `;
  document.head.appendChild(style);

  const saved = localStorage.getItem('readerFontSize') || 'comfortable';
  applySize(saved);

  const savedAlign = localStorage.getItem('readerAlign') || 'center';
  applyAlign(savedAlign);
});
