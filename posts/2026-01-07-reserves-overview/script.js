/**
 * Central Bank Reserves: Real-Time Circular Consciousness Loop
 * A political engagement art piece representing Mongolia's financial & social data
 * Updates in real-time from shared data feeds
 */

(function () {
  'use strict';

  const CONFIG = {
    dataUrl: '/data/reserves.json', // Will fetch real reserve data
    updateInterval: 5000, // Update every 5 seconds
    animationDuration: 1500, // Smooth transitions
  };

  // Fallback demo data (will be replaced by real data)
  const DEMO_DATA = {
    total: 3850,
    unit: 'USD Millions',
    components: [
      { label: 'Foreign Exchange', value: 2400, key: 'fx', change: 0.5 },
      { label: 'Gold', value: 850, key: 'gold', change: -0.2 },
      { label: 'SDRs & IMF', value: 450, key: 'sdr', change: 0 },
      { label: 'Other Assets', value: 150, key: 'other', change: 1.2 },
    ],
    timestamp: new Date().toISOString(),
    mongoliaCitizenEngagement: 42, // Example: percent public engagement
  };

  class ReservesCircle {
    constructor() {
      this.data = DEMO_DATA;
      this.container = document.querySelector('.circular-loop');
      this.init();
    }

    init() {
      this.render();
      this.setupEventListeners();
      this.startAutoUpdate();
      this.initializeSegments();
    }

    render() {
      // Render center value
      const centerValue = document.querySelector('.circle-center-value');
      if (centerValue) {
        centerValue.textContent = `$${this.data.total}M`;
      }

      // Render cards
      this.renderCards();
    }

    renderCards() {
      const grid = document.querySelector('.reserves-grid');
      if (!grid) return;

      grid.innerHTML = this.data.components
        .map((comp) => this.createCard(comp))
        .join('');

      // Add live engagement card
      const engagementCard = document.createElement('div');
      engagementCard.className = 'reserve-card card-other';
      engagementCard.innerHTML = `
        <h3>🇲🇳 Public Pulse</h3>
        <div class="value">${this.data.mongoliaCitizenEngagement}%</div>
        <div class="change neutral">Engaged citizens</div>
      `;
      grid.appendChild(engagementCard);
    }

    createCard(component) {
      const percentage = ((component.value / this.data.total) * 100).toFixed(1);
      const changeClass =
        component.change > 0 ? 'positive' : component.change < 0 ? 'negative' : 'neutral';
      const changeSymbol = component.change > 0 ? '↑' : component.change < 0 ? '↓' : '→';

      return `
        <div class="reserve-card card-${component.key}">
          <h3>${component.label}</h3>
          <div class="value">$${component.value}M</div>
          <div style="font-size: 0.8rem; color: rgba(255,255,255,0.6);">${percentage}%</div>
          <div class="change ${changeClass}">
            ${changeSymbol} ${Math.abs(component.change).toFixed(2)}%
          </div>
        </div>
      `;
    }

    initializeSegments() {
      // Position segments dynamically
      const segments = document.querySelectorAll('.segment');
      segments.forEach((seg, idx) => {
        const angle = (idx / segments.length) * 360;
        seg.style.transform = `rotate(${angle}deg) translateY(-180px) rotate(-${angle}deg)`;
        seg.addEventListener('click', () => this.onSegmentClick(idx));
      });
    }

    onSegmentClick(idx) {
      const component = this.data.components[idx];
      if (component) {
        console.log(`Selected: ${component.label} - $${component.value}M`);
        // Could trigger modal or details view
        this.showSegmentDetails(component);
      }
    }

    showSegmentDetails(component) {
      // Simple alert or could show modal
      const msg = `${component.label}\n$${component.value}M (${((component.value / this.data.total) * 100).toFixed(1)}%)\nChange: ${component.change > 0 ? '+' : ''}${component.change}%`;
      console.log(msg);
    }

    setupEventListeners() {
      // Click segments for details
      document.addEventListener('click', (e) => {
        if (e.target.closest('.segment')) {
          const idx = Array.from(document.querySelectorAll('.segment')).indexOf(e.target.closest('.segment'));
          this.onSegmentClick(idx);
        }
      });
    }

    async fetchLiveData() {
      try {
        const res = await fetch(CONFIG.dataUrl, { cache: 'no-store' });
        if (res.ok) {
          const newData = await res.json();
          this.updateData(newData);
        }
      } catch (err) {
        console.log('Using fallback data (API unavailable):', err);
      }
    }

    updateData(newData) {
      // Smooth update with animation
      const oldTotal = this.data.total;
      this.data = { ...this.data, ...newData };

      // Animate transition
      this.animateValueChange(oldTotal, this.data.total);
      this.renderCards();
    }

    animateValueChange(from, to) {
      const centerValue = document.querySelector('.circle-center-value');
      if (!centerValue) return;

      const diff = to - from;
      const steps = 30;
      let current = 0;

      const interval = setInterval(() => {
        current++;
        const progress = current / steps;
        const easeValue = Math.easeInOutQuad(progress);
        const displayed = Math.round(from + diff * easeValue);
        centerValue.textContent = `$${displayed}M`;

        if (current >= steps) {
          clearInterval(interval);
          centerValue.textContent = `$${to}M`;
        }
      }, CONFIG.animationDuration / steps);
    }

    startAutoUpdate() {
      setInterval(() => this.fetchLiveData(), CONFIG.updateInterval);
    }
  }

  // Easing function for smooth animations
  Math.easeInOutQuad = function (t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
  };

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    new ReservesCircle();

    // Update timestamp
    const timestamp = document.querySelector('.data-timestamp');
    if (timestamp) {
      timestamp.textContent = `Last updated: ${new Date().toLocaleString('en-US')}`;
    }
  });
})();
