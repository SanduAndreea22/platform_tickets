/* Theme, mobile nav, dropdowns, toasts, scroll-reveal. Shared by both shells. */
function setTheme(mode) {
  document.documentElement.setAttribute("data-theme", mode);
  document.querySelectorAll("#themeToggle i").forEach(function (icon) {
    icon.classList.toggle("fa-sun", mode === "dark");
    icon.classList.toggle("fa-moon", mode !== "dark");
  });
  document.dispatchEvent(new CustomEvent("themechange", { detail: mode }));
}

(function initTheme() {
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) {}
  setTheme(saved || document.documentElement.getAttribute("data-theme") || "light");
})();

var themeToggle = document.getElementById("themeToggle");
if (themeToggle) {
  themeToggle.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", next); } catch (e) {}
    setTheme(next);
  });
}

/* Mobile menu */
var menuToggle = document.getElementById("menuToggle");
var navbar = document.getElementById("navbar");
if (menuToggle && navbar) {
  menuToggle.addEventListener("click", function (e) {
    e.stopPropagation();
    var open = navbar.classList.toggle("is-open");
    var icon = menuToggle.querySelector("i");
    if (icon) { icon.classList.toggle("fa-bars", !open); icon.classList.toggle("fa-xmark", open); }
  });
  document.addEventListener("click", function (e) {
    if (!navbar.contains(e.target)) navbar.classList.remove("is-open");
  });
}

/* Dropdown */
document.querySelectorAll(".dropdown-btn").forEach(function (btn) {
  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    var panel = btn.closest(".dropdown").querySelector(".dropdown-content");
    document.querySelectorAll(".dropdown-content.is-open").forEach(function (p) { if (p !== panel) p.classList.remove("is-open"); });
    panel.classList.toggle("is-open");
  });
});
document.addEventListener("click", function () {
  document.querySelectorAll(".dropdown-content").forEach(function (p) { p.classList.remove("is-open"); });
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") document.querySelectorAll(".dropdown-content").forEach(function (p) { p.classList.remove("is-open"); });
});

/* Toasts: auto-dismiss + manual close */
document.querySelectorAll(".message-card").forEach(function (card, i) {
  function close() { card.classList.add("is-leaving"); setTimeout(function () { card.remove(); }, 320); }
  var btn = card.querySelector(".toast-close");
  if (btn) btn.addEventListener("click", close);
  setTimeout(close, 6500 + i * 600);
});

/* Scroll reveal */
(function () {
  var els = document.querySelectorAll(".reveal-up");
  if (!els.length) return;
  if (!("IntersectionObserver" in window)) { els.forEach(function (el) { el.classList.add("is-in"); }); return; }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); } });
  }, { threshold: .12 });
  els.forEach(function (el, i) { el.style.transitionDelay = Math.min(i % 6, 5) * 60 + "ms"; io.observe(el); });
})();

/* Password reveal (login/register) */
function togglePassword() {
  var pass = document.getElementById("password");
  var icon = document.getElementById("eyeIcon");
  if (!pass) return;
  var show = pass.type === "password";
  pass.type = show ? "text" : "password";
  if (icon) { icon.classList.toggle("fa-eye", !show); icon.classList.toggle("fa-eye-slash", show); }
}

/* Transparent header over dark hero sections, solid once scrolled */
(function () {
  var header = document.querySelector(".site-header");
  if (!header || !document.querySelector(".hero, .discover-head, .detail-hero, .content-hero")) return;
  function update() { header.classList.toggle("on-hero", window.scrollY < 24); }
  update();
  window.addEventListener("scroll", update, { passive: true });
})();
