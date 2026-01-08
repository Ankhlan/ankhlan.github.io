(function () {
  'use strict';

  const POLL_DURATION = 30; // seconds per poll
  let currentPollIdx = 0;
  let pollData = [];
  let timerInterval = null;

  async function loadJson(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  function generateQrUrl(text) {
    // QR code via api.qrserver.com
    const encoded = encodeURIComponent(text);
    return `https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encoded}`;
  }

  function displayPoll(container, pollIdx) {
    if (!pollData || !pollData.polls || pollIdx >= pollData.polls.length) return;

    const poll = pollData.polls[pollIdx];
    const qEl = container.querySelector('.poll-q');
    const optsEl = container.querySelector('.poll-options');
    const qrEl = container.querySelector('.poll-qr-code');
    const timerEl = container.querySelector('.poll-timer');

    if (qEl) qEl.textContent = 'Q: ' + (poll.question || 'Loading…');

    if (optsEl && poll.options) {
      optsEl.innerHTML = poll.options
        .map((opt, i) => {
          const count = (poll.votes || [])[i] || 0;
          return `<div class="poll-opt">${opt}: <span class="poll-count">${count}</span></div>`;
        })
        .join('');
    }

    // Generate QR code pointing to voting endpoint
    if (qrEl) {
      const votingUrl = `${window.location.origin}/vote?poll=${pollIdx}`;
      qrEl.src = generateQrUrl(votingUrl);
      qrEl.alt = `Vote: ${poll.question}`;
    }

    // Reset timer
    if (timerEl) {
      timerEl.setAttribute('data-timer', POLL_DURATION);
      timerEl.textContent = POLL_DURATION + 's';
    }
  }

  function rotatePoll(container) {
    if (!pollData.polls) return;
    currentPollIdx = (currentPollIdx + 1) % pollData.polls.length;
    displayPoll(container, currentPollIdx);
  }

  function startTimer(container) {
    if (timerInterval) clearInterval(timerInterval);

    timerInterval = setInterval(function () {
      const timerEl = container.querySelector('.poll-timer');
      if (!timerEl) return;

      let remaining = parseInt(timerEl.getAttribute('data-timer'), 10) || POLL_DURATION;
      remaining -= 1;

      if (remaining <= 0) {
        rotatePoll(container);
      } else {
        timerEl.setAttribute('data-timer', remaining);
        timerEl.textContent = remaining + 's';
      }
    }, 1000);
  }

  function initPolls(container) {
    const src = container.getAttribute('data-polls-src') || '/data/polls.json';

    loadJson(src).then(data => {
      if (!data || !data.polls || !data.polls.length) return;

      pollData = data;
      currentPollIdx = 0;

      displayPoll(container, currentPollIdx);
      startTimer(container);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-lcd-polls]').forEach(initPolls);
  });
})();
