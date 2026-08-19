document.addEventListener("DOMContentLoaded", function () {
  const URGENT_THRESHOLD_MS = 2 * 60 * 1000;

  function formatRemaining(ms) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")} left`;
  }

  function tick() {
    document.querySelectorAll(".reservation-expiry[data-expires-at]").forEach((el) => {
      const expiresAt = new Date(el.dataset.expiresAt).getTime();
      const countdownEl = el.querySelector(".reservation-countdown");
      if (!countdownEl || Number.isNaN(expiresAt)) return;

      const remaining = expiresAt - Date.now();

      if (remaining <= 0) {
        countdownEl.textContent = "expired";
        el.classList.add("is-expired");
        return;
      }

      countdownEl.textContent = formatRemaining(remaining);
      el.classList.toggle("is-urgent", remaining <= URGENT_THRESHOLD_MS);
    });
  }

  tick();
  setInterval(tick, 1000);
});
